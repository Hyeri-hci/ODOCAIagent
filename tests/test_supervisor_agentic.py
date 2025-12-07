import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

"""Agentic Routing Nodes 테스트."""
import pytest
from backend.agents.supervisor.models import SupervisorState
from backend.agents.supervisor.nodes.routing_nodes import (
    intent_analysis_node,
    decision_node,
    quality_check_node,
    map_task_type_to_intent,
    infer_intent_from_context,
    route_after_decision,
    route_after_quality_check,
)


class TestIntentMapping:
    """Intent 매핑 테스트."""

    def test_map_task_type_diagnose(self):
        assert map_task_type_to_intent("diagnose_repo") == "diagnose"

    def test_map_task_type_onboard(self):
        assert map_task_type_to_intent("build_onboarding_plan") == "onboard"

    def test_map_task_type_unknown(self):
        assert map_task_type_to_intent("invalid_task") == "unknown"


class TestIntentInference:
    """Intent 추론 테스트."""

    def test_infer_from_task_type(self):
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo"
        )
        intent, confidence = infer_intent_from_context(state)
        assert intent == "diagnose"
        assert confidence == 1.0

    def test_infer_from_user_context_diagnose(self):
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            user_context={"message": "이 저장소를 진단해주세요"}
        )
        intent, confidence = infer_intent_from_context(state)
        assert intent == "diagnose"

    def test_infer_from_user_context_onboard(self):
        state = SupervisorState(
            task_type="build_onboarding_plan",
            owner="test",
            repo="repo",
            user_context={"message": "온보딩 플랜을 만들어주세요"}
        )
        intent, confidence = infer_intent_from_context(state)
        assert intent == "onboard"


class TestIntentAnalysisNode:
    """intent_analysis_node 테스트."""

    def test_sets_detected_intent(self):
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo"
        )
        result = intent_analysis_node(state)
        assert result["detected_intent"] == "diagnose"
        assert result["intent_confidence"] == 1.0
        assert result["step"] == 1

    def test_onboard_intent(self):
        state = SupervisorState(
            task_type="build_onboarding_plan",
            owner="test",
            repo="repo"
        )
        result = intent_analysis_node(state)
        assert result["detected_intent"] == "onboard"


class TestDecisionNode:
    """decision_node 테스트."""

    def test_diagnose_intent_routes_to_diagnosis(self):
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            detected_intent="diagnose"
        )
        result = decision_node(state)
        assert result["next_node_override"] == "run_diagnosis_node"
        assert "diagnose" in result["decision_reason"].lower()

    def test_onboard_intent_routes_to_diagnosis_first(self):
        state = SupervisorState(
            task_type="build_onboarding_plan",
            owner="test",
            repo="repo",
            detected_intent="onboard"
        )
        result = decision_node(state)
        assert result["next_node_override"] == "run_diagnosis_node"

    def test_unknown_intent_routes_to_end(self):
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            detected_intent="unknown"
        )
        result = decision_node(state)
        assert result["next_node_override"] == "__end__"

    def test_explain_with_existing_diagnosis(self):
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            detected_intent="explain",
            diagnosis_result={"health_score": 80}
        )
        result = decision_node(state)
        # explain intent with existing diagnosis routes to chat_response_node
        assert result["next_node_override"] == "chat_response_node"

    def test_explain_without_diagnosis(self):
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            detected_intent="explain"
        )
        result = decision_node(state)
        assert result["next_node_override"] == "run_diagnosis_node"


