"""CompareRunner: Expert runner for comparing two repositories."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from backend.agents.diagnosis.service import run_diagnosis
from backend.common.github_client import fetch_repo_overview, GitHubClientError
from backend.agents.shared.contracts import AnswerContract, safe_get

from .base import ExpertRunner, RunnerResult, FailedRepo, FailureReason

logger = logging.getLogger(__name__)


# Standardized failure reason messages (Korean)
FAILURE_REASON_MESSAGES: Dict[FailureReason, str] = {
    "not_found": "레포지토리가 존재하지 않습니다",
    "forbidden": "접근 권한이 없습니다",
    "rate_limit": "API 제한에 도달했습니다",
    "timeout": "응답 지연(타임아웃)입니다",
    "unknown": "알 수 없는 오류입니다",
}


def _normalize_error_reason(error: Exception, http_status: Optional[int] = None) -> Tuple[FailureReason, int, str]:
    """Normalizes exception to standard failure reason code."""
    error_str = str(error).lower()
    detail = str(error)
    
    # Extract HTTP status from GitHubClientError if available
    status = http_status or 0
    if hasattr(error, "status_code"):
        status = error.status_code
    elif "404" in error_str:
        status = 404
    elif "403" in error_str:
        status = 403
    elif "429" in error_str:
        status = 429
    
    # Map to standard reason codes (check various formats)
    if status == 404 or "not found" in error_str or "not_found" in error_str:
        return "not_found", status or 404, detail
    elif status == 403 or "forbidden" in error_str or "access" in error_str:
        return "forbidden", status or 403, detail
    elif status == 429 or "rate" in error_str or "limit" in error_str:
        return "rate_limit", status or 429, detail
    elif "timeout" in error_str or "timed out" in error_str:
        return "timeout", status or 408, detail
    else:
        return "unknown", status or 500, detail


class CompareRunner(ExpertRunner):
    """Expert runner for comparing two repositories."""
    
    runner_name = "compare"
    required_artifacts = ["repo_a_overview", "repo_b_overview"]
    optional_artifacts = ["repo_a_diagnosis", "repo_b_diagnosis"]
    max_retries = 1
    
    def __init__(
        self,
        repo_a: str,
        repo_b: str,
        user_context: Optional[Dict[str, Any]] = None,
    ):
        repo_id = f"{repo_a}_vs_{repo_b}"
        super().__init__(repo_id, user_context)
        self.repo_a = repo_a
        self.repo_b = repo_b
        self._diagnosis_a: Optional[Dict[str, Any]] = None
        self._diagnosis_b: Optional[Dict[str, Any]] = None
        # Structured error info
        self._failed_repo_a: Optional[FailedRepo] = None
        self._failed_repo_b: Optional[FailedRepo] = None
    
    def _collect_artifacts(self) -> None:
        """Collects artifacts for both repositories."""
        self._repo_a_error = None
        self._repo_b_error = None
        
        # Repo A
        owner_a, repo_a = self._parse_repo(self.repo_a)
        if owner_a and repo_a:
            try:
                overview_a = fetch_repo_overview(owner_a, repo_a)
                self.collector.add(
                    kind="repo_a_overview",
                    data=overview_a,
                    artifact_id=f"ARTIFACT:OVERVIEW:{self.repo_a}",
                    required=True,
                )
            except GitHubClientError as e:
                self._repo_a_error = str(e)
                reason, status, detail = _normalize_error_reason(e)
                self._failed_repo_a = FailedRepo(
                    owner=owner_a, repo=repo_a, reason=reason,
                    http_status=status, detail=detail
                )
                self.collector.add_error("repo_a_overview", str(e))
        else:
            self._repo_a_error = f"Invalid format: {self.repo_a}"
            owner_a, repo_a = self.repo_a.split("/") if "/" in self.repo_a else (self.repo_a, "")
            self._failed_repo_a = FailedRepo(
                owner=owner_a, repo=repo_a, reason="unknown",
                http_status=400, detail=self._repo_a_error
            )
            self.collector.add_error("repo_a_overview", self._repo_a_error)
        
        # Repo B
        owner_b, repo_b = self._parse_repo(self.repo_b)
        if owner_b and repo_b:
            try:
                overview_b = fetch_repo_overview(owner_b, repo_b)
                self.collector.add(
                    kind="repo_b_overview",
                    data=overview_b,
                    artifact_id=f"ARTIFACT:OVERVIEW:{self.repo_b}",
                    required=True,
                )
            except GitHubClientError as e:
                self._repo_b_error = str(e)
                reason, status, detail = _normalize_error_reason(e)
                self._failed_repo_b = FailedRepo(
                    owner=owner_b, repo=repo_b, reason=reason,
                    http_status=status, detail=detail
                )
                self.collector.add_error("repo_b_overview", str(e))
        else:
            self._repo_b_error = f"Invalid format: {self.repo_b}"
            owner_b, repo_b = self.repo_b.split("/") if "/" in self.repo_b else (self.repo_b, "")
            self._failed_repo_b = FailedRepo(
                owner=owner_b, repo=repo_b, reason="unknown",
                http_status=400, detail=self._repo_b_error
            )
            self.collector.add_error("repo_b_overview", self._repo_b_error)
    
    def _parse_repo(self, repo_id: str) -> Tuple[Optional[str], Optional[str]]:
        """Parses owner/repo format."""
        parts = repo_id.split("/")
        if len(parts) == 2:
            return parts[0], parts[1]
        return None, None
    
    def _execute(self) -> RunnerResult:
        """Executes comparison between two repositories."""
        # Run diagnosis for both repos
        owner_a, repo_a = self._parse_repo(self.repo_a)
        owner_b, repo_b = self._parse_repo(self.repo_b)
        
        if not all([owner_a, repo_a, owner_b, repo_b]):
            return RunnerResult.fail("Invalid repository format")
        
        user_level = safe_get(self.user_context, "level", "beginner")
        
        # Diagnosis A
        try:
            payload_a = {
                "owner": owner_a,
                "repo": repo_a,
                "task_type": "full_diagnosis",
                "focus": ["documentation", "activity"],
                "user_context": {"level": user_level},
            }
            self._diagnosis_a = run_diagnosis(payload_a)
            if self._diagnosis_a:
                self.collector.add(
                    kind="repo_a_diagnosis",
                    data=self._diagnosis_a,
                    artifact_id=f"ARTIFACT:DIAGNOSIS:{self.repo_a}",
                    required=False,
                )
        except Exception as e:
            logger.warning(f"Diagnosis A failed: {e}")
            self._diagnosis_a = None
        
        # Diagnosis B
        try:
            payload_b = {
                "owner": owner_b,
                "repo": repo_b,
                "task_type": "full_diagnosis",
                "focus": ["documentation", "activity"],
                "user_context": {"level": user_level},
            }
            self._diagnosis_b = run_diagnosis(payload_b)
            if self._diagnosis_b:
                self.collector.add(
                    kind="repo_b_diagnosis",
                    data=self._diagnosis_b,
                    artifact_id=f"ARTIFACT:DIAGNOSIS:{self.repo_b}",
                    required=False,
                )
        except Exception as e:
            logger.warning(f"Diagnosis B failed: {e}")
            self._diagnosis_b = None
        
        # Check for partial failures - if one diagnosis failed, use fallback
        overview_a = self.collector.get("repo_a_overview")
        overview_b = self.collector.get("repo_b_overview")
        
        # If either repo has no overview (not just diagnosis failure), use fallback
        if not overview_a or not overview_b:
            logger.info(f"[compare] Partial failure detected: A={bool(overview_a)}, B={bool(overview_b)}")
            return self._fallback_execute()
        
        # Both overviews available - build full comparison
        text = self._build_comparison_text()
        answer = self._build_answer(text)
        
        return RunnerResult.ok(
            answer=answer,
            artifacts_out=self.collector.get_ids(),
            meta={
                "repo_a": self.repo_a,
                "repo_b": self.repo_b,
            },
        )
    
    def _fallback_execute(self) -> RunnerResult:
        """Fallback: handle partial failures - single repo analysis or overview only."""
        overview_a = self.collector.get("repo_a_overview")
        overview_b = self.collector.get("repo_b_overview")
        
        # Both failed
        if not overview_a and not overview_b:
            failed_repos = []
            if self._failed_repo_a:
                failed_repos.append(self._failed_repo_a)
            if self._failed_repo_b:
                failed_repos.append(self._failed_repo_b)
            
            error_msg = "두 저장소 모두 접근할 수 없습니다."
            if self._repo_a_error:
                error_msg += f"\n- {self.repo_a}: {self._repo_a_error}"
            if self._repo_b_error:
                error_msg += f"\n- {self.repo_b}: {self._repo_b_error}"
            return RunnerResult.fail(error_msg)
        
        # One repo failed - return partial success with structured failure info
        if overview_a and not overview_b:
            text = self._build_partial_comparison(
                success_repo=self.repo_a,
                success_overview=overview_a,
                failed_repo=self.repo_b,
                failed_info=self._failed_repo_b,
            )
            answer = AnswerContract(
                text=text,
                sources=self.collector.get_ids() or [f"ARTIFACT:OVERVIEW:{self.repo_a}"],
                source_kinds=["partial_compare"],
            )
            return RunnerResult.partial_ok(
                answer=answer,
                artifacts_out=self.collector.get_ids(),
                failed_repos=[self._failed_repo_b] if self._failed_repo_b else [],
                reason=f"repo_b_failed:{self._repo_b_error}",
            )
        
        if overview_b and not overview_a:
            text = self._build_partial_comparison(
                success_repo=self.repo_b,
                success_overview=overview_b,
                failed_repo=self.repo_a,
                failed_info=self._failed_repo_a,
            )
            answer = AnswerContract(
                text=text,
                sources=self.collector.get_ids() or [f"ARTIFACT:OVERVIEW:{self.repo_b}"],
                source_kinds=["partial_compare"],
            )
            return RunnerResult.partial_ok(
                answer=answer,
                artifacts_out=self.collector.get_ids(),
                failed_repos=[self._failed_repo_a] if self._failed_repo_a else [],
                reason=f"repo_a_failed:{self._repo_a_error}",
            )
        
        # Both available but diagnosis failed - use overview comparison
        text = self._build_overview_comparison(overview_a, overview_b)
        
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
    
    def _build_partial_comparison(
        self,
        success_repo: str,
        success_overview: Dict,
        failed_repo: str,
        failed_info: Optional[FailedRepo],
    ) -> str:
        """Builds text when one repo is not accessible with structured warning."""
        stars = success_overview.get("stargazers_count", 0)
        forks = success_overview.get("forks_count", 0)
        desc = success_overview.get("description", "설명 없음")
        
        # Build standardized failure reason message
        if failed_info:
            reason_msg = FAILURE_REASON_MESSAGES.get(failed_info.reason, "알 수 없는 오류입니다.")
            http_code = failed_info.http_status
            warning_block = f"**※ 불완전 비교**: `{failed_repo}` 처리 중 {reason_msg}(HTTP {http_code}). 성공한 `{success_repo}` 기준으로 요약을 제공합니다."
        else:
            warning_block = f"**※ 불완전 비교**: `{failed_repo}` 저장소에 접근할 수 없습니다. 성공한 `{success_repo}` 기준으로 요약을 제공합니다."
        
        # Build next actions based on failure reason
        next_actions = self._build_next_actions(failed_repo, success_repo, failed_info)
        
        text = f"""{warning_block}

