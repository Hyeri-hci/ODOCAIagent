"""
Onboarding Recommender LLM v1.2

규칙 기반 Task에 LLM을 활용해 자연어 추천 이유, 우선순위, 시나리오 생성.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Literal, Optional

from .onboarding_tasks import TaskSuggestion, OnboardingTasks, Difficulty
from backend.agents.diagnosis.config import DiagnosisMetrics, LLMTimer

logger = logging.getLogger(__name__)


# 출력 데이터 모델

@dataclass
class EnrichedTask:
    """LLM이 보강한 Task 정보."""
    
    task_id: str  # 원본 TaskSuggestion.id
    reason_text: str  # LLM이 생성한 자연어 추천 이유 (1-2문장)
    priority_rank: int  # 같은 난이도 내 우선순위 (1이 가장 높음)
    estimated_time: Optional[str] = None  # "30분", "1-2시간" 등
    prerequisites: List[str] = field(default_factory=list)  # 선행 요구사항
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OnboardingScenario:
    """LLM이 생성한 온보딩 시나리오."""
    
    title: str  # "첫 1주일 온보딩 로드맵"
    summary: str  # 전체 요약 (2-3문장)
    steps: List[Dict[str, str]] = field(default_factory=list)  # [{step, task_id, description}]
    tips: List[str] = field(default_factory=list)  # 추가 팁
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LLMEnrichedTasks:
    """LLM이 보강한 전체 결과."""
    
    enriched_tasks: Dict[str, EnrichedTask] = field(default_factory=dict)  # task_id -> EnrichedTask
    scenario: Optional[OnboardingScenario] = None
    top_3_tasks: List[str] = field(default_factory=list)  # 최우선 추천 3개 task_id
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "enriched_tasks": {k: v.to_dict() for k, v in self.enriched_tasks.items()},
            "scenario": self.scenario.to_dict() if self.scenario else None,
            "top_3_tasks": self.top_3_tasks,
        }


# ============================================================
# 프롬프트 템플릿
# ============================================================

# 프롬프트 버전 (변경 시 업데이트)
PROMPT_VERSION = "1.2.0"

TASK_ENRICHMENT_PROMPT = """당신은 오픈소스 기여 멘토입니다.
초보 기여자가 바로 시작할 수 있도록, 각 Task에 대해 친근하고 실용적인 추천 이유를 작성해주세요.

## 버전
- 프롬프트 버전: {prompt_version}

## 사용자 정보
- 경험 수준: {user_level}
- 목표: {user_goal}

## 프로젝트 상태
- 건강 상태: {health_level}
- 아카이브 여부: {is_archived}

## Task 목록 (규칙으로 이미 분류됨)
{tasks_json}

## 중요 정책

### Intent(목적) 해석 지침
- **contribute**: 실제 코드/문서 기여가 가능한 Task. 건강한 프로젝트에서만 적극 권장.
- **study**: 학습 목적의 Task. 비활성/아카이브 프로젝트에서 주로 활용.
- **evaluate**: 프로젝트 평가 목적. 아카이브 프로젝트나 대안 검토 시 활용.

### Task Score 해석 지침
- 80점 이상: 최근 활동이 활발하고 적정 난이도 → 최우선 추천
- 50-79점: 보통 수준 → 관심사에 따라 추천
- 50점 미만: 오래된 이슈이거나 복잡도 높음 → 신중하게 추천

### 비건강/아카이브 프로젝트 지침
{unhealthy_project_guidance}

## 작성 지침

1. 각 Task에 대해 한글로 1-2문장의 **추천 이유(reason_text)**를 작성하세요.
   - intent와 task_score를 고려하여 작성
   - reason_tags와 meta_flags를 참고
   - 왜 이 Task가 사용자에게 적합한지 설명
   - 친근하지만 전문적인 톤

2. 같은 난이도 내에서 **우선순위(priority_rank)**를 매기세요.
   - 1이 가장 우선 추천
   - task_score가 높은 Task 우선
   - 사용자 수준과 목표에 맞춰 결정

3. 가능하면 **예상 소요 시간(estimated_time)**도 추정하세요.
   - "30분", "1-2시간", "반나절" 등

## 제약 조건 (필수)
- **JSON 형식만 출력하세요. JSON 외의 텍스트는 절대 포함하지 마세요.**
- **task_id는 반드시 위 Task 목록에 있는 ID만 사용하세요.**
- **새로운 task_id를 만들지 마세요.**
- **top_3_tasks에는 위 Task 목록의 ID만 포함하세요.**

