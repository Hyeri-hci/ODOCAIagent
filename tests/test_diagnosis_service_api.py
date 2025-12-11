import pytest
from backend.api.diagnosis_service import diagnose_repository

def test_diagnose_repository_api():
    """
    diagnose_repository API가 프론트엔드에서 사용하기 적합한 형태의
    Dict 결과를 반환하는지 테스트합니다.
    """
    owner = "Hyeri-hci"
    repo = "odoc_test_repo"
    
    print(f"\nTesting diagnose_repository API for {owner}/{repo}...")
    
    # 1. 정상 호출 (LLM 요약 없이)
    response = diagnose_repository(owner, repo, use_llm_summary=False)
    
    assert response["ok"] is True
    assert "data" in response
    assert "error" not in response
    
    data = response["data"]
    
    # DTO 필드 검증
    expected_fields = [
        "repo_id", 
        "documentation_quality", "activity_maintainability",
        "health_score", "health_level",
        "onboarding_score", "onboarding_level",
        "dependency_complexity_score", "dependency_complexity_level", "dependency_flags",
        "docs_issues_count", "activity_issues_count"
    ]
    
    for field in expected_fields:
        assert field in data, f"Missing field in response data: {field}"
    
    assert isinstance(data["dependency_flags"], list)
    assert data["dependency_complexity_level"] in ["low", "medium", "high"]
    
    # 값 범위 검증
    assert 0 <= data["health_score"] <= 100
    
    print(f"API Response Data: {data}")

    # 2. 실패 호출 (존재하지 않는 레포)
    print("\nTesting failure case...")
    bad_owner = "Hyeri-hci"
    bad_repo = "non_existent_repo_12345"
    
    response_fail = diagnose_repository(bad_owner, bad_repo, use_llm_summary=False)
    
    assert response_fail["ok"] is False
    assert "error" in response_fail
    assert "task_type" in response_fail
    assert response_fail["task_type"] == "diagnose_repo"
    
    print(f"Failure Response: {response_fail}")