### {success_repo} 단일 정보

비교 대상인 **{failed_repo}**에 접근 불가하여 **{success_repo}**의 정보만 제공합니다.

| 지표 | 값 |
|------|-----|
| 설명 | {desc[:100]} |
| Stars | {stars:,} |
| Forks | {forks:,} |

**다음 행동**
{next_actions}"""
        
        return text
    
    def _build_next_actions(
        self,
        failed_repo: str,
        success_repo: str,
        failed_info: Optional[FailedRepo],
    ) -> str:
        """Builds context-aware next action suggestions."""
        actions = []
        
        if failed_info:
            if failed_info.reason == "not_found":
                actions.append(f"1. `{failed_repo}` 저장소 이름/오타를 확인해 주세요")
                actions.append(f"2. 올바른 저장소명으로 다시 비교해 보세요")
            elif failed_info.reason == "forbidden":
                actions.append("1. GitHub 토큰에 해당 저장소 접근 권한이 있는지 확인해 주세요")
                actions.append("2. 비공개 저장소라면 Personal Access Token에 `repo` 스코프가 필요합니다")
                actions.append(f"3. 공개 대체 저장소를 찾아 비교해 보세요")
            elif failed_info.reason == "rate_limit":
                actions.append("1. GitHub API 제한에 도달했습니다. 잠시 후 다시 시도해 주세요")
                actions.append("2. 인증된 토큰을 사용하면 제한이 완화됩니다")
            elif failed_info.reason == "timeout":
                actions.append("1. 네트워크 상태를 확인해 주세요")
                actions.append("2. 잠시 후 다시 시도해 주세요")
            else:
                actions.append(f"1. `{failed_repo}` 저장소 상태를 확인해 주세요")
        else:
            actions.append(f"1. `{failed_repo}` 저장소 이름이 올바른지 확인해 주세요")
        
        actions.append(f"- `{success_repo} 분석해줘`로 단일 저장소 분석을 받아보세요")
        
        return "\n".join(actions)
    
    def _build_comparison_text(self) -> str:
        """Builds full comparison text with diagnosis data."""
        scores_a = self._diagnosis_a.get("scores", {}) if self._diagnosis_a else {}
        scores_b = self._diagnosis_b.get("scores", {}) if self._diagnosis_b else {}
        
        overview_a = self.collector.get("repo_a_overview") or {}
        overview_b = self.collector.get("repo_b_overview") or {}
        
        health_a = scores_a.get("health_score", "N/A")
        health_b = scores_b.get("health_score", "N/A")
        doc_a = scores_a.get("documentation_quality", "N/A")
        doc_b = scores_b.get("documentation_quality", "N/A")
        activity_a = scores_a.get("activity_maintainability", "N/A")
        activity_b = scores_b.get("activity_maintainability", "N/A")
        onboarding_a = scores_a.get("onboarding_score", "N/A")
        onboarding_b = scores_b.get("onboarding_score", "N/A")
        
        stars_a = overview_a.get("stargazers_count", 0)
        stars_b = overview_b.get("stargazers_count", 0)
        
        # Determine winner
        winner = self._determine_winner(scores_a, scores_b)
        
        text = f"""### {self.repo_a} vs {self.repo_b} 비교