class TestQualityCheckNode:
    """quality_check_node 테스트."""

    def test_valid_diagnosis_passes(self):
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            diagnosis_result={
                "repo_id": "test/repo",
                "health_score": 80,
                "health_level": "good",
                "onboarding_score": 70
            }
        )
        result = quality_check_node(state)
        assert result["quality_issues"] == []
        assert result["next_node_override"] == "__end__"

    def test_missing_diagnosis_triggers_rerun(self):
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            diagnosis_result=None,
            rerun_count=0,
            max_rerun=2
        )
        result = quality_check_node(state)
        assert len(result["quality_issues"]) > 0
        assert result["rerun_count"] == 1
        assert result["next_node_override"] == "run_diagnosis_node"

    def test_max_rerun_reached_proceeds(self):
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            diagnosis_result=None,
            rerun_count=2,
            max_rerun=2
        )
        result = quality_check_node(state)
        assert len(result["quality_issues"]) > 0
        assert result["next_node_override"] == "__end__"

    def test_invalid_health_score_triggers_issue(self):
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            diagnosis_result={
                "repo_id": "test/repo",
                "health_score": 150,
                "health_level": "good",
                "onboarding_score": 70
            },
            rerun_count=0
        )
        result = quality_check_node(state)
        assert any("out of range" in issue for issue in result["quality_issues"])


class TestRoutingFunctions:
    """라우팅 함수 테스트."""

    def test_route_after_decision(self):
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            next_node_override="run_diagnosis_node"
        )
        assert route_after_decision(state) == "run_diagnosis_node"

    def test_route_after_decision_default(self):
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            next_node_override=None
        )
        assert route_after_decision(state) == "__end__"

    def test_route_after_quality_check_rerun(self):
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            next_node_override="run_diagnosis_node"
        )
        assert route_after_quality_check(state) == "run_diagnosis_node"

    def test_route_after_quality_check_onboard(self):
        state = SupervisorState(
            task_type="build_onboarding_plan",
            owner="test",
            repo="repo",
            detected_intent="onboard",
            next_node_override="__end__"
        )
        assert route_after_quality_check(state) == "fetch_issues_node"

    def test_route_after_quality_check_end(self):
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            detected_intent="diagnose",
            next_node_override="__end__"
        )
        assert route_after_quality_check(state) == "__end__"


class TestDynamicFlowAdjustments:
    """동적 플로우 조정 테스트."""

    def test_decision_node_beginner_adjustment(self):
        state = SupervisorState(
            task_type="build_onboarding_plan",
            owner="test",
            repo="repo",
            detected_intent="onboard",
            user_context={"experience_level": "beginner"}
        )
        result = decision_node(state)
        assert "beginner_friendly_plan" in result["flow_adjustments"]

    def test_decision_node_low_health_warning(self):
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            detected_intent="diagnose",
            diagnosis_result={"health_score": 20}
        )
        result = decision_node(state)
        assert "add_health_warning" in result["flow_adjustments"]
        assert len(result["warnings"]) > 0

    def test_quality_check_low_health_adjustment(self):
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            diagnosis_result={
                "repo_id": "test/repo",
                "health_score": 25,
                "health_level": "bad",
                "onboarding_score": 30
            }
        )
        result = quality_check_node(state)
        assert "recommend_deep_analysis" in result["flow_adjustments"]
        assert any("30점 미만" in w for w in result["warnings"])

    def test_quality_check_moderate_health(self):
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            diagnosis_result={
                "repo_id": "test/repo",
                "health_score": 45,
                "health_level": "warning",
                "onboarding_score": 50
            }
        )
        result = quality_check_node(state)
        assert "moderate_health_notice" in result["flow_adjustments"]

    def test_quality_check_activity_issues_adjustment(self):
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            diagnosis_result={
                "repo_id": "test/repo",
                "health_score": 60,
                "health_level": "warning",
                "onboarding_score": 55,
                "activity_issues": ["No recent commits"]
            }
        )
        result = quality_check_node(state)
        assert "enhance_issue_recommendations" in result["flow_adjustments"]

    def test_quality_check_docs_issues_adjustment(self):
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            diagnosis_result={
                "repo_id": "test/repo",
                "health_score": 70,
                "health_level": "good",
                "onboarding_score": 65,
                "docs_issues": ["Missing README sections"]
            }
        )
        result = quality_check_node(state)
        assert "add_docs_improvement_guide" in result["flow_adjustments"]

    def test_quality_check_preserves_existing_adjustments(self):
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            flow_adjustments=["existing_adjustment"],
            warnings=["existing_warning"],
            diagnosis_result={
                "repo_id": "test/repo",
                "health_score": 80,
                "health_level": "good",
                "onboarding_score": 75
            }
        )
        result = quality_check_node(state)
        assert "existing_adjustment" in result["flow_adjustments"]
        assert "existing_warning" in result["warnings"]

    def test_quality_check_no_duplicate_adjustments(self):
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            flow_adjustments=["add_health_warning"],
            diagnosis_result={
                "repo_id": "test/repo",
                "health_score": 25,
                "health_level": "bad",
                "onboarding_score": 30
            }
        )
        result = quality_check_node(state)
        count = result["flow_adjustments"].count("recommend_deep_analysis")
        assert count <= 1


