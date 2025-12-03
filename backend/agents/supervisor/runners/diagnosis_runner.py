"""DiagnosisRunner: Expert runner for repository health diagnosis."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.agents.diagnosis.service import run_diagnosis
from backend.common.github_client import (
    fetch_repo_overview,
    GitHubClientError,
)
from backend.agents.shared.contracts import (
    AnswerContract,
    safe_get,
    safe_get_nested,
)

from .base import ExpertRunner, RunnerResult, ArtifactCollector

logger = logging.getLogger(__name__)


class DiagnosisRunner(ExpertRunner):
    """Expert runner for full repository diagnosis."""
    
    runner_name = "diagnosis"
    required_artifacts = ["repo_overview"]
    optional_artifacts = ["readme", "activity", "community_profile"]
    max_retries = 1
    
    def __init__(
        self,
        repo_id: str,
        user_context: Optional[Dict[str, Any]] = None,
        task_type: str = "full_diagnosis",
        focus: Optional[List[str]] = None,
        intent: Optional[str] = None,
        sub_intent: Optional[str] = None,
    ):
        super().__init__(repo_id, user_context)
        self.task_type = task_type
        self.focus = focus or ["documentation", "activity"]
        self.intent = intent
        self.sub_intent = sub_intent
        self._diagnosis_result: Optional[Dict[str, Any]] = None
    
    def _build_needs(self) -> Dict[str, bool]:
        """intent 기반 needs 생성 (비용 최적화)."""
        # 기본값: 모두 True
        needs = {
            "need_health": True,
            "need_readme": True,
            "need_activity": True,
            "need_onboarding": True,
        }
        
        # intent가 health/overview면 onboarding 최소화
        if self.sub_intent in ("health", "overview"):
            needs["need_onboarding"] = False
        
        # activity_only면 readme 분석 최소화
        if self.task_type == "activity_only":
            needs["need_readme"] = False
        
        # docs_only면 activity 분석 최소화
        if self.task_type == "docs_only":
            needs["need_activity"] = False
        
        return needs
    
    def _collect_artifacts(self) -> None:
        """Collects artifacts for diagnosis."""
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
        except GitHubClientError as e:
            self.collector.add_error("repo_overview", str(e))
        except Exception as e:
            logger.error(f"Unexpected error fetching repo overview: {e}")
            self.collector.add_error("repo_overview", str(e))
    
    def _execute(self) -> RunnerResult:
        """Executes diagnosis and builds response."""
        parts = self.repo_id.split("/")
        if len(parts) != 2:
            return RunnerResult.fail(f"Invalid repo_id format: {self.repo_id}")
        
        owner, repo = parts
        user_level = safe_get(self.user_context, "level", "beginner")
        
        # Build diagnosis payload
        payload = {
            "owner": owner,
            "repo": repo,
            "task_type": self.task_type,
            "focus": self.focus,
            "user_context": {"level": user_level},
            "needs": self._build_needs(),  # intent 기반 비용 최적화
            "advanced_analysis": False,
        }
        
        try:
            result = run_diagnosis(payload)
            self._diagnosis_result = result
            
            # Add diagnosis artifacts
            if result:
                if result.get("scores"):
                    self.collector.add(
                        kind="diagnosis_scores",
                        data=result["scores"],
                    )
                if result.get("labels"):
                    self.collector.add(
                        kind="diagnosis_labels",
                        data=result["labels"],
                    )
                if result.get("onboarding_tasks"):
                    self.collector.add(
                        kind="onboarding_tasks",
                        data=result["onboarding_tasks"],
                    )
                if result.get("explain_context"):
                    self.collector.add(
                        kind="explain_context",
                        data=result["explain_context"],
                    )
            
            # Build response text
            text = self._build_diagnosis_summary(result)
            
            answer = self._build_answer(text)
            
            return RunnerResult.ok(
                answer=answer,
                artifacts_out=self.collector.get_ids(),
                meta={"diagnosis_scores": result.get("scores", {})},
            )
            
        except Exception as e:
            logger.error(f"Diagnosis execution failed: {e}")
            return RunnerResult.fail(str(e))
    
    def _fallback_execute(self) -> RunnerResult:
        """Fallback: return basic repo info from overview."""
        overview = self.collector.get("repo_overview")
        if not overview:
            return RunnerResult.fail("No repo overview available for fallback")
        
        text = self._build_fallback_summary(overview)
        
        answer = AnswerContract(
            text=text,
            sources=self.collector.get_ids() or [f"FALLBACK:{self.repo_id}"],
            source_kinds=self.collector.get_kinds() or ["fallback"],
        )
        
        return RunnerResult.degraded_ok(
            answer=answer,
            artifacts_out=self.collector.get_ids(),
            reason="diagnosis_failed_using_overview",
        )
    
    def _build_diagnosis_summary(self, result: Dict[str, Any]) -> str:
        """Builds diagnosis summary text."""
        scores = result.get("scores", {})
        labels = result.get("labels", {})
        tasks = result.get("onboarding_tasks", {})
        
        health_score = scores.get("health_score", "N/A")
        doc_quality = scores.get("documentation_quality", "N/A")
        activity = scores.get("activity_maintainability", "N/A")
        onboarding = scores.get("onboarding_score", "N/A")
        
        health_level = labels.get("health_level", "unknown")
        onboarding_level = labels.get("onboarding_level", "unknown")
        
        # Format tasks
        beginner_tasks = tasks.get("beginner", [])[:3]
        task_lines = []
        for i, task in enumerate(beginner_tasks, 1):
            title = task.get("title", "제목 없음")
            task_lines.append(f"{i}. {title}")
        tasks_text = "\n".join(task_lines) if task_lines else "(Task 없음)"
        
        text = f"""### {self.repo_id} 분석 결과

