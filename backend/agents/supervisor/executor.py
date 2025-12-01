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
    """
    PlanStep들을 위상 정렬하여 실행 레벨별로 그룹화.
    
    같은 레벨의 스텝들은 병렬 실행 가능.
    
    Returns:
        List[List[PlanStep]]: 레벨별 스텝 그룹
    """
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
    같은 레벨은 병렬 실행 가능 (현재는 순차).
    
    Args:
        steps: 실행할 PlanStep 목록
        ctx: 실행 컨텍스트
    
    Returns:
        실행 결과 딕셔너리
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


def create_default_agent_runners() -> Dict[AgentType, Callable]:
    """기본 Agent runner 생성."""
    from backend.agents.diagnosis.service import run_diagnosis
    
    def diagnosis_runner(params: Dict, state: Dict, dependencies: Dict) -> Dict:
        """Diagnosis Agent runner."""
        repo = state.get("repo") or {}
        payload = {
            "owner": repo.get("owner", ""),
            "repo": repo.get("name", ""),
            "task_type": params.get("task_type", "full"),
            "user_context": state.get("user_context", {}),
        }
        return run_diagnosis(payload)
    
    def recommendation_runner(params: Dict, state: Dict, dependencies: Dict) -> Dict:
        """Recommendation Agent runner (placeholder)."""
        # TODO: 실제 구현
        return {"style": params.get("style", "explain")}
    
    def compare_runner(params: Dict, state: Dict, dependencies: Dict) -> Dict:
        """Compare Agent runner (placeholder)."""
        # TODO: 실제 구현
        return {"comparison": "placeholder"}
    
    return {
        AgentType.DIAGNOSIS: diagnosis_runner,
        AgentType.RECOMMENDATION: recommendation_runner,
        AgentType.COMPARE: compare_runner,
    }