**결론**: {winner}

| 지표 | {self.repo_a} | {self.repo_b} | 우위 |
|------|-------------|-------------|------|
| 건강 점수 | {health_a} | {health_b} | {self._compare_emoji(health_a, health_b)} |
| 문서화 품질 | {doc_a} | {doc_b} | {self._compare_emoji(doc_a, doc_b)} |
| 활동성 | {activity_a} | {activity_b} | {self._compare_emoji(activity_a, activity_b)} |
| 온보딩 용이성 | {onboarding_a} | {onboarding_b} | {self._compare_emoji(onboarding_a, onboarding_b)} |
| Stars | {stars_a:,} | {stars_b:,} | {self._compare_emoji(stars_a, stars_b)} |

**다음 행동**
- `{self.repo_a} 자세히 분석해줘`: A 저장소 상세 분석
- `{self.repo_b} 자세히 분석해줘`: B 저장소 상세 분석"""
        
        return text
    
    def _build_overview_comparison(
        self,
        overview_a: Optional[Dict],
        overview_b: Optional[Dict],
    ) -> str:
        """Builds comparison using only overview data."""
        def get_val(o: Optional[Dict], key: str, default: Any = "N/A") -> Any:
            return o.get(key, default) if o else default
        
        stars_a = get_val(overview_a, "stargazers_count", 0)
        stars_b = get_val(overview_b, "stargazers_count", 0)
        forks_a = get_val(overview_a, "forks_count", 0)
        forks_b = get_val(overview_b, "forks_count", 0)
        issues_a = get_val(overview_a, "open_issues_count", 0)
        issues_b = get_val(overview_b, "open_issues_count", 0)
        
        text = f"""### {self.repo_a} vs {self.repo_b} 기본 비교

