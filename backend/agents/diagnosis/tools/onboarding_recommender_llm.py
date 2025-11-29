"""
Onboarding Recommender LLM v1.0

규칙 기반 Task에 LLM을 활용해 자연어 추천 이유, 우선순위, 온보딩 시나리오 생성.

설계 원칙:
- 규칙 기반(Tool): difficulty/level/kind/reason_tags는 이미 계산됨
- LLM 기반(Agent): 자연어 추천 이유, 우선순위 조정, 온보딩 스토리 생성
- Fallback: LLM 실패 시 fallback_reason 사용

Related: onboarding_tasks.py (규칙 기반 Tool)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Literal, Optional

from .onboarding_tasks import TaskSuggestion, OnboardingTasks, Difficulty

logger = logging.getLogger(__name__)


# ============================================================
# 출력 데이터 모델
# ============================================================

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

TASK_ENRICHMENT_PROMPT = """당신은 오픈소스 기여 멘토입니다.
초보 기여자가 바로 시작할 수 있도록, 각 Task에 대해 친근하고 실용적인 추천 이유를 작성해주세요.

## 사용자 정보
- 경험 수준: {user_level}
- 목표: {user_goal}

## Task 목록 (규칙으로 이미 분류됨)
{tasks_json}

## 작성 지침

1. 각 Task에 대해 한글로 1-2문장의 **추천 이유(reason_text)**를 작성하세요.
   - reason_tags와 meta_flags를 참고하여 작성
   - 왜 이 Task가 사용자에게 적합한지 설명
   - 친근하지만 전문적인 톤

2. 같은 난이도 내에서 **우선순위(priority_rank)**를 매기세요.
   - 1이 가장 우선 추천
   - 사용자 수준과 목표에 맞춰 결정

3. 가능하면 **예상 소요 시간(estimated_time)**도 추정하세요.
   - "30분", "1-2시간", "반나절" 등

## 응답 형식 (JSON)
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

ONBOARDING_SCENARIO_PROMPT = """당신은 오픈소스 기여 멘토입니다.
선택된 Task들을 바탕으로 초보 기여자를 위한 **첫 1주일 온보딩 로드맵**을 작성해주세요.

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

## 응답 형식 (JSON)
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
) -> LLMEnrichedTasks:
    """
    LLM을 사용해 Task에 자연어 추천 이유와 우선순위 추가.
    
    Args:
        tasks: 규칙 기반으로 생성된 OnboardingTasks
        user_level: 사용자 경험 수준 (beginner/intermediate/advanced)
        user_goal: 사용자의 목표
    
    Returns:
        LLMEnrichedTasks: LLM이 보강한 결과
    """
    try:
        from backend.llm.factory import fetch_llm_client
        from backend.llm.base import ChatRequest, ChatMessage
        
        # Task 목록을 JSON으로 변환
        all_tasks = tasks.beginner + tasks.intermediate + tasks.advanced
        tasks_data = []
        for task in all_tasks[:15]:  # 최대 15개로 제한 (토큰 절약)
            tasks_data.append({
                "task_id": task.id,
                "title": task.title,
                "difficulty": task.difficulty,
                "level": task.level,
                "kind": task.kind,
                "reason_tags": task.reason_tags,
                "meta_flags": task.meta_flags,
                "labels": task.labels,
            })
        
        prompt = TASK_ENRICHMENT_PROMPT.format(
            user_level=user_level,
            user_goal=user_goal,
            tasks_json=json.dumps(tasks_data, ensure_ascii=False, indent=2),
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
        response = client.chat(request)
        
        # JSON 파싱
        result = _parse_enrichment_response(response.content, all_tasks)
        logger.info("LLM enrichment successful: %d tasks enriched", len(result.enriched_tasks))
        return result
    
    except Exception as e:
        logger.warning("LLM enrichment failed, using fallback: %s", e)
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
        response = client.chat(request)
        
        # JSON 파싱
        scenario = _parse_scenario_response(response.content)
        logger.info("LLM scenario generation successful")
        return scenario
    
    except Exception as e:
        logger.warning("LLM scenario generation failed, using fallback: %s", e)
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
    
    Returns:
        Dict with enriched_tasks, scenario, top_3_tasks
    """
    if use_llm:
        enriched = enrich_tasks_with_llm(tasks, user_level, user_goal)
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
