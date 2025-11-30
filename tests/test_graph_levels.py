"""
레벨별 온보딩 테스트

초보자/중급자/고급자 각 레벨에 맞는 Task가 추천되는지 확인.
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
    level=logging.WARNING,  # 간결한 출력을 위해 WARNING으로
    format="%(name)s - %(message)s"
)

from backend.agents.supervisor.graph import build_supervisor_graph
from backend.agents.supervisor.models import SupervisorState


def test_level(level: str, query: str):
    """특정 레벨 테스트"""
    graph = build_supervisor_graph()
    
    initial_state: SupervisorState = {
        "user_query": query,
        "history": [],
    }
    
    print("=" * 70)
    print(f"테스트: {level.upper()} 레벨")
    print("=" * 70)
    print(f"질문: {query}")
    print()
    
    result = graph.invoke(initial_state)
    
    user_context = result.get("user_context", {})
    detected_level = user_context.get("level", "unknown")
    
    print(f"감지된 레벨: {detected_level}")
    print(f"intent: {result.get('intent')}")
    print()
    
    # 온보딩 Task 정보
    diagnosis_result = result.get("diagnosis_result", {})
    onboarding_tasks = diagnosis_result.get("onboarding_tasks", {})
    
    if onboarding_tasks:
        beginner = onboarding_tasks.get("beginner", [])
        intermediate = onboarding_tasks.get("intermediate", [])
        advanced = onboarding_tasks.get("advanced", [])
        
        print(f"온보딩 Task 분포: 초보자={len(beginner)}, 중급자={len(intermediate)}, 고급자={len(advanced)}")
    
    # LLM 응답 출력
    llm_summary = result.get("llm_summary", "")
    print()
    print("-" * 70)
    print("LLM 응답:")
    print("-" * 70)
    print(llm_summary)
    print()
    
    return detected_level


def main():
    # 1. 초보자 테스트
    test_level(
        "beginner",
        "초보자인데 facebook/react에 기여하고 싶어요. 어디서부터 시작하면 좋을까요?"
    )
    
    print("\n" + "=" * 70 + "\n")
    
    # 2. 중급자 테스트
    test_level(
        "intermediate", 
        "facebook/react에 기여하고 싶습니다. React를 2년 정도 사용해왔고, 버그 수정이나 기능 개선에 참여하고 싶어요."
    )
    
    print("\n" + "=" * 70 + "\n")
    
    # 3. 고급자 테스트
    test_level(
        "advanced",
        "저는 React 코어 컨트리뷰터 경험이 있는 고급 개발자입니다. facebook/react에서 Fiber나 Reconciler 같은 복잡한 이슈에 기여하고 싶어요."
    )


if __name__ == "__main__":
    main()
