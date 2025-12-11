import pytest
from unittest.mock import patch, MagicMock
from backend.agents.supervisor.models import SupervisorInput, TaskType
from backend.agents.supervisor.service import init_state_from_input
from backend.agents.diagnosis.models import DiagnosisInput, DiagnosisOutput
from backend.agents.diagnosis.service import run_diagnosis
from backend.core.models import DiagnosisCoreResult

def test_supervisor_input_valid():
    inp = SupervisorInput(
        task_type="diagnose_repo",
        owner="Hyeri-hci",
        repo="OSSDoctor",
    )
    assert inp.task_type == "diagnose_repo"
    assert inp.owner == "Hyeri-hci"

def test_init_state_defaults():
    inp = SupervisorInput(task_type="diagnose_repo", owner="a", repo="b")
    state = init_state_from_input(inp)
    # SupervisorState는 Pydantic BaseModel이므로 속성 접근 사용
    assert state.step == 0
    assert state.max_step == 10
    assert state.diagnosis_result is None
    assert state.task_type == "diagnose_repo"
    # repo_id는 owner/repo 조합
    assert f"{state.owner}/{state.repo}" == "a/b"

@pytest.mark.slow
@pytest.mark.skip(reason="Mock 경로가 변경된 API와 맞지 않음 - 리팩토링 필요")
@patch("backend.agents.diagnosis.service.fetch_repo_snapshot")
@patch("backend.agents.diagnosis.service.analyze_docs")
@patch("backend.agents.diagnosis.service.analyze_activity")
@patch("backend.agents.diagnosis.service.parse_dependencies")
@patch("backend.agents.diagnosis.service.compute_scores")
def test_run_diagnosis_service(mock_compute, mock_deps, mock_activity, mock_docs, mock_fetch):
    # Mock return values
    mock_fetch.return_value = MagicMock()
    mock_docs.return_value = MagicMock(missing_sections=[], marketing_ratio=0.5)
    mock_docs.return_value.to_dict.return_value = {}
    mock_activity.return_value = MagicMock()
    mock_activity.return_value.to_dict.return_value = {}
    mock_deps.return_value = MagicMock()
    
    mock_diagnosis_result = DiagnosisCoreResult(
        repo_id="test/repo",
        documentation_quality=80,
        activity_maintainability=70,
        health_score=75,
        health_level="good",
        onboarding_score=80,
        onboarding_level="easy",
        is_healthy=True,
        dependency_complexity_score=20,
        dependency_flags=[],
        docs_issues=[],
        activity_issues=[]
    )
    mock_compute.return_value = mock_diagnosis_result

    # Input
    input_data = DiagnosisInput(owner="test", repo="repo", use_llm_summary=False)
    
    # Run
    output = run_diagnosis(input_data)
    
    # Verify
    assert isinstance(output, DiagnosisOutput)
    assert output.repo_id == "test/repo"
    assert output.health_score == 75
    assert output.dependency_complexity_level == "low" # score 20 -> low
    assert output.summary_for_user.startswith("### test/repo 진단 결과") # Fallback summary
