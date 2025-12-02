"""OnepagerRunner: Expert runner for generating one-page project summaries."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.agents.diagnosis.service import run_diagnosis
from backend.common.github_client import fetch_repo_overview, GitHubClientError
from backend.llm.base import ChatMessage, ChatRequest
from backend.llm.factory import fetch_llm_client
from backend.agents.shared.contracts import AnswerContract, safe_get

from .base import ExpertRunner, RunnerResult

logger = logging.getLogger(__name__)


ONEPAGER_SYSTEM_PROMPT = """당신은 GitHub 저장소를 한 페이지로 요약하는 전문가입니다.

## 역할
- 프로젝트 개요, 건강도, 시작 방법을 한 페이지에 요약
- 제공된 데이터만 사용 (추측 금지)
- 신규 기여자가 빠르게 이해할 수 있도록 작성

## 출력 형식

### {repo_name} 한 페이지 가이드

**프로젝트 소개**
[1-2문장: 프로젝트가 무엇인지]

**기술 스택**
- 주 언어: {language}
- (기타 주요 기술)

**건강도 요약**
| 지표 | 점수 | 평가 |
|------|------|------|
| ... | ... | ... |

**시작하기**
1. [첫 번째 단계]
2. [두 번째 단계]
3. [세 번째 단계]

**추천 첫 기여 Task**
- [Task 1]
- [Task 2]

