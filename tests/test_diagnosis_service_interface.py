from backend.agents.diagnosis.models import DiagnosisInput
from backend.agents.diagnosis.service import run_diagnosis
from unittest.mock import patch, MagicMock
from backend.core.models import DiagnosisCoreResult

@patch("backend.agents.diagnosis.service.fetch_repo_snapshot")
@patch("backend.agents.diagnosis.service.analyze_docs")
@patch("backend.agents.diagnosis.service.analyze_activity")
@patch("backend.agents.diagnosis.service.analyze_structure")
@patch("backend.agents.diagnosis.service.parse_dependencies")
@patch("backend.agents.diagnosis.service.compute_scores")
def test_run_diagnosis_basic(mock_compute, mock_deps, mock_structure, mock_activity, mock_docs, mock_fetch):
    # Mock return values
    mock_fetch.return_value = MagicMock()
    mock_docs.return_value = MagicMock(missing_sections=[], marketing_ratio=0.5)
    mock_docs.return_value.to_dict.return_value = {}
    mock_activity.return_value = MagicMock()
    mock_activity.return_value.to_dict.return_value = {}
    mock_structure.return_value = MagicMock()
    mock_structure.return_value.to_dict.return_value = {}
    mock_deps.return_value = MagicMock()
    
    mock_diagnosis_result = DiagnosisCoreResult(
        repo_id="Hyeri-hci/ODOCAIagent",
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

    # Run
    input_ = DiagnosisInput(owner="Hyeri-hci", repo="ODOCAIagent", use_llm_summary=False)
    output = run_diagnosis(input_)

    # Verify
    assert output.repo_id == "Hyeri-hci/ODOCAIagent"
    assert isinstance(output.health_score, float)
    assert isinstance(output.onboarding_score, float)
    assert isinstance(output.docs, dict)
    assert isinstance(output.activity, dict)
    assert isinstance(output.structure, dict)
    assert isinstance(output.summary_for_user, str)