(상세 진단을 수행하지 못해 기본 정보만 비교합니다)

| 지표 | {self.repo_a} | {self.repo_b} |
|------|-------------|-------------|
| Stars | {stars_a:,} | {stars_b:,} |
| Forks | {forks_a:,} | {forks_b:,} |
| Open Issues | {issues_a:,} | {issues_b:,} |

**다음 행동**
- 잠시 후 다시 시도해 상세 비교를 받아보세요"""
        
        return text
    
    def _determine_winner(
        self,
        scores_a: Dict[str, Any],
        scores_b: Dict[str, Any],
    ) -> str:
        """Determines overall winner based on health scores."""
        try:
            health_a = int(scores_a.get("health_score", 0))
            health_b = int(scores_b.get("health_score", 0))
            
            if health_a > health_b + 5:
                return f"**{self.repo_a}**가 전반적으로 더 건강한 프로젝트입니다."
            elif health_b > health_a + 5:
                return f"**{self.repo_b}**가 전반적으로 더 건강한 프로젝트입니다."
            else:
                return "두 프로젝트가 비슷한 수준입니다. 세부 지표를 확인하세요."
        except (ValueError, TypeError):
            return "점수 비교가 어렵습니다. 세부 정보를 확인하세요."
    
    def _compare_emoji(self, val_a: Any, val_b: Any) -> str:
        """Returns comparison indicator."""
        try:
            a = int(val_a) if val_a != "N/A" else 0
            b = int(val_b) if val_b != "N/A" else 0
            
            if a > b:
                return "A"
            elif b > a:
                return "B"
            else:
                return "-"
        except (ValueError, TypeError):
            return "-"