## 응답 형식 (JSON만 출력)
```json
{{
  "enriched_tasks": [
    {{
      "task_id": "issue#123",
      "reason_text": "이 이슈는 good-first-issue로 표시되어 있어 메인테이너가 초보자를 위해 준비해둔 것입니다.",
      "priority_rank": 1,
      "estimated_time": "1-2시간"
    }}
  ],
  "top_3_tasks": ["issue#123", "meta:create_contributing", "issue#456"]
}}
```
"""

# 비건강/아카이브 프로젝트용 LLM 가이던스
UNHEALTHY_PROJECT_GUIDANCE_TEMPLATE = """
이 프로젝트는 현재 **{status}** 상태입니다.
- 직접 기여(contribute)보다는 **학습(study)** 또는 **평가(evaluate)** 목적의 Task를 우선 추천하세요.
- 코드 리딩, 아키텍처 분석, 대안 프로젝트 검토 등을 강조하세요.
- "이 프로젝트에서 배울 수 있는 것"에 초점을 맞추세요.
- PR 제출보다는 개인 학습 결과물 정리를 권장하세요.
"""

HEALTHY_PROJECT_GUIDANCE = """
이 프로젝트는 **활발하게 유지보수**되고 있습니다.
- 기여(contribute) Task를 적극 추천하세요.
- 최근 이슈(task_score 높음)를 우선 추천하세요.
- 메인테이너와의 소통을 장려하세요.
"""

ONBOARDING_SCENARIO_PROMPT = """당신은 오픈소스 기여 멘토입니다.
선택된 Task들을 바탕으로 초보 기여자를 위한 **첫 1주일 온보딩 로드맵**을 작성해주세요.

## 버전
- 프롬프트 버전: {prompt_version}

## 사용자 정보
- 경험 수준: {user_level}
- 주당 가용 시간: {hours_per_week}시간
- 목표: {user_goal}

## 저장소 정보
- 저장소: {repo}
- 건강 상태: {health_level}
- 온보딩 난이도: {onboarding_level}

## 추천 Task 목록 (우선순위 순)
{top_tasks_json}

## 작성 지침

1. **summary**: 전체 온보딩 계획 요약 (2-3문장)

2. **steps**: 단계별 실행 계획
   - 각 단계에 구체적인 Task 연결
   - 예상 소요 시간과 결과물 명시
   - 최대 5단계까지

3. **tips**: 초보자를 위한 실용적인 팁 2-3개

## 제약 조건 (필수)
- **JSON 형식만 출력하세요. JSON 외의 텍스트는 절대 포함하지 마세요.**
- **task_id는 반드시 위 Task 목록에 있는 ID만 사용하세요. 없으면 null.**
- **steps 배열의 각 step에는 step, task_id, description 필드가 반드시 있어야 합니다.**