**주의 사항**
- [있다면 리스크나 주의점]
"""


class OnepagerRunner(ExpertRunner):
    """Expert runner for generating one-page project summaries."""
    
    runner_name = "onepager"
    required_artifacts = ["repo_overview"]
    optional_artifacts = ["diagnosis", "readme"]
    max_retries = 1
    
    def __init__(
        self,
        repo_id: str,
        user_context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(repo_id, user_context)
        self._diagnosis_result: Optional[Dict[str, Any]] = None
    
    def _collect_artifacts(self) -> None:
        """Collects artifacts for onepager generation."""
        parts = self.repo_id.split("/")
        if len(parts) != 2:
            self.collector.add_error("repo_id", f"Invalid format: {self.repo_id}")
            return
        
        owner, repo = parts
        
        # Required: repo_overview
        try:
            overview = fetch_repo_overview(owner, repo)
            self.collector.add(
                kind="repo_overview",
                data=overview,
                required=True,
            )
            
            # Optional: readme (from overview)
            readme_content = overview.get("readme_content")
            if readme_content:
                self.collector.add(
                    kind="readme",
                    data=readme_content[:3000],  # Limit for prompt
                    required=False,
                )
        except GitHubClientError as e:
            self.collector.add_error("repo_overview", str(e))
        except Exception as e:
            logger.error(f"Unexpected error fetching repo overview: {e}")
            self.collector.add_error("repo_overview", str(e))
    
    def _execute(self) -> RunnerResult:
        """Executes onepager generation."""
        parts = self.repo_id.split("/")
        if len(parts) != 2:
            return RunnerResult.fail(f"Invalid repo_id format: {self.repo_id}")
        
        owner, repo = parts
        user_level = safe_get(self.user_context, "level", "beginner")
        
        # Run diagnosis
        try:
            payload = {
                "owner": owner,
                "repo": repo,
                "task_type": "full_diagnosis",
                "focus": ["documentation", "activity"],
                "user_context": {"level": user_level},
            }
            self._diagnosis_result = run_diagnosis(payload)
            if self._diagnosis_result:
                self.collector.add(
                    kind="diagnosis",
                    data=self._diagnosis_result,
                    required=False,
                )
        except Exception as e:
            logger.warning(f"Diagnosis for onepager failed: {e}")
        
        # Build onepager using LLM
        try:
            text = self._generate_onepager_llm()
        except Exception as e:
            logger.warning(f"LLM onepager failed, using template: {e}")
            text = self._build_template_onepager()
        
        answer = self._build_answer(text)
        
        return RunnerResult.ok(
            answer=answer,
            artifacts_out=self.collector.get_ids(),
            meta={"generated_by": "llm" if self._diagnosis_result else "template"},
        )
    
    def _fallback_execute(self) -> RunnerResult:
        """Fallback: generate onepager from overview only."""
        text = self._build_template_onepager()
        
        answer = AnswerContract(
            text=text,
            sources=self.collector.get_ids() or [f"FALLBACK:{self.repo_id}"],
            source_kinds=self.collector.get_kinds() or ["fallback"],
        )
        
        return RunnerResult.degraded_ok(
            answer=answer,
            artifacts_out=self.collector.get_ids(),
            reason="llm_failed_using_template",
        )
    
    def _generate_onepager_llm(self) -> str:
        """Generates onepager using LLM."""
        overview = self.collector.get("repo_overview") or {}
        readme = self.collector.get("readme") or ""
        diagnosis = self._diagnosis_result or {}
        
        # Build user prompt
        user_parts = [f"## 저장소: {self.repo_id}\n"]
        
        # Overview
        user_parts.append("### 기본 정보")
        user_parts.append(f"- 설명: {overview.get('description') or '(없음)'}")
        user_parts.append(f"- 언어: {overview.get('language') or '(없음)'}")
        user_parts.append(f"- Stars: {overview.get('stargazers_count', 0):,}")
        user_parts.append(f"- Forks: {overview.get('forks_count', 0):,}")
        user_parts.append(f"- License: {(overview.get('license') or {}).get('spdxId') or '(없음)'}")
        user_parts.append("")
        
        # Diagnosis scores
        if diagnosis:
            scores = diagnosis.get("scores", {})
            user_parts.append("### 건강도 점수")
            user_parts.append(f"- 건강 점수: {scores.get('health_score', 'N/A')}")
            user_parts.append(f"- 문서화 품질: {scores.get('documentation_quality', 'N/A')}")
            user_parts.append(f"- 활동성: {scores.get('activity_maintainability', 'N/A')}")
            user_parts.append(f"- 온보딩 용이성: {scores.get('onboarding_score', 'N/A')}")
            user_parts.append("")
            
            # Tasks
            tasks = diagnosis.get("onboarding_tasks", {})
            beginner_tasks = tasks.get("beginner", [])[:3]
            if beginner_tasks:
                user_parts.append("### 추천 Task")
                for task in beginner_tasks:
                    user_parts.append(f"- {task.get('title', '제목 없음')}")
                user_parts.append("")
        
        # README
        if readme:
            user_parts.append("### README (일부)")
            user_parts.append("```")
            user_parts.append(readme[:1500])
            user_parts.append("```")
        
        user_prompt = "\n".join(user_parts)
        
        # Call LLM
        client = fetch_llm_client()
        request = ChatRequest(
            messages=[
                ChatMessage(role="system", content=ONEPAGER_SYSTEM_PROMPT.format(
                    repo_name=self.repo_id,
                    language=overview.get("language") or "(없음)",
                )),
                ChatMessage(role="user", content=user_prompt),
            ],
            temperature=0.3,
            max_tokens=1200,
        )
        
        response = client.chat(request)
        return response.content
    
    def _build_template_onepager(self) -> str:
        """Builds onepager using template (no LLM)."""
        overview = self.collector.get("repo_overview") or {}
        diagnosis = self._diagnosis_result or {}
        
        description = overview.get("description") or "(설명 없음)"
        language = overview.get("language") or "(없음)"
        stars = overview.get("stargazers_count", 0)
        forks = overview.get("forks_count", 0)
        
        scores = diagnosis.get("scores", {})
        health = scores.get("health_score", "N/A")
        doc = scores.get("documentation_quality", "N/A")
        activity = scores.get("activity_maintainability", "N/A")
        onboarding = scores.get("onboarding_score", "N/A")
        
        tasks = diagnosis.get("onboarding_tasks", {})
        beginner_tasks = tasks.get("beginner", [])[:3]
        task_lines = []
        for task in beginner_tasks:
            task_lines.append(f"- {task.get('title', '제목 없음')}")
        tasks_text = "\n".join(task_lines) if task_lines else "- (Task 정보 없음)"
        
        text = f"""### {self.repo_id} 한 페이지 가이드

**프로젝트 소개**
{description}

**기술 스택**
- 주 언어: {language}
- Stars: {stars:,} | Forks: {forks:,}

**건강도 요약**
| 지표 | 점수 |
|------|------|
| 건강 점수 | {health} |
| 문서화 품질 | {doc} |
| 활동성 | {activity} |
| 온보딩 용이성 | {onboarding} |

**추천 첫 기여 Task**
{tasks_text}

**다음 행동**
- `{self.repo_id} 분석해줘`: 상세 분석 보기
- `점수 설명해줘`: 각 점수의 근거 확인"""
        
        return text
