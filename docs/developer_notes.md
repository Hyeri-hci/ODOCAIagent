# 개발자 노트 및 아키텍처 의사결정

이 문서는 이전에 코드 주석에 산발적으로 흩어져 있던 내부 사고 과정, 아키텍처 의사결정 및 맥락을 기록합니다.

## Legacy Diagnosis Graph (`backend/agents/diagnosis/graph_legacy.py`)

### Legacy Graph의 상태 관리 (State Management)
Legacy `graph_legacy.py`에서 `SupervisorState` Pydantic 모델과 진단 그래프의 데이터 흐름 요구사항 간에 불일치가 발생했습니다.

- **문제 (Issue)**: `fetch_repo_data_node`는 `RepoSnapshot`을 가져오지만, 공유된 `SupervisorState` 모델에는 원래 `repo_snapshot` 필드가 없었습니다.
- **제약 사항 (Constraint)**: LangGraph에서 노드가 딕셔너리를 반환하면 상태(State) 업데이트를 시도합니다. Pydantic 모델에 해당 필드가 없으면 상태 루트(root)에 직접 저장할 수 없습니다.
- **결정 (Decision)**: Legacy 그래프를 위해 엄격한 `SupervisorState` 모델을 수정하는 대신, `repo_snapshot`을 `user_context`(유연한 Dict) 내에 저장하기로 결정했습니다.
- **참고 (Note)**: 새로운 `SupervisorState` 설계(v2)에서는 이 문제를 깔끔하게 처리하기 위해 `repo_snapshot`을 선택적(Optional) 필드로 명시적으로 추가했습니다.

## 일반 지침 (General Guidelines)
- **코드 주석**: 코드 주석은 코드가 *왜* 그렇게 동작하는지(명확하지 않은 경우) 또는 *무엇*을 하는지에 집중하세요. 코드 내에 긴 내부 독백이나 디버깅 사고 과정을 작성하지 마세요.
- **문서화**: 복잡한 아키텍처 선택이나 임시 해결책을 설명하려면 이 파일이나 별도의 설계 문서를 사용하세요.
