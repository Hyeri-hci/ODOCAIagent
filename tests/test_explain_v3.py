"""
Explain v3 테스트 - 점수 해설 파이프라인 검증.

테스트 케이스:
1. 단일 metric explain (health_score)
2. 복수 metric explain (2개)
3. 복수 metric explain (3개)
4. 0개 metric fallback
5. 4개 이상 metric fallback
"""
import pytest
from unittest.mock import MagicMock, patch

from backend.agents.supervisor.nodes.summarize_node import (
    _extract_target_metrics,
    _format_diagnosis_for_explain,
    _format_diagnosis_for_explain_multi,
    _postprocess_explain_response,
    _generate_explain_response,
    METRIC_ALIAS_MAP,
    METRIC_NAME_KR,
)
from backend.agents.diagnosis.tools.scoring.reasoning_builder import build_explain_context
from backend.agents.diagnosis.tools.scoring.health_formulas import (
    SCORE_FORMULA_DESC,
    METRIC_EXPLANATION,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_diagnosis_result():
    """테스트용 diagnosis_result"""
    return {
        "scores": {
            "health_score": 76,
            "documentation_quality": 80,
            "activity_maintainability": 74,
            "onboarding_score": 78,
            "is_healthy": True,
        },
        "details": {
            "docs": {
                "readme_categories": {
                    "introduction": True,
                    "installation": True,
                    "usage": True,
                    "contributing": False,
                    "license": True,
                    "contact": False,
                    "badges": True,
                    "examples": False,
                },
            },
            "readme_metrics": {
                "word_count": 500,
            },
            "activity": {
                "commit": {
                    "total_commits": 120,
                    "unique_authors": 8,
                    "days_since_last_commit": 3,
                    "commits_per_week": 15,
                },
                "issue": {
                    "open_issues": 25,
                    "opened_issues_in_window": 30,
                    "closed_issues_in_window": 20,
                    "issue_closure_ratio": 0.67,
                    "median_time_to_close_days": 7,
                },
                "pr": {
                    "prs_in_window": 45,
                    "merged_in_window": 38,
                    "pr_merge_ratio": 0.84,
                    "median_time_to_merge_days": 2,
                },
                "scores": {
                    "commit_score": 0.75,
                    "issue_score": 0.65,
                    "pr_score": 0.80,
                    "overall": 0.74,
                },
            },
        },
        "onboarding_tasks": {
            "beginner": [
                {"title": "Fix typo", "labels": ["good first issue"]},
                {"title": "Add test", "labels": ["help wanted"]},
            ],
            "intermediate": [],
            "advanced": [],
        },
    }


@pytest.fixture
def sample_explain_context(sample_diagnosis_result):
    """테스트용 explain_context"""
    return build_explain_context(sample_diagnosis_result)


# ============================================================================
# _extract_target_metrics 테스트
# ============================================================================

class TestExtractTargetMetrics:
    def test_single_metric_korean(self):
        """한국어 단일 메트릭 추출"""
        assert _extract_target_metrics("활동성 점수 설명해 줘") == ["activity_maintainability"]
        assert _extract_target_metrics("문서 품질이 왜 이래?") == ["documentation_quality"]
        assert _extract_target_metrics("온보딩 점수 알려줘") == ["onboarding_score"]
    
    def test_single_metric_english(self):
        """영어 단일 메트릭 추출"""
        assert _extract_target_metrics("explain health_score") == ["health_score"]
        assert _extract_target_metrics("what is activity score?") == ["activity_maintainability"]
    
    def test_multi_metrics(self):
        """복수 메트릭 추출"""
        result = _extract_target_metrics("문서랑 활동성 점수 비교해 줘")
        assert "documentation_quality" in result
        assert "activity_maintainability" in result
        assert len(result) == 2
    
    def test_three_metrics(self):
        """3개 메트릭 추출"""
        result = _extract_target_metrics("health, 문서, 온보딩 세 개를 비교해서 설명해 줘")
        assert len(result) == 3
        assert "health_score" in result
        assert "documentation_quality" in result
        assert "onboarding_score" in result
    
    def test_no_metrics(self):
        """메트릭 없는 경우"""
        assert _extract_target_metrics("점수 좀 설명해 줘") == []
        assert _extract_target_metrics("왜 이렇게 나왔어?") == []
    
    def test_duplicate_removal(self):
        """중복 제거 확인"""
        result = _extract_target_metrics("문서 점수, 리드미 품질, readme 설명해 줘")
        assert result == ["documentation_quality"]
    
    def test_colloquial_aliases(self):
        """구어체 alias 테스트"""
        assert _extract_target_metrics("이 리포 어때?") == ["health_score"]
        assert _extract_target_metrics("최근 활동 어때?") == ["activity_maintainability"]
        assert _extract_target_metrics("진입 장벽 어때?") == ["onboarding_score"]
        assert _extract_target_metrics("문서화 잘 되어 있어?") == ["documentation_quality"]


# ============================================================================
# _format_diagnosis_for_explain 테스트
# ============================================================================

class TestFormatDiagnosisForExplain:
    def test_health_score_format(self, sample_explain_context):
        """health_score 포맷팅"""
        result = _format_diagnosis_for_explain("health_score", sample_explain_context)
        
        assert "전체 건강 점수" in result
        assert "76" in result  # score
        assert "공식" in result
        assert "documentation_quality" in result
        assert "activity_maintainability" in result
    
    def test_documentation_quality_format(self, sample_explain_context):
        """documentation_quality 포맷팅"""
        result = _format_diagnosis_for_explain("documentation_quality", sample_explain_context)
        
        assert "문서 품질" in result
        assert "80" in result  # score
        assert "포함 섹션" in result
        assert "누락 섹션" in result
    
    def test_activity_format(self, sample_explain_context):
        """activity_maintainability 포맷팅"""
        result = _format_diagnosis_for_explain("activity_maintainability", sample_explain_context)
        
        assert "활동성" in result
        assert "COMMIT" in result
        assert "ISSUE" in result
        assert "PR" in result
        assert "120" in result  # total commits
    
    def test_missing_metric(self, sample_explain_context):
        """존재하지 않는 메트릭"""
        result = _format_diagnosis_for_explain("unknown_metric", sample_explain_context)
        assert "상세 데이터가 없습니다" in result


# ============================================================================
# _format_diagnosis_for_explain_multi 테스트
# ============================================================================

class TestFormatDiagnosisForExplainMulti:
    def test_two_metrics(self, sample_explain_context):
        """2개 메트릭 포맷팅"""
        result = _format_diagnosis_for_explain_multi(
            ["health_score", "documentation_quality"],
            sample_explain_context
        )
        
        assert "복수 점수 분석" in result
        assert "전체 건강 점수" in result
        assert "문서 품질" in result
    
    def test_three_metrics(self, sample_explain_context):
        """3개 메트릭 포맷팅"""
        result = _format_diagnosis_for_explain_multi(
            ["health_score", "activity_maintainability", "onboarding_score"],
            sample_explain_context
        )
        
        assert result.count("---") >= 2  # 구분선 있어야 함


# ============================================================================
# _postprocess_explain_response 테스트
# ============================================================================

class TestPostprocessExplainResponse:
    def test_report_header_warning(self, caplog):
        """리포트 헤더 감지 시 warning"""
        text = "## 저장소 건강 상태\n- bullet 1"
        
        with caplog.at_level("WARNING"):
            _postprocess_explain_response(text)
        
        assert "리포트 템플릿 헤더 감지" in caplog.text
    
    def test_returns_text_unchanged(self):
        """텍스트가 그대로 반환됨"""
        text = "- bullet 1\n- bullet 2\n- bullet 3"
        result = _postprocess_explain_response(text)
        assert result == text


# ============================================================================
# _generate_explain_response 테스트 (LLM Mock)
# ============================================================================

class TestGenerateExplainResponse:
    def test_zero_metrics_fallback(self, sample_explain_context):
        """0개 메트릭 → 질문 되묻기"""
        result = _generate_explain_response(
            user_query="점수 설명해 줘",
            metrics=[],
            explain_context=sample_explain_context,
            repo_id="test/repo",
        )
        
        assert "어떤 점수를 설명해 드릴까요" in result
    
    def test_four_plus_metrics_fallback(self, sample_explain_context):
        """4개 이상 메트릭 → 제한 안내"""
        result = _generate_explain_response(
            user_query="전부 다 설명해",
            metrics=["health_score", "documentation_quality", "activity_maintainability", "onboarding_score"],
            explain_context=sample_explain_context,
            repo_id="test/repo",
        )
        
        assert "최대 3개까지" in result
    
    @patch("backend.agents.supervisor.nodes.summarize_node.fetch_llm_client")
    def test_single_metric_llm_call(self, mock_fetch_llm, sample_explain_context):
        """단일 메트릭 → LLM 호출"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "앞서 분석한 test/repo의 활동성 점수(74점)를 설명드릴게요.\n- 커밋 활발\n- PR 빠름"
        mock_client.chat.return_value = mock_response
        mock_fetch_llm.return_value = mock_client
        
        result = _generate_explain_response(
            user_query="활동성 설명해 줘",
            metrics=["activity_maintainability"],
            explain_context=sample_explain_context,
            repo_id="test/repo",
        )
        
        assert "앞서 분석한" in result
        mock_client.chat.assert_called_once()
    
    @patch("backend.agents.supervisor.nodes.summarize_node.fetch_llm_client")
    def test_multi_metric_llm_call(self, mock_fetch_llm, sample_explain_context):
        """복수 메트릭 → LLM 호출"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "### 점수 개요\n두 점수 비교...\n### 문서 품질\n- bullet\n### 활동성\n- bullet"
        mock_client.chat.return_value = mock_response
        mock_fetch_llm.return_value = mock_client
        
        result = _generate_explain_response(
            user_query="문서랑 활동성 비교해 줘",
            metrics=["documentation_quality", "activity_maintainability"],
            explain_context=sample_explain_context,
            repo_id="test/repo",
        )
        
        assert "점수 개요" in result
        mock_client.chat.assert_called_once()


# ============================================================================
# health_formulas 테스트
# ============================================================================

class TestHealthFormulas:
    def test_score_formula_desc_exists(self):
        """SCORE_FORMULA_DESC에 모든 메트릭 존재"""
        expected_metrics = ["health_score", "documentation_quality", "activity_maintainability", "onboarding_score"]
        for metric in expected_metrics:
            assert metric in SCORE_FORMULA_DESC
            assert "formula" in SCORE_FORMULA_DESC[metric]
    
    def test_metric_explanation_exists(self):
        """METRIC_EXPLANATION에 모든 메트릭 존재"""
        expected_metrics = ["health_score", "documentation_quality", "activity_maintainability", "onboarding_score"]
        for metric in expected_metrics:
            assert metric in METRIC_EXPLANATION


# ============================================================================
# reasoning_builder 테스트
# ============================================================================

class TestReasoningBuilder:
    def test_build_explain_context(self, sample_diagnosis_result):
        """explain_context 전체 빌드"""
        context = build_explain_context(sample_diagnosis_result)
        
        assert "health_score" in context
        assert "documentation_quality" in context
        assert "activity_maintainability" in context
        assert "onboarding_score" in context
    
    def test_health_reasoning_structure(self, sample_diagnosis_result):
        """health_reasoning 구조 검증"""
        context = build_explain_context(sample_diagnosis_result)
        health = context["health_score"]
        
        assert "score" in health
        assert "formula" in health
        assert "components" in health
        assert "is_healthy" in health
        assert health["score"] == 76
    
    def test_activity_reasoning_structure(self, sample_diagnosis_result):
        """activity_reasoning 구조 검증"""
        context = build_explain_context(sample_diagnosis_result)
        activity = context["activity_maintainability"]
        
        assert "commit" in activity
        assert "issue" in activity
        assert "pr" in activity
        assert activity["commit"]["total_commits"] == 120


# ============================================================================
# Task Personalization Tests
# ============================================================================

class TestTaskPersonalization:
    @pytest.fixture
    def sample_tasks(self):
        """테스트용 TaskSuggestion 목록"""
        from backend.agents.diagnosis.tools.onboarding.onboarding_tasks import TaskSuggestion
        return [
            TaskSuggestion(
                kind="doc",
                difficulty="easy",
                level=1,
                id="issue#1",
                title="README 오타 수정",
                task_score=0.8,
                estimated_hours=0.5,
                required_skills=["markdown", "git"],
            ),
            TaskSuggestion(
                kind="bugfix",
                difficulty="medium",
                level=3,
                id="issue#2",
                title="버그 수정",
                task_score=0.7,
                estimated_hours=2.5,
                required_skills=["python", "testing"],
            ),
            TaskSuggestion(
                kind="feature",
                difficulty="hard",
                level=5,
                id="issue#3",
                title="새 기능 구현",
                task_score=0.9,
                estimated_hours=8.0,
                required_skills=["python", "architecture", "testing"],
            ),
        ]
    
    def test_skill_match_score(self, sample_tasks):
        """스킬 매칭 점수 계산"""
        from backend.agents.diagnosis.tools.onboarding.onboarding_tasks import _calculate_skill_match_score
        
        task = sample_tasks[1]  # python, testing
        user_skills = ["python", "javascript"]
        
        score = _calculate_skill_match_score(task, user_skills)
        assert 0.4 <= score <= 0.6  # 1/2 match
    
    def test_skill_match_no_overlap(self, sample_tasks):
        """스킬 겹침 없음"""
        from backend.agents.diagnosis.tools.onboarding.onboarding_tasks import _calculate_skill_match_score
        
        task = sample_tasks[0]  # markdown, git
        user_skills = ["python", "java"]
        
        score = _calculate_skill_match_score(task, user_skills)
        assert score == 0.0
    
    def test_time_fit_score_optimal(self, sample_tasks):
        """시간 적합도 - 최적 범위"""
        from backend.agents.diagnosis.tools.onboarding.onboarding_tasks import _calculate_time_fit_score
        
        task = sample_tasks[1]  # 2.5 hours
        score = _calculate_time_fit_score(task, time_budget_hours=4.0)  # 62.5% ratio
        assert score == 1.0
    
    def test_time_fit_score_too_short(self, sample_tasks):
        """시간 적합도 - 너무 짧음"""
        from backend.agents.diagnosis.tools.onboarding.onboarding_tasks import _calculate_time_fit_score
        
        task = sample_tasks[0]  # 0.5 hours
        score = _calculate_time_fit_score(task, time_budget_hours=5.0)  # 10% ratio
        assert score == 0.7
    
    def test_rank_tasks_for_user(self, sample_tasks):
        """rank_tasks_for_user 기본 동작"""
        from backend.agents.diagnosis.tools.onboarding.onboarding_tasks import rank_tasks_for_user
        
        ranked = rank_tasks_for_user(
            sample_tasks,
            user_skills=["python", "testing"],
            time_budget_hours=3.0,
            experience_level="beginner",
            top_k=3,
        )
        
        assert len(ranked) >= 1
        assert "task" in ranked[0]
        assert "match_score" in ranked[0]
        assert "match_reasons" in ranked[0]
    
    def test_generate_personalized_recommendation(self, sample_tasks):
        """개인화 추천 메시지 생성"""
        from backend.agents.diagnosis.tools.onboarding.onboarding_tasks import generate_personalized_recommendation
        
        result = generate_personalized_recommendation(
            sample_tasks,
            user_skills=["markdown", "git"],
            time_budget_hours=2.0,
            experience_level="beginner",
        )
        
        assert "top_picks" in result
        assert "message" in result
        assert "meta" in result
        assert "입문자" in result["message"]
    
    def test_empty_tasks_recommendation(self):
        """빈 태스크 목록 처리"""
        from backend.agents.diagnosis.tools.onboarding.onboarding_tasks import generate_personalized_recommendation
        
        result = generate_personalized_recommendation(
            [],
            user_skills=["python"],
            time_budget_hours=2.0,
            experience_level="beginner",
        )
        
        assert result["top_picks"] == []
        assert "찾지 못했습니다" in result["message"]



