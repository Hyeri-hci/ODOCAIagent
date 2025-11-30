"""
Supervisor Graph 온보딩 테스트

초보자가 기여를 시작하고 싶을 때, 추천 온보딩 Task가 자연스럽게 출력되는지 확인.
"""
import logging
import sys
import os
from pathlib import Path

# Windows 콘솔 UTF-8 출력 설정
if sys.platform == "win32":
    os.system("chcp 65001 > nul 2>&1")

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(name)s - %(message)s"
)

from backend.agents.supervisor.graph import build_supervisor_graph
from backend.agents.supervisor.models import SupervisorState


def test_onboarding():
    """온보딩 모드 테스트: 초보자용 추천 Task 출력 확인"""
    graph = build_supervisor_graph()
    
    # 초보자가 기여하고 싶다는 질문
    initial_state: SupervisorState = {
        "user_query": "초보자인데 facebook/react에 기여하고 싶어요. 어디서부터 시작하면 좋을까요?",
        "history": [],
    }
    
    print("=" * 60)
    print("온보딩 테스트: 초보자 기여 시작점 추천")
    print("=" * 60)
    print(f"질문: {initial_state['user_query']}")
    print()
    
    try:
        result = graph.invoke(initial_state)
        
        print("=" * 60)
        print("분석 결과")
        print("=" * 60)
        print(f"task_type: {result.get('task_type')}")
        print(f"intent: {result.get('intent')}")
        print(f"repo: {result.get('repo')}")
        print(f"user_context: {result.get('user_context')}")
        
        # 온보딩 Task 정보 확인
        diagnosis_result = result.get("diagnosis_result", {})
        onboarding_tasks = diagnosis_result.get("onboarding_tasks", {})
        
        if onboarding_tasks:
            beginner = onboarding_tasks.get("beginner", [])
            intermediate = onboarding_tasks.get("intermediate", [])
            meta = onboarding_tasks.get("meta", {})
            
            print(f"\n온보딩 Task 통계:")
            print(f"  - 총 Task: {meta.get('total_count', 0)}개")
            print(f"  - 초보자용: {len(beginner)}개")
            print(f"  - 중급자용: {len(intermediate)}개")
            
            if beginner:
                print(f"\n초보자용 Task (상위 3개):")
                for i, task in enumerate(beginner[:3], 1):
                    print(f"  {i}. [{task.get('difficulty')}] {task.get('title')}")
                    print(f"     - 라벨: {', '.join(task.get('labels', [])[:3])}")
                    print(f"     - 점수: {task.get('task_score', 0):.0f}점")
        
        # LLM 요약 결과
        llm_summary = result.get("llm_summary", "")
        print(f"\n{'=' * 60}")
        print("LLM 응답 (길이: {})".format(len(llm_summary)))
        print("=" * 60)
        print(llm_summary if llm_summary else "없음")
        
        # 결과 파일 저장
        output_file = Path(__file__).parent / "test_graph_onboarding_result.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write("온보딩 테스트 결과\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"질문: {initial_state['user_query']}\n\n")
            f.write(f"task_type: {result.get('task_type')}\n")
            f.write(f"intent: {result.get('intent')}\n")
            f.write(f"user_context: {result.get('user_context')}\n\n")
            f.write("=" * 60 + "\n")
            f.write("LLM 응답\n")
            f.write("=" * 60 + "\n\n")
            f.write(llm_summary)
        
        print(f"\n결과가 {output_file}에 저장되었습니다.")
        
        # 검증: 온보딩 관련 키워드가 응답에 포함되어 있는지
        keywords = ["Task", "시작", "추천", "초보자", "이슈"]
        found = [kw for kw in keywords if kw in llm_summary]
        print(f"\n응답 검증: 키워드 {len(found)}/{len(keywords)}개 발견 ({', '.join(found)})")
        
    except Exception as e:
        print(f"에러 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_onboarding()
