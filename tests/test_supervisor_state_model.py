from backend.agents.supervisor.models import SupervisorInput
from backend.agents.supervisor.service import init_state_from_input

def test_init_state_defaults():
    inp = SupervisorInput(task_type="diagnose_repo", owner="a", repo="b")
    state = init_state_from_input(inp)

    assert state.task_type == "diagnose_repo"
    assert state.step == 0
    assert state.max_step == 10
    assert state.diagnosis_result is None
    assert state.candidate_issues == []
    assert state.onboarding_plan is None
    assert state.error is None
