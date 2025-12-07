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
        assert result["next_node_override"] == "__end__"

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
