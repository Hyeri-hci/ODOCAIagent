
from typing import Optional
from backend.agents.supervisor.graph import get_supervisor_graph
from backend.core.models import DiagnosisCoreResult

def run_supervisor_diagnosis(
    owner: str,
    repo: str,
    ref: str = "main"
) -> Optional[DiagnosisCoreResult]:
    """
    Supervisor를 통해 저장소 진단을 실행하는 엔트리 포인트.
    LLM 요약보다는 Core 진단 결과(DiagnosisCoreResult) 반환에 집중.
    """
    # 1. 그래프 생성
    graph = get_supervisor_graph()
    
    # 2. 초기 상태 구성
    # thread_id는 owner/repo/ref 조합으로 설정하여 재실행 시 상태 복원 가능성 열어둠
    config = {"configurable": {"thread_id": f"{owner}/{repo}@{ref}"}}
    
    initial_state = {
        "owner": owner,
        "repo": repo,
        "repo_ref": ref,
        "task_type": "diagnosis",
        "messages": [],
    }
    
    # 3. 그래프 실행
    # invoke를 사용하여 동기적으로 실행 완료 대기
    result = graph.invoke(initial_state, config=config)
    
    # 4. 결과 추출
    # SupervisorState에서 diagnosis_result 반환
    return result.get("diagnosis_result")
