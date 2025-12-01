"""
Plan Executor - 계획 실행 및 에러 정책 기반 재계획.

PlanStep들을 위상 정렬하여 순차/병렬 실행.
에러 발생 시 ERROR_POLICY에 따라 재시도/대체/질문 전환.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Set

from backend.agents.shared.contracts import (
    AgentType,
    ErrorAction,
    ErrorKind,
    PlanStep,
    AgentError,
    ERROR_POLICY,
)
from backend.common.events import (
    EventType,
    emit_event,
    persist_artifact,
    span,
)
from backend.common.parallel import run_parallel

logger = logging.getLogger(__name__)

# 최대 재시도 횟수
MAX_RETRIES = 2
# 백오프 배수
BACKOFF_MULTIPLIER = 1.5


def topological_sort(steps: List[PlanStep]) -> List[List[PlanStep]]:
    if not steps:
        return []
    
    # 의존성 그래프 구성
    step_map = {step.id: step for step in steps}
    in_degree: Dict[str, int] = defaultdict(int)
    dependents: Dict[str, List[str]] = defaultdict(list)
    
    for step in steps:
        in_degree[step.id]  # 초기화
        for need in step.needs:
            if need in step_map:
                dependents[need].append(step.id)
                in_degree[step.id] += 1
    
    # BFS로 레벨별 정렬
    levels: List[List[PlanStep]] = []
    current_level = [step_map[sid] for sid, deg in in_degree.items() if deg == 0]
    
    while current_level:
        levels.append(current_level)
        next_level_ids: Set[str] = set()
        
        for step in current_level:
            for dep_id in dependents[step.id]:
                in_degree[dep_id] -= 1
                if in_degree[dep_id] == 0:
                    next_level_ids.add(dep_id)
        
        current_level = [step_map[sid] for sid in next_level_ids]
    
    return levels


class PlanExecutionContext:
    """Plan 실행 컨텍스트."""
    def __init__(
        self, 
        session_id: str,
        agent_runners: Dict[AgentType, Callable],
        state: Dict[str, Any],
    ):
        self.session_id = session_id
        self.agent_runners = agent_runners
        self.state = state
        self.results: Dict[str, Dict[str, Any]] = {}
        self.artifacts: Dict[str, List[str]] = {}
        self.errors: List[Dict[str, Any]] = []
        self.aborted = False
        self.disambiguation_required = False


def _run_single_step(
    step: PlanStep,
    ctx: PlanExecutionContext,
) -> Dict[str, Any]:
    """단일 스텝 실행."""
    actor = f"node:{step.agent.value}"
    
    with span(f"step_{step.id}", actor=actor):
        emit_event(
            EventType.NODE_STARTED,
            actor=actor,
            inputs={"step_id": step.id, "params": step.params}
        )
        
        start_time = time.time()
        
        try:
            # Agent runner 가져오기
            runner = ctx.agent_runners.get(step.agent)
            if not runner:
                raise AgentError(
                    f"Agent runner not found: {step.agent.value}",
                    kind=ErrorKind.INVALID_INPUT
                )
            
            # 선행 스텝 결과 수집
            deps = {}
            for need_id in step.needs:
                if need_id in ctx.results:
                    deps[need_id] = ctx.results[need_id]
            
            # Agent 실행
            result = runner(
                params=step.params,
                state=ctx.state,
                dependencies=deps,
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Artifact 저장
            artifact_ids = []
            if result and isinstance(result, dict):
                artifact_id = persist_artifact(
                    kind=f"step_{step.id}",
                    content=result,
                )
                artifact_ids.append(artifact_id)
            
            emit_event(
                EventType.NODE_FINISHED,
                actor=actor,
                outputs={"step_id": step.id, "success": True},
                artifacts_out=artifact_ids,
                duration_ms=duration_ms,
            )
            
            return {"result": result, "artifacts": artifact_ids, "success": True}
            
        except AgentError as e:
            duration_ms = (time.time() - start_time) * 1000
            
            emit_event(
                EventType.NODE_FINISHED,
                actor=actor,
                outputs={"step_id": step.id, "error": e.kind.value, "success": False},
                duration_ms=duration_ms,
            )
            
            raise
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            emit_event(
                EventType.NODE_FINISHED,
                actor=actor,
                outputs={"step_id": step.id, "error": str(e), "success": False},
                duration_ms=duration_ms,
            )
            
            raise AgentError(str(e), kind=ErrorKind.UNKNOWN)


def _handle_error(
    step: PlanStep,
    error: AgentError,
    ctx: PlanExecutionContext,
    retry_count: int,
) -> ErrorAction:
    """에러 처리 및 다음 액션 결정."""
    # 스텝별 정책 우선, 없으면 전역 정책
    action = ERROR_POLICY.get(error.kind, step.on_error)
    
    emit_event(
        EventType.ERROR_OCCURRED,
        actor=f"node:{step.agent.value}",
        outputs={
            "step_id": step.id,
            "error_kind": error.kind.value,
            "action": action.value,
            "retry_count": retry_count,
        }
    )
    
    ctx.errors.append({
        "step_id": step.id,
        "error_kind": error.kind.value,
        "message": str(error),
        "action": action.value,
    })
    
    return action


def execute_plan(
    steps: List[PlanStep],
    ctx: PlanExecutionContext,
) -> Dict[str, Any]:
    """
    Plan 실행.
    
    위상 정렬된 스텝들을 레벨별로 실행.
    """
    if not steps:
        return {"results": {}, "artifacts": {}, "errors": [], "status": "empty"}
    
    with span("execute_plan", actor="supervisor"):
        levels = topological_sort(steps)
        
        emit_event(
            EventType.SUPERVISOR_ROUTE_SELECTED,
            outputs={
                "total_steps": len(steps),
                "levels": len(levels),
                "level_sizes": [len(level) for level in levels],
            }
        )
        
        for level_idx, level_steps in enumerate(levels):
            if ctx.aborted:
                break
            
            logger.info(f"Executing level {level_idx + 1}/{len(levels)} with {len(level_steps)} steps")
            
            for step in level_steps:
                if ctx.aborted:
                    break
                
                retry_count = 0
                success = False
                
                while retry_count <= MAX_RETRIES and not success and not ctx.aborted:
                    try:
                        result = _run_single_step(step, ctx)
                        ctx.results[step.id] = result
                        ctx.artifacts[step.id] = result.get("artifacts", [])
                        success = True
                        
                    except AgentError as e:
                        action = _handle_error(step, e, ctx, retry_count)
                        
                        if action == ErrorAction.RETRY:
                            retry_count += 1
                            if retry_count <= MAX_RETRIES:
                                wait_time = 0.5 * (BACKOFF_MULTIPLIER ** retry_count)
                                logger.info(f"Retrying step {step.id} in {wait_time}s")
                                time.sleep(wait_time)
                            continue
                        
                        elif action == ErrorAction.FALLBACK:
                            # 대체 파라미터 적용
                            fallback_params = e.suggested_fallback()
                            if fallback_params:
                                step.params.update(fallback_params)
                                retry_count += 1
                                continue
                            else:
                                # Fallback 없으면 빈 결과로 진행
                                ctx.results[step.id] = {"result": None, "fallback": True}
                                success = True
                        
                        elif action == ErrorAction.ASK_USER:
                            ctx.disambiguation_required = True
                            emit_event(
                                EventType.SUPERVISOR_ROUTE_SELECTED,
                                route="disambiguation"
                            )
                            # 중단하지 않고 빈 결과로 진행 (프론트 없이 이벤트만 기록)
                            ctx.results[step.id] = {"result": None, "ask_user": True}
                            success = True
                        
                        else:  # ABORT
                            ctx.aborted = True
                            break
        
        # 최종 상태 결정
        status = "completed"
        if ctx.aborted:
            status = "aborted"
        elif ctx.disambiguation_required:
            status = "disambiguation"
        elif ctx.errors:
            status = "partial"
        
        return {
            "results": ctx.results,
            "artifacts": ctx.artifacts,
            "errors": ctx.errors,
            "status": status,
        }


def collect_artifacts_for_recommendation(
    state: Dict[str, Any],
    results: Dict[str, Dict],
    required_kinds: List[str],
) -> List[Dict[str, str]]:
    """
    Recommendation용 Artifact 수집.
    
    state/results에서 required_kinds에 해당하는 artifact를 찾아서 반환.
    """
    from backend.common.events import get_artifact_store
    
    store = get_artifact_store()
    session_id = state.get("_session_id", "")
    collected = []
    
    # 1. ArtifactStore에서 kind로 조회
    if session_id:
        for kind in required_kinds:
            artifacts = store.get_by_kind(session_id, kind)
            for artifact in artifacts:
                collected.append({
                    "id": artifact.id,
                    "kind": artifact.kind,
                    "content": artifact.content,
                })
    
    # 2. results에서 step 결과로 저장된 artifact 조회
    for step_id, step_result in results.items():
        artifact_ids = step_result.get("artifacts", [])
        for aid in artifact_ids:
            artifact = store.get(aid)
            if artifact and artifact.kind in required_kinds:
                collected.append({
                    "id": artifact.id,
                    "kind": artifact.kind,
                    "content": artifact.content,
                })
    
    # 3. diagnosis_result에서 직접 추출 (fallback)
    diagnosis_result = state.get("diagnosis_result")
    if diagnosis_result and "diagnosis_raw" in required_kinds:
        collected.append({
            "id": "diagnosis_raw_inline",
            "kind": "diagnosis_raw",
            "content": diagnosis_result,
        })
    
    return collected


def build_recommendation_prompt(
    style: str,
    state: Dict[str, Any],
    artifacts: List[Dict],
) -> str:
    """Recommendation 프롬프트 빌드."""
    repo = state.get("repo") or {}
    repo_id = f"{repo.get('owner', '')}/{repo.get('name', '')}"
    user_context = state.get("user_context") or {}
    user_level = user_context.get("level", "beginner")
    user_query = state.get("user_query", "")
    
    # Artifact 내용 정리
    artifact_context = []
    for art in artifacts:
        content = art.get("content", {})
        if isinstance(content, dict):
            # 핵심 정보만 추출
            if art["kind"] == "diagnosis_raw":
                scores = content.get("scores", {})
                labels = content.get("labels", {})
                artifact_context.append(f"[진단 점수]\n{scores}\n[라벨]\n{labels}")
            elif art["kind"] == "onboarding_tasks":
                tasks = content.get("beginner", [])[:3]
                artifact_context.append(f"[온보딩 Task]\n{tasks}")
            else:
                artifact_context.append(f"[{art['kind']}]\n{content}")
    
    context_str = "\n\n".join(artifact_context) if artifact_context else "(수집된 데이터 없음)"
    
    level_kr = {"beginner": "초보자", "intermediate": "중급자", "advanced": "고급자"}.get(user_level, "초보자")
    
    style_prompts = {
        "explain": f"""당신은 수석 오픈소스 컨설턴트입니다.
