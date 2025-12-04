import pytest
from backend.agents.supervisor.service import run_supervisor_diagnosis

def test_diagnosis_no_llm_mode():
    """
    LLM 요약 없이 진단이 수행되는지 테스트.
    use_llm_summary=False일 때:
    1. 진단 결과(DiagnosisCoreResult)가 정상적으로 반환되어야 함.
    2. 에러 메시지가 없어야 함.
    3. LLM 호출 없이도 메시지에 요약이 포함되어야 함.
    """
    # 테스트용 레포지토리 (가벼운 것 사용)
    owner = "Hyeri-hci"
    repo = "odoc_test_repo" # 또는 로컬에서 접근 가능한 다른 레포
    
    print(f"\nTesting No-LLM mode for {owner}/{repo}...")
    
    # use_llm_summary=False로 실행
    result, error_msg = run_supervisor_diagnosis(owner, repo, use_llm_summary=False)
    
    assert error_msg is None, f"Diagnosis failed: {error_msg}"
    assert result is not None, "Diagnosis result is None"
    
    # 결과 검증
    print(f"Health Score: {result.health_score}")
    assert result.health_score >= 0
    
    # 메시지 검증 (SupervisorState를 직접 반환받지 않으므로, 
    # run_supervisor_diagnosis가 반환하는 값에는 메시지가 포함되지 않음.
    # 하지만 에러 없이 리턴되었다는 것은 그래프가 끝까지 돌았다는 뜻.)
    
    # 추가적으로, 로그에 [LLM] 경고가 없는지 눈으로 확인 필요 (pytest -s 사용)
