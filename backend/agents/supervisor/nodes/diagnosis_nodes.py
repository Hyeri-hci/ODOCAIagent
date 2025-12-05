from backend.agents.diagnosis.models import DiagnosisInput
from backend.agents.diagnosis.service import run_diagnosis
from backend.agents.supervisor.models import SupervisorState

def run_diagnosis_node(state: SupervisorState) -> dict:
    """
    Supervisor 그래프에서 진단을 실행하는 노드.
    SupervisorState -> DiagnosisInput -> run_diagnosis -> SupervisorState 업데이트
    
    * Idempotency: 이미 diagnosis_result가 있다면 재실행하지 않고 기존 결과를 반환합니다.
    """
    if state.diagnosis_result:
        # 이미 진단 결과가 있으면 재사용 (Smart Agent Behavior)
        return {}

    if not state.owner or not state.repo:
        return {"error": "owner/repo is required for diagnosis"}

    try:
        input_data = DiagnosisInput(
            owner=state.owner, 
            repo=state.repo,
            use_llm_summary=state.user_context.get("use_llm_summary", True)
        )
        
        output = run_diagnosis(input_data)
        
        # 결과 업데이트 (Pydantic 모델의 필드에 맞춰 dict 반환)
        # LangGraph는 이 dict를 기존 state에 merge함
        return {
            "diagnosis_result": output.to_dict(),
            "last_answer_kind": "report",
            # 필요한 경우 repo_snapshot 등도 여기서 업데이트 가능하지만,
            # run_diagnosis가 DTO만 반환하므로 현재 구조에서는 diagnosis_result에 집중
        }
        
    except Exception as e:
        return {"error": f"Diagnosis failed: {str(e)}"}
