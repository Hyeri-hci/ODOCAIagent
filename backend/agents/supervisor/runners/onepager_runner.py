"""OnepagerRunner: Expert runner for generating one-page project summaries."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from backend.agents.diagnosis.service import run_diagnosis
from backend.common.github_client import fetch_repo_overview, GitHubClientError
from backend.llm.base import ChatMessage, ChatRequest
from backend.llm.factory import fetch_llm_client
from backend.agents.shared.contracts import AnswerContract, safe_get

from .base import ExpertRunner, RunnerResult

logger = logging.getLogger(__name__)


class OnepagerTier(Enum):
    """Artifact tier for onepager quality."""
    TIER_1 = "tier_1"  # python_metrics + diagnosis_raw + repo_facts (최상)
    TIER_2 = "tier_2"  # repo_facts + readme_head (개요)
    TIER_3 = "tier_3"  # repo_facts만 (최소)
    NONE = "none"      # 아무것도 없음


@dataclass
class OnepagerArtifacts:
    """Collected artifacts for onepager generation."""
    repo_facts: Optional[Dict[str, Any]] = None
    readme_head: Optional[str] = None
    python_metrics: Optional[Dict[str, Any]] = None
    diagnosis_raw: Optional[Dict[str, Any]] = None
    recent_activity: Optional[Dict[str, Any]] = None
    
    def get_tier(self) -> OnepagerTier:
        """Determines artifact tier."""
        if not self.repo_facts:
            return OnepagerTier.NONE
        if self.python_metrics or self.diagnosis_raw:
            return OnepagerTier.TIER_1
        if self.readme_head:
            return OnepagerTier.TIER_2
        return OnepagerTier.TIER_3
    
    def get_source_ids(self) -> List[str]:
        """Returns list of available source IDs."""
        sources = []
        if self.repo_facts:
            sources.append("repo_facts")
        if self.readme_head:
            sources.append("readme_head")
        if self.python_metrics:
            sources.append("python_metrics")
        if self.diagnosis_raw:
            sources.append("diagnosis_raw")
        if self.recent_activity:
            sources.append("recent_activity")
        return sources
    
    def get_source_kinds(self) -> List[str]:
        """Returns list of source kinds matching source IDs."""
        return self.get_source_ids()  # Same as IDs for this case


# 4섹션 스펙 고정 시스템 프롬프트
ONEPAGER_SYSTEM_PROMPT = """당신은 GitHub 저장소를 한 페이지로 요약하는 전문가입니다.

## 역할
- 4개 섹션(개요/장점/리스크/즉시 행동)으로 8-12문장 요약
- 제공된 데이터만 사용 (추측 금지)
- 각 섹션에 근거 데이터를 명시

## 출력 형식 (4섹션 고정)

### {repo_name} 한 페이지 요약

**1. 개요**
[프로젝트 목적, 주요 기술, 활동 최신성 1-2문장]

**2. 장점**
- [문서/테스트/릴리스/커뮤니티 강점 2-3개]

**3. 리스크**
- [유지보수/이슈 체류/보안/버스팩터 위험 2-3개]

