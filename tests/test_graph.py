"""
Supervisor Graph 간단 테스트
"""
import logging
import sys
import os
from pathlib import Path

# Windows 콘솔 UTF-8 출력 설정 (chcp 65001과 동일한 효과)
if sys.platform == "win32":
    os.system("chcp 65001 > nul 2>&1")

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

# 로깅 설정 (INFO 레벨로 주요 상태만 확인)
logging.basicConfig(
    level=logging.INFO,
    format="%(name)s - %(message)s"
)

from backend.agents.supervisor.graph import build_supervisor_graph
from backend.agents.supervisor.models import SupervisorState

def test_graph():
    # 그래프 빌드
    graph = build_supervisor_graph()
    
    # 초기 상태 (필수 필드만 설정, 나머지는 기본값 사용)
    initial_state: SupervisorState = {
        "user_query": "https://github.com/facebook/react 저장소 건강 상태 분석해줘",
        "history": [],
    }
    
    print("=" * 60)
    print("테스트 시작: facebook/react 저장소 건강 상태 분석")
    print("=" * 60)
    
    # 그래프 실행
    try:
        result = graph.invoke(initial_state)
        
        print("\n" + "=" * 60)
        print("결과")
        print("=" * 60)
        print(f"task_type: {result.get('task_type')}")
        print(f"diagnosis_task_type: {result.get('diagnosis_task_type')}")
        print(f"repo: {result.get('repo')}")
        
        # 디버깅: 전체 키 출력
        print(f"\n전체 state 키: {list(result.keys())}")
        
        llm_summary = result.get("llm_summary") or ""
        print(f"\n최종 응답 (길이: {len(llm_summary)}):")
        print(llm_summary if llm_summary else "없음")
        
        # 결과를 파일로도 저장
        output_file = Path(__file__).parent / "test_graph_result.txt"
        diagnosis_result = result.get('diagnosis_result', {})
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write("테스트 결과\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"task_type: {result.get('task_type')}\n")
            f.write(f"diagnosis_task_type: {result.get('diagnosis_task_type')}\n")
            f.write(f"repo: {result.get('repo')}\n\n")
            
            # 점수 정보
            f.write("=" * 60 + "\n")
            f.write("점수 정보\n")
            f.write("=" * 60 + "\n")
            f.write(f"scores: {diagnosis_result.get('scores')}\n\n")
            
            # 활동성 데이터 (LLM에 전달되는 실제 숫자)
            f.write("=" * 60 + "\n")
            f.write("활동성 데이터 (LLM에 전달됨)\n")
            f.write("=" * 60 + "\n")
            activity = diagnosis_result.get('details', {}).get('activity', {})
            f.write(f"commit: {activity.get('commit')}\n")
            f.write(f"issue: {activity.get('issue')}\n")
            f.write(f"pr: {activity.get('pr')}\n\n")
            
            f.write("=" * 60 + "\n")
            f.write("최종 응답 (LLM 생성)\n")
            f.write("=" * 60 + "\n\n")
            f.write(llm_summary)
        print(f"\n결과가 {output_file}에 저장되었습니다.")
        
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_graph()
