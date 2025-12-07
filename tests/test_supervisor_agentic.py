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

