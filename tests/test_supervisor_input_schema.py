from backend.agents.supervisor.models import SupervisorInput
import pytest

def test_supervisor_input_valid():
    inp = SupervisorInput(
        task_type="diagnose_repo",
        owner="Hyeri-hci",
        repo="ODOCAIagent",
    )
    assert inp.task_type == "diagnose_repo"
    assert inp.owner == "Hyeri-hci"

def test_supervisor_input_invalid_task_type():
    with pytest.raises(Exception):
        SupervisorInput(task_type="unknown", owner="a", repo="b")  # ValidationError 기대