class TestCacheAwareDecision:
    """캐시 인식 라우팅 테스트."""

    def test_cache_disabled_routes_to_diagnosis(self):
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            detected_intent="diagnose",
            use_cache=False
        )
        result = decision_node(state)
        assert result["next_node_override"] == "run_diagnosis_node"
        assert result["cache_hit"] == False

    def test_cache_hit_field_set(self):
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="nonexistent",
            repo="repo",
            detected_intent="diagnose",
            use_cache=True
        )
        result = decision_node(state)
        assert "cache_hit" in result


class TestCompareIntent:
    """비교 분석 Intent 테스트."""

    def test_compare_keyword_inference(self):
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            user_context={"message": "두 프로젝트를 비교해주세요"}
        )
        intent, confidence = infer_intent_from_context(state)
        assert intent == "compare"

    def test_decision_node_compare_intent(self):
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            detected_intent="compare",
            compare_repos=["owner1/repo1", "owner2/repo2"]
        )
        result = decision_node(state)
        assert result["next_node_override"] == "batch_diagnosis_node"

    def test_decision_node_compare_empty_repos_warning(self):
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            detected_intent="compare",
            compare_repos=[]
        )
        result = decision_node(state)
        assert result["next_node_override"] == "__end__"
        assert any("비교할 저장소" in w for w in result["warnings"])


class TestComparisonNodes:
    """비교 분석 노드 테스트."""

    def test_compare_results_node_empty(self):
        from backend.agents.supervisor.nodes.comparison_nodes import compare_results_node
        
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            compare_results={}
        )
        result = compare_results_node(state)
        assert "비교할 결과가 없습니다" in result["compare_summary"]

    def test_compare_results_node_with_data(self):
        from backend.agents.supervisor.nodes.comparison_nodes import compare_results_node
        
        state = SupervisorState(
            task_type="diagnose_repo",
            owner="test",
            repo="repo",
            compare_results={
                "owner1/repo1": {
                    "health_score": 80,
                    "onboarding_score": 70,
                    "health_level": "good",
                    "onboarding_level": "easy"
                },
                "owner2/repo2": {
                    "health_score": 60,
                    "onboarding_score": 50,
                    "health_level": "warning",
                    "onboarding_level": "medium"
                }
            }
        )
        result = compare_results_node(state)
        # 비교 요약에 두 저장소가 모두 언급되어야 함
        assert "owner1/repo1" in result["compare_summary"]
        assert "owner2/repo2" in result["compare_summary"]
        # 점수도 언급되어야 함 (구체적 형식은 LLM에 따라 다를 수 있음)
        assert "80" in result["compare_summary"] or "건강" in result["compare_summary"]

    def test_parse_repo_string(self):
        from backend.agents.supervisor.nodes.comparison_nodes import _parse_repo_string
        
        assert _parse_repo_string("owner/repo") == ("owner", "repo")
        assert _parse_repo_string("https://github.com/owner/repo") == ("owner", "repo")
        
        with pytest.raises(ValueError):
            _parse_repo_string("invalid")