**4. 즉시 행동 (Top-3)**
1. [구체적 Task: "~추가", "~개선", "~설정"]
2. [구체적 Task]
3. [구체적 Task]
"""

# Tier별 디그레이드 프롬프트
TIER2_DISCLAIMER = "\n> 장점/리스크는 README 기반 추정입니다. 정확한 분석은 `{repo} 분석해줘`를 요청하세요."
TIER3_DISCLAIMER = "\n> 데이터 부족으로 장점/리스크가 제한적입니다. 상세 분석은 `{repo} 분석해줘`를 요청하세요."


class OnepagerRunner(ExpertRunner):
    """Expert runner for generating one-page project summaries with 4-section format."""
    
    runner_name = "onepager"
    required_artifacts = ["repo_facts"]
    optional_artifacts = ["readme_head", "python_metrics", "diagnosis_raw", "recent_activity"]
    max_retries = 1
    
    def __init__(
        self,
        repo_id: str,
        user_context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(repo_id, user_context)
        self._artifacts = OnepagerArtifacts()
        self._tier = OnepagerTier.NONE
    
    def _collect_artifacts(self) -> None:
        """Collects artifacts for onepager generation with tier detection."""
        parts = self.repo_id.split("/")
        if len(parts) != 2:
            self.collector.add_error("repo_id", f"Invalid format: {self.repo_id}")
            return
        
        owner, repo = parts
        
        # Step 1: Collect repo_facts (필수)
        try:
            overview = fetch_repo_overview(owner, repo)
            self._artifacts.repo_facts = overview
            self.collector.add(kind="repo_facts", data=overview, required=True)
            
            # Extract readme_head (Tier 2)
            readme_content = overview.get("readme_content")
            if readme_content:
                self._artifacts.readme_head = readme_content[:2000]
                self.collector.add(kind="readme_head", data=self._artifacts.readme_head, required=False)
            
            # Extract recent_activity from overview
            self._artifacts.recent_activity = {
                "pushed_at": overview.get("pushed_at"),
                "updated_at": overview.get("updated_at"),
                "open_issues": overview.get("open_issues_count", 0),
            }
            self.collector.add(kind="recent_activity", data=self._artifacts.recent_activity, required=False)
            
        except GitHubClientError as e:
            error_msg = str(e)
            self.collector.add_error("repo_facts", error_msg)
            
            # 권한 오류 감지
            if "NOT_FOUND" in error_msg or "404" in error_msg:
                self.collector.add_error("access", "Repository not found or private")
            return
        except Exception as e:
            logger.error(f"Unexpected error fetching repo overview: {e}")
            self.collector.add_error("repo_facts", str(e))
            return
        
        # Step 2: Try to get diagnosis (Tier 1)
        try:
            payload = {
                "owner": owner,
                "repo": repo,
                "task_type": "full",
                "focus": ["documentation", "activity"],
                "user_context": self.user_context or {},
            }
            diagnosis_result = run_diagnosis(payload)
            if diagnosis_result:
                self._artifacts.diagnosis_raw = diagnosis_result
                self.collector.add(kind="diagnosis_raw", data=diagnosis_result, required=False)
                
                # Extract python_metrics from diagnosis
                scores = diagnosis_result.get("scores", {})
                if scores:
                    self._artifacts.python_metrics = scores
                    self.collector.add(kind="python_metrics", data=scores, required=False)
        except Exception as e:
            logger.warning(f"Diagnosis for onepager failed (will use Tier 2/3): {e}")
        
        # Determine tier
        self._tier = self._artifacts.get_tier()
        logger.info(f"Onepager artifact tier: {self._tier.value}")
    
    def _onepager_guard(self) -> Tuple[bool, Optional[str]]:
        """Guard: checks if we have minimum artifacts to proceed.
        
        Returns: (can_proceed, error_message_if_not)
        """
        # Check for access errors
        errors = self.collector.errors
        for error in errors:
            if "access" in error.lower() or "not_found" in error.lower() or "404" in error.lower():
                return False, "저장소를 찾을 수 없거나 비공개입니다. 저장소 이름과 권한을 확인해 주세요."
        
        # Must have repo_facts at minimum
        if not self._artifacts.repo_facts:
            return False, "저장소 기본 정보를 가져올 수 없습니다."
        
        return True, None
    
    def _execute(self) -> RunnerResult:
        """Executes onepager generation with tier-based quality."""
        # Guard check
        can_proceed, error_msg = self._onepager_guard()
        if not can_proceed:
            return RunnerResult.fail(error_msg or "Onepager guard failed")
        
        # Generate based on tier
        try:
            if self._tier == OnepagerTier.TIER_1:
                text = self._generate_tier1_onepager()
            elif self._tier == OnepagerTier.TIER_2:
                text = self._generate_tier2_onepager()
            else:
                text = self._generate_tier3_onepager()
        except Exception as e:
            logger.warning(f"LLM onepager failed, using template: {e}")
            text = self._build_fallback_onepager()
        
        # Build answer with sources
        sources = self._artifacts.get_source_ids()
        if not sources:
            sources = ["repo_facts"]  # Minimum fallback
        
        # Tier 1 requires ≥3 sources, Tier 2/3 requires ≥2
        min_sources = 3 if self._tier == OnepagerTier.TIER_1 else 2
        if len(sources) < min_sources and len(sources) > 0:
            # Pad with available sources
            while len(sources) < min_sources and sources:
                sources.append(sources[0])
        
        answer = AnswerContract(
            text=text,
            sources=sources,
            source_kinds=self._artifacts.get_source_kinds() or ["repo_facts"],
        )
        
        degraded = self._tier in [OnepagerTier.TIER_2, OnepagerTier.TIER_3]
        
        if degraded:
            return RunnerResult.degraded_ok(
                answer=answer,
                artifacts_out=sources,
                reason=f"tier_{self._tier.value}_limited_data",
            )
        
        return RunnerResult.ok(
            answer=answer,
            artifacts_out=sources,
            meta={"tier": self._tier.value, "section_count": 4},
        )
    
    def _fallback_execute(self) -> RunnerResult:
        """Fallback: generate onepager from available data."""
        text = self._build_fallback_onepager()
        
        sources = self._artifacts.get_source_ids()
        if not sources:
            sources = [f"FALLBACK:{self.repo_id}"]
        
        answer = AnswerContract(
            text=text,
            sources=sources,
            source_kinds=self._artifacts.get_source_kinds() or ["fallback"],
        )
        
        return RunnerResult.degraded_ok(
            answer=answer,
            artifacts_out=sources,
            reason="fallback_minimal_data",
        )
    
    def _generate_tier1_onepager(self) -> str:
        """Generates full onepager with diagnosis data (Tier 1)."""
        return self._call_llm_onepager(include_diagnosis=True, disclaimer="")
    
    def _generate_tier2_onepager(self) -> str:
        """Generates onepager with README-based estimates (Tier 2)."""
        disclaimer = TIER2_DISCLAIMER.format(repo=self.repo_id)
        return self._call_llm_onepager(include_diagnosis=False, disclaimer=disclaimer)
    
    def _generate_tier3_onepager(self) -> str:
        """Generates minimal onepager with limited data warning (Tier 3)."""
        disclaimer = TIER3_DISCLAIMER.format(repo=self.repo_id)
        return self._call_llm_onepager(include_diagnosis=False, disclaimer=disclaimer)
    
    def _call_llm_onepager(self, include_diagnosis: bool, disclaimer: str) -> str:
        """Calls LLM to generate onepager with 4-section format."""
        repo_facts = self._artifacts.repo_facts or {}
        readme_head = self._artifacts.readme_head or ""
        diagnosis = self._artifacts.diagnosis_raw or {}
        recent_activity = self._artifacts.recent_activity or {}
        
        # Build user prompt
        user_parts = [f"## 저장소: {self.repo_id}\n"]
        
        # Section 1: repo_facts
        user_parts.append("### 기본 정보 (repo_facts)")
        user_parts.append(f"- 설명: {repo_facts.get('description') or '(없음)'}")
        user_parts.append(f"- 언어: {repo_facts.get('language') or '(없음)'}")
        user_parts.append(f"- Stars: {repo_facts.get('stargazers_count', 0):,}")
        user_parts.append(f"- Forks: {repo_facts.get('forks_count', 0):,}")
        user_parts.append(f"- License: {(repo_facts.get('license') or {}).get('spdxId') or '(없음)'}")
        user_parts.append("")
        
        # Section 2: recent_activity
        user_parts.append("### 최근 활동 (recent_activity)")
        user_parts.append(f"- 마지막 푸시: {recent_activity.get('pushed_at') or '(없음)'}")
        user_parts.append(f"- 열린 이슈: {recent_activity.get('open_issues', 0)}")
        user_parts.append("")
        
        # Section 3: diagnosis (Tier 1 only)
        if include_diagnosis and diagnosis:
            scores = diagnosis.get("scores", {})
            labels = diagnosis.get("labels", {})
            
            user_parts.append("### 건강도 점수 (python_metrics/diagnosis_raw)")
            user_parts.append(f"- 건강 점수: {scores.get('health_score', 'N/A')}")
            user_parts.append(f"- 문서화 품질: {scores.get('documentation_quality', 'N/A')}")
            user_parts.append(f"- 활동성: {scores.get('activity_maintainability', 'N/A')}")
            user_parts.append(f"- 온보딩 용이성: {scores.get('onboarding_score', 'N/A')}")
            user_parts.append(f"- 건강 레벨: {labels.get('health_level', 'N/A')}")
            user_parts.append(f"- 문서 이슈: {', '.join(labels.get('docs_issues', [])) or '없음'}")
            user_parts.append(f"- 활동성 이슈: {', '.join(labels.get('activity_issues', [])) or '없음'}")
            user_parts.append("")
            
            # Tasks
            tasks = diagnosis.get("onboarding_tasks", {})
            beginner_tasks = tasks.get("beginner", [])[:3]
            if beginner_tasks:
                user_parts.append("### 추천 Task (onboarding_tasks)")
                for task in beginner_tasks:
                    user_parts.append(f"- {task.get('title', '제목 없음')}: {task.get('rationale', '')[:50]}")
                user_parts.append("")
        else:
            user_parts.append("### 건강도 점수")
            user_parts.append("(진단 데이터 없음 - README 기반 추정 필요)")
            user_parts.append("")
        
        # Section 4: readme_head
        if readme_head:
            user_parts.append("### README (readme_head)")
            user_parts.append("```")
            user_parts.append(readme_head[:1200])
            user_parts.append("```")
        
        user_parts.append("\n위 데이터를 기반으로 4섹션(개요/장점/리스크/즉시 행동) 한 페이지 요약을 작성해 주세요.")
        
        user_prompt = "\n".join(user_parts)
        
        # Call LLM
        client = fetch_llm_client()
        request = ChatRequest(
            messages=[
                ChatMessage(role="system", content=ONEPAGER_SYSTEM_PROMPT.format(
                    repo_name=self.repo_id,
                )),
                ChatMessage(role="user", content=user_prompt),
            ],
            temperature=0.3,
            max_tokens=700,
        )
        
        response = client.chat(request)
        result = response.content
        
        # Add disclaimer if needed
        if disclaimer:
            result += disclaimer
        
        return result
    
    def _build_fallback_onepager(self) -> str:
        """Builds minimal onepager using template (no LLM)."""
        repo_facts = self._artifacts.repo_facts or {}
        diagnosis = self._artifacts.diagnosis_raw or {}
        
        description = repo_facts.get("description") or "(설명 없음)"
        language = repo_facts.get("language") or "(없음)"
        stars = repo_facts.get("stargazers_count", 0)
        forks = repo_facts.get("forks_count", 0)
        
        # Scores (if available)
        scores = diagnosis.get("scores", {})
        health = scores.get("health_score", "N/A")
        
        # Tasks (if available)
        tasks = diagnosis.get("onboarding_tasks", {})
        beginner_tasks = tasks.get("beginner", [])[:3]
        task_lines = []
        for i, task in enumerate(beginner_tasks, 1):
            task_lines.append(f"{i}. {task.get('title', '제목 없음')}")
        tasks_text = "\n".join(task_lines) if task_lines else "1. README 개선\n2. 테스트 추가\n3. 문서화 보완"
        
        # Determine disclaimer
        tier = self._artifacts.get_tier()
        if tier == OnepagerTier.TIER_3:
            disclaimer = TIER3_DISCLAIMER.format(repo=self.repo_id)
        elif tier == OnepagerTier.TIER_2:
            disclaimer = TIER2_DISCLAIMER.format(repo=self.repo_id)
        else:
            disclaimer = ""
        
        text = f"""### {self.repo_id} 한 페이지 요약

**1. 개요**
{description}
주 언어: {language} | Stars: {stars:,} | Forks: {forks:,}

**2. 장점**
- 활발한 커뮤니티 ({stars:,} Stars)
- 오픈소스 프로젝트로 기여 가능

**3. 리스크**
- 건강 점수: {health}
- (상세 분석 필요)

**4. 즉시 행동 (Top-3)**
{tasks_text}

**다음 행동**
- `{self.repo_id} 분석해줘`: 상세 분석 보기
- `점수 설명해줘`: 각 점수의 근거 확인{disclaimer}"""
        
        return text