**한 줄 요약**: {health_level} 상태의 프로젝트입니다.

| 지표 | 점수 | 상태 |
|------|------|------|
| 건강 점수 | {health_score} | {self._score_emoji(health_score)} |
| 문서화 품질 | {doc_quality} | {self._score_emoji(doc_quality)} |
| 활동성 | {activity} | {self._score_emoji(activity)} |
| 온보딩 용이성 | {onboarding} | {self._score_emoji(onboarding)} |

**온보딩 난이도**: {onboarding_level}

**추천 시작 Task**
{tasks_text}

**다음 행동**
- `점수 설명해줘`: 각 점수의 근거 확인
- `기여하고 싶어`: 더 많은 Task 추천"""
        
        return text
    
    def _build_fallback_summary(self, overview: Dict[str, Any]) -> str:
        """Builds fallback summary from repo overview."""
        full_name = overview.get("full_name", self.repo_id)
        description = overview.get("description") or "(설명 없음)"
        stars = overview.get("stargazers_count", 0)
        forks = overview.get("forks_count", 0)
        language = overview.get("language") or "(없음)"
        
        text = f"""### {full_name}

{description}

| 항목 | 값 |
|------|-----|
| 언어 | {language} |
| Stars | {stars:,} |
| Forks | {forks:,} |

상세 분석을 수행하지 못했습니다. 잠시 후 다시 시도해 주세요.

**다음 행동**
- `{full_name} 분석해줘`: 다시 분석 시도
- 다른 저장소로 시도해 보세요"""
        
        return text
    
    def _score_emoji(self, score: Any) -> str:
        """Returns status text based on score."""
        try:
            s = int(score)
            if s >= 80:
                return "우수"
            elif s >= 60:
                return "양호"
            elif s >= 40:
                return "보통"
            else:
                return "개선 필요"
        except (ValueError, TypeError):
            return "-"
    
    def get_diagnosis_result(self) -> Optional[Dict[str, Any]]:
        """Returns the raw diagnosis result for further processing."""
        return self._diagnosis_result