저장소 {repo_id}에 대해 {level_kr} 수준으로 분석 결과를 해설해주세요.

[사용자 질문]
{user_query}

[수집된 데이터]
{context_str}

[지시사항]
1. 마크다운 리포트 형식으로 작성
2. 수치를 근거로 들 때 반드시 출처 명시
3. 어조는 전문적이지만 친절하게
4. 이모지 사용 금지""",
        
        "refine": f"""사용자가 요청한 조건에 맞게 Task를 재추천합니다.
저장소: {repo_id}
사용자 레벨: {level_kr}

[사용자 요청]
{user_query}

[수집된 Task 데이터]
{context_str}

[지시사항]
1. 조건에 맞는 Task 3-5개 선별
2. 각 Task에 선택 이유 한 줄 추가
3. 이모지 사용 금지""",
        
        "onepager": f"""저장소 {repo_id}에 대한 1페이지 요약을 생성합니다.

[수집된 데이터]
{context_str}

[지시사항]
1. 프로젝트 소개 (2-3문장)
2. 핵심 지표 (표 형식)
3. 기여 시작점 (bullet 3개)
4. 이모지 사용 금지""",
    }
    
    return style_prompts.get(style, style_prompts["explain"])


def create_default_agent_runners() -> Dict[AgentType, Callable]:
    """기본 Agent runner 생성."""
    from backend.agents.diagnosis.service import run_diagnosis
    from backend.agents.shared.contracts import ArtifactRef, ArtifactKind
    from backend.llm.contract_wrapper import generate_answer_with_contract
    
    def diagnosis_runner(params: Dict, state: Dict, dependencies: Dict) -> Dict:
        """Diagnosis Agent runner."""
        repo = state.get("repo") or {}
        payload = {
            "owner": repo.get("owner", ""),
            "repo": repo.get("name", ""),
            "task_type": params.get("task_type", "full"),
            "user_context": state.get("user_context", {}),
        }
        result = run_diagnosis(payload)
        
        # Artifact 저장
        persist_artifact(kind="diagnosis_raw", content=result)
        
        return result
    
    def recommendation_runner(params: Dict, state: Dict, dependencies: Dict) -> Dict:
        """Recommendation Agent runner - AnswerContract 기반 실구현."""
        style = params.get("style", "explain")
        
        # Plan에서 지정한 artifacts_required 또는 기본값
        required_kinds = params.get("artifacts_required", [
            "diagnosis_raw", "onboarding_tasks", "activity_metrics"
        ])
        
        # dependencies에서 이전 step 결과 수집
        results = {}
        for dep_id, dep_result in dependencies.items():
            if isinstance(dep_result, dict) and "result" in dep_result:
                results[dep_id] = dep_result
        
        # Artifact 수집
        artifacts = collect_artifacts_for_recommendation(state, results, required_kinds)
        
        if not artifacts:
            logger.warning("No artifacts collected for recommendation")
            return {
                "style": style,
                "answer_contract": None,
                "error": "No artifacts available"
            }
        
        # ArtifactRef 리스트 생성
        artifact_refs = [
            ArtifactRef(
                id=art["id"],
                kind=ArtifactKind(art["kind"]) if art["kind"] in [e.value for e in ArtifactKind] else ArtifactKind.SUMMARY,
                session_id=state.get("_session_id", "unknown"),
            )
            for art in artifacts
        ]
        
        # 프롬프트 생성
        prompt = build_recommendation_prompt(style, state, artifacts)
        
        try:
            # AnswerContract 강제 LLM 호출
            answer = generate_answer_with_contract(
                prompt=prompt,
                context_artifacts=artifact_refs,
                require_sources=True,
                max_tokens=4096,
                temperature=0.3,
            )
            
            return {
                "style": style,
                "answer_contract": answer.model_dump(),
                "sources": answer.sources,
            }
        except Exception as e:
            logger.error(f"Recommendation runner failed: {e}")
            return {
                "style": style,
                "answer_contract": None,
                "error": str(e)
            }
    
    def compare_runner(params: Dict, state: Dict, dependencies: Dict) -> Dict:
        """Compare Agent runner."""
        repos = params.get("repos", [])
        if len(repos) < 2:
            return {"error": "Need at least 2 repos to compare"}
        
        # 각 repo에 대해 diagnosis 실행
        results = []
        for repo_info in repos[:2]:
            payload = {
                "owner": repo_info.get("owner", ""),
                "repo": repo_info.get("name", ""),
                "task_type": "full",
            }
            result = run_diagnosis(payload)
            results.append(result)
        
        return {
            "repo_a": repos[0],
            "repo_b": repos[1],
            "diagnosis_a": results[0] if len(results) > 0 else None,
            "diagnosis_b": results[1] if len(results) > 1 else None,
        }
    
    def smalltalk_runner(params: Dict, state: Dict, dependencies: Dict) -> Dict:
        """
        Smalltalk runner - 인사/잡담 응답 (LLM 미사용, 즉시 응답).
        
        p95 < 100ms 목표로 템플릿 기반 응답 생성.
        """
        style = params.get("style", "greeting")
        
        if style == "greeting":
            text = (
                "안녕하세요! ODOC입니다. 무엇을 도와드릴까요?\n\n"
                "예시:\n"
                "- 레포 개요: 'facebook/react가 뭐야?'\n"
                "- 진단: 'react 상태 분석해줘'\n"
                "- 비교: 'react랑 vue 비교해줘'"
            )
        else:  # chitchat
            text = (
                "네, 계속 도와드릴게요! 다음 중 하나를 시도해보세요:\n\n"
                "- 레포 개요: 'vercel/next.js가 뭐야?'\n"
                "- 진단: 'tensorflow 분석해줘'\n"
                "- 온보딩: '이 프로젝트에 기여하고 싶어'"
            )
        
        return {
            "style": style,
            "answer_contract": {
                "text": text,
                "sources": ["SYS:TEMPLATES:SMALLTALK"],
                "source_kinds": ["system_template"],
            }
        }
    
    def help_runner(params: Dict, state: Dict, dependencies: Dict) -> Dict:
        """
        Help runner - 도움말 응답 (LLM 미사용, 즉시 응답).
        
        p95 < 100ms 목표로 템플릿 기반 기능 안내.
        """
        text = (
            "제가 할 수 있는 일:\n\n"
            "**레포 개요**\n"
            "'facebook/react가 뭐야?', 'vercel/next.js 알려줘'\n\n"
            "**진단 분석**\n"
            "'react 상태 분석해줘', 'tensorflow 진단해줘'\n\n"
            "**비교 분석**\n"
            "'react랑 vue 비교해줘', 'next.js vs nuxt.js'\n\n"
            "**온보딩 추천**\n"
            "'초보자인데 이 프로젝트에 기여하고 싶어'\n\n"
            "**발표용 요약**\n"
            "'한 장 요약 만들어줘'\n\n"
            "어떤 걸 해볼까요?"
        )
        
        return {
            "style": "help",
            "answer_contract": {
                "text": text,
                "sources": ["SYS:TEMPLATES:HELP"],
                "source_kinds": ["system_template"],
            }
        }
    
    return {
        AgentType.DIAGNOSIS: diagnosis_runner,
        AgentType.RECOMMENDATION: recommendation_runner,
        AgentType.COMPARE: compare_runner,
        AgentType.SMALLTALK: smalltalk_runner,
        AgentType.HELP: help_runner,
    }