## 응답 형식 (JSON만 출력)
```json
{{
  "title": "첫 1주일 온보딩 로드맵",
  "summary": "이 프로젝트는 문서화가 필요한 상태입니다. 먼저 README 개선부터 시작해서...",
  "steps": [
    {{
      "step": "1단계: 환경 구축",
      "task_id": null,
      "description": "저장소를 fork하고 로컬에 클론합니다. (30분)"
    }},
    {{
      "step": "2단계: 첫 기여",
      "task_id": "meta:improve_readme_what",
      "description": "README의 프로젝트 소개 섹션을 보강합니다. (1시간)"
    }}
  ],
  "tips": [
    "PR을 올리기 전에 CONTRIBUTING.md를 꼭 읽어보세요.",
    "막히는 부분이 있으면 이슈에 질문을 남겨도 괜찮습니다."
  ]
}}
```
"""


# ============================================================
# LLM 호출 함수
# ============================================================

def enrich_tasks_with_llm(
    tasks: OnboardingTasks,
    user_level: str = "beginner",
    user_goal: str = "오픈소스 기여 시작",
    health_level: str = "good",
    is_archived: bool = False,
) -> LLMEnrichedTasks:
    """
    LLM을 사용해 Task에 자연어 추천 이유와 우선순위 추가.
    
    Args:
        tasks: 규칙 기반으로 생성된 OnboardingTasks
        user_level: 사용자 경험 수준 (beginner/intermediate/advanced)
        user_goal: 사용자의 목표
        health_level: 프로젝트 건강 상태 (good/warning/critical)
        is_archived: 아카이브된 프로젝트 여부
    
    Returns:
        LLMEnrichedTasks: LLM이 보강한 결과
    """
    metrics = DiagnosisMetrics()
    
    try:
        from backend.llm.factory import fetch_llm_client
        from backend.llm.base import ChatRequest, ChatMessage
        
        # Task 목록을 JSON으로 변환 (intent, task_score 포함)
        all_tasks = tasks.beginner + tasks.intermediate + tasks.advanced
        tasks_data = []
        for task in all_tasks[:15]:  # 최대 15개로 제한 (토큰 절약)
            tasks_data.append({
                "task_id": task.id,
                "title": task.title,
                "difficulty": task.difficulty,
                "level": task.level,
                "kind": task.kind,
                "intent": task.intent,
                "task_score": task.task_score,
                "reason_tags": task.reason_tags,
                "meta_flags": task.meta_flags,
                "labels": task.labels,
            })
        
        # 비건강/아카이브 프로젝트 가이던스 결정
        if is_archived:
            unhealthy_guidance = UNHEALTHY_PROJECT_GUIDANCE_TEMPLATE.format(
                status="아카이브됨 (더 이상 유지보수되지 않음)"
            )
        elif health_level == "critical":
            unhealthy_guidance = UNHEALTHY_PROJECT_GUIDANCE_TEMPLATE.format(
                status="심각한 건강 문제 (장기간 업데이트 없음)"
            )
        elif health_level == "warning":
            unhealthy_guidance = UNHEALTHY_PROJECT_GUIDANCE_TEMPLATE.format(
                status="주의 필요 (활동 저조)"
            )
        else:
            unhealthy_guidance = HEALTHY_PROJECT_GUIDANCE
        
        prompt = TASK_ENRICHMENT_PROMPT.format(
            prompt_version=PROMPT_VERSION,
            user_level=user_level,
            user_goal=user_goal,
            health_level=health_level,
            is_archived="예" if is_archived else "아니오",
            tasks_json=json.dumps(tasks_data, ensure_ascii=False, indent=2),
            unhealthy_project_guidance=unhealthy_guidance,
        )
        
        client = fetch_llm_client()
        request = ChatRequest(
            messages=[
                ChatMessage(
                    role="system",
                    content="당신은 오픈소스 기여 멘토입니다. JSON 형식으로만 응답하세요.",
                ),
                ChatMessage(role="user", content=prompt),
            ],
            temperature=0.7,
            max_tokens=2000,
        )
        
        # LLM 호출
        with LLMTimer(metrics) as timer:
            response = client.chat(request)
            result = _parse_enrichment_response(response.content, all_tasks)
            timer.mark_success()
        
        logger.info("LLM enrichment successful: %d tasks enriched", len(result.enriched_tasks))
        return result
    
    except Exception as e:
        # Fallback 사용 (메트릭은 LLMCallTimer에서 자동 기록)
        logger.warning("LLM enrichment failed, using fallback: %s", e)
        metrics.record_fallback(reason="enrichment_failure")
        return _create_fallback_enrichment(tasks)


def generate_onboarding_scenario(
    tasks: OnboardingTasks,
    enriched: LLMEnrichedTasks,
    repo: str,
    health_level: str = "good",
    onboarding_level: str = "normal",
    user_level: str = "beginner",
    user_goal: str = "오픈소스 기여 시작",
    hours_per_week: int = 5,
) -> OnboardingScenario:
    """
    LLM을 사용해 온보딩 시나리오(로드맵) 생성.
    
    Args:
        tasks: 규칙 기반 OnboardingTasks
        enriched: LLM이 보강한 결과
        repo: 저장소 이름 (owner/repo)
        health_level: 프로젝트 건강 상태
        onboarding_level: 온보딩 난이도
        user_level: 사용자 경험 수준
        user_goal: 사용자 목표
        hours_per_week: 주당 가용 시간
    
    Returns:
        OnboardingScenario: 단계별 온보딩 계획
    """
    metrics = DiagnosisMetrics()
    
    try:
        from backend.llm.factory import fetch_llm_client
        from backend.llm.base import ChatRequest, ChatMessage
        
        # Top 3 Task 정보 추출
        top_tasks_data = []
        all_tasks_map = {t.id: t for t in (tasks.beginner + tasks.intermediate + tasks.advanced)}
        
        for task_id in enriched.top_3_tasks[:5]:
            task = all_tasks_map.get(task_id)
            if task:
                enriched_info = enriched.enriched_tasks.get(task_id)
                top_tasks_data.append({
                    "task_id": task_id,
                    "title": task.title,
                    "difficulty": task.difficulty,
                    "reason_text": enriched_info.reason_text if enriched_info else task.fallback_reason,
                    "estimated_time": enriched_info.estimated_time if enriched_info else None,
                })
        
        prompt = ONBOARDING_SCENARIO_PROMPT.format(
            prompt_version=PROMPT_VERSION,
            user_level=user_level,
            hours_per_week=hours_per_week,
            user_goal=user_goal,
            repo=repo,
            health_level=health_level,
            onboarding_level=onboarding_level,
            top_tasks_json=json.dumps(top_tasks_data, ensure_ascii=False, indent=2),
        )
        
        client = fetch_llm_client()
        request = ChatRequest(
            messages=[
                ChatMessage(
                    role="system",
                    content="당신은 오픈소스 기여 멘토입니다. JSON 형식으로만 응답하세요.",
                ),
                ChatMessage(role="user", content=prompt),
            ],
            temperature=0.7,
            max_tokens=1500,
        )
        
        # LLM 호출
        with LLMTimer(metrics) as timer:
            response = client.chat(request)
            scenario = _parse_scenario_response(response.content)
            timer.mark_success()
        
        metrics.record_scenario(success=True)
        logger.info("LLM scenario generation successful")
        return scenario
    
    except Exception as e:
        logger.warning("LLM scenario generation failed, using fallback: %s", e)
        metrics.record_fallback(reason="scenario_failure")
        metrics.record_scenario(success=False)
        return _create_fallback_scenario(tasks, enriched, repo)


# ============================================================
# 응답 파싱 헬퍼
# ============================================================

def _parse_enrichment_response(
    response_text: str,
    all_tasks: List[TaskSuggestion],
) -> LLMEnrichedTasks:
    """LLM 응답에서 enrichment 정보 파싱."""
    result = LLMEnrichedTasks()
    
    try:
        # JSON 블록 추출
        json_text = _extract_json(response_text)
        data = json.loads(json_text)
        
        # enriched_tasks 파싱
        for item in data.get("enriched_tasks", []):
            task_id = item.get("task_id")
            if task_id:
                result.enriched_tasks[task_id] = EnrichedTask(
                    task_id=task_id,
                    reason_text=item.get("reason_text", ""),
                    priority_rank=item.get("priority_rank", 99),
                    estimated_time=item.get("estimated_time"),
                    prerequisites=item.get("prerequisites", []),
                )
        
        # top_3_tasks 파싱
        result.top_3_tasks = data.get("top_3_tasks", [])[:5]
        
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to parse LLM enrichment response: %s", e)
        # Fallback: 원본 Task의 fallback_reason 사용
        for task in all_tasks:
            result.enriched_tasks[task.id] = EnrichedTask(
                task_id=task.id,
                reason_text=task.fallback_reason or "",
                priority_rank=task.level,
            )
        result.top_3_tasks = [t.id for t in all_tasks[:3]]
    
    return result


def _parse_scenario_response(response_text: str) -> OnboardingScenario:
    """LLM 응답에서 시나리오 정보 파싱."""
    try:
        json_text = _extract_json(response_text)
        data = json.loads(json_text)
        
        return OnboardingScenario(
            title=data.get("title", "첫 1주일 온보딩 로드맵"),
            summary=data.get("summary", ""),
            steps=data.get("steps", []),
            tips=data.get("tips", []),
        )
    
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to parse LLM scenario response: %s", e)
        return OnboardingScenario(
            title="첫 1주일 온보딩 로드맵",
            summary="LLM 응답 파싱 실패로 기본 시나리오 제공",
            steps=[],
            tips=["저장소 README를 먼저 읽어보세요."],
        )


def _extract_json(text: str) -> str:
    """응답에서 JSON 블록 추출."""
    # ```json ... ``` 블록 추출
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end > start:
            return text[start:end].strip()
    
    # ``` ... ``` 블록 추출
    if "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        if end > start:
            return text[start:end].strip()
    
    # { ... } 추출
    if "{" in text:
        start = text.find("{")
        # 마지막 } 찾기
        end = text.rfind("}") + 1
        if end > start:
            return text[start:end]
    
    return text


# ============================================================
# Fallback 함수
# ============================================================

def _create_fallback_enrichment(tasks: OnboardingTasks) -> LLMEnrichedTasks:
    """LLM 실패 시 규칙 기반 Fallback 생성."""
    result = LLMEnrichedTasks()
    
    all_tasks = tasks.beginner + tasks.intermediate + tasks.advanced
    
    for i, task in enumerate(all_tasks):
        result.enriched_tasks[task.id] = EnrichedTask(
            task_id=task.id,
            reason_text=task.fallback_reason or f"{task.difficulty} 난이도의 기여 Task",
            priority_rank=task.level,
            estimated_time=_estimate_time_from_level(task.level),
        )
    
    # Top 3: beginner 우선
    result.top_3_tasks = [t.id for t in tasks.beginner[:3]] or [t.id for t in all_tasks[:3]]
    
    return result


def _create_fallback_scenario(
    tasks: OnboardingTasks,
    enriched: LLMEnrichedTasks,
    repo: str,
) -> OnboardingScenario:
    """LLM 실패 시 규칙 기반 시나리오 생성."""
    steps = [
        {
            "step": "1단계: 환경 구축",
            "task_id": None,
            "description": f"{repo} 저장소를 fork하고 로컬에 클론합니다. (30분)",
        },
        {
            "step": "2단계: 프로젝트 이해",
            "task_id": None,
            "description": "README와 CONTRIBUTING.md를 읽고 프로젝트 구조를 파악합니다. (1시간)",
        },
    ]
    
    # 추천 Task 추가
    for i, task_id in enumerate(enriched.top_3_tasks[:2], start=3):
        all_tasks = tasks.beginner + tasks.intermediate + tasks.advanced
        task = next((t for t in all_tasks if t.id == task_id), None)
        if task:
            steps.append({
                "step": f"{i}단계: {task.title}",
                "task_id": task_id,
                "description": task.fallback_reason or task.title,
            })
    
    return OnboardingScenario(
        title="첫 1주일 온보딩 로드맵",
        summary=f"{repo} 프로젝트에 첫 기여를 시작하기 위한 단계별 계획입니다.",
        steps=steps,
        tips=[
            "PR을 올리기 전에 CONTRIBUTING.md를 꼭 읽어보세요.",
            "막히는 부분이 있으면 이슈에 질문을 남겨도 괜찮습니다.",
            "작은 기여부터 시작해서 점진적으로 범위를 넓히세요.",
        ],
    )


def _estimate_time_from_level(level: int) -> str:
    """레벨에서 예상 소요 시간 추정."""
    time_map = {
        1: "30분-1시간",
        2: "1-2시간",
        3: "2-3시간",
        4: "반나절",
        5: "1일",
        6: "2-3일",
    }
    return time_map.get(level, "1-2시간")


# ============================================================
# 통합 함수
# ============================================================

def enrich_onboarding_tasks(
    tasks: OnboardingTasks,
    repo: str,
    health_level: str = "good",
    onboarding_level: str = "normal",
    user_level: str = "beginner",
    user_goal: str = "오픈소스 기여 시작",
    hours_per_week: int = 5,
    use_llm: bool = True,
    is_archived: bool = False,
) -> Dict[str, Any]:
    """
    온보딩 Task를 LLM으로 보강하고 시나리오 생성.
    
    Args:
        tasks: 규칙 기반 OnboardingTasks
        repo: 저장소 이름
        health_level: 프로젝트 건강 상태
        onboarding_level: 온보딩 난이도
        user_level: 사용자 경험 수준
        user_goal: 사용자 목표
        hours_per_week: 주당 가용 시간
        use_llm: LLM 사용 여부 (False면 Fallback 사용)
        is_archived: 아카이브된 프로젝트 여부
    
    Returns:
        Dict with enriched_tasks, scenario, top_3_tasks
    """
    if use_llm:
        enriched = enrich_tasks_with_llm(
            tasks, user_level, user_goal, health_level, is_archived
        )
        scenario = generate_onboarding_scenario(
            tasks, enriched, repo,
            health_level, onboarding_level,
            user_level, user_goal, hours_per_week,
        )
    else:
        enriched = _create_fallback_enrichment(tasks)
        scenario = _create_fallback_scenario(tasks, enriched, repo)
    
    enriched.scenario = scenario
    
    return enriched.to_dict()
