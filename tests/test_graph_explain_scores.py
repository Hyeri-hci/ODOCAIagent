"""
explain_scores Intent 테스트

사용자가 점수에 대해 질문할 때 상세한 설명을 제공하는지 테스트합니다.
"""

import sys
import os
from pathlib import Path

# 프로젝트 루트 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))

# Windows 콘솔 인코딩 설정
if sys.platform == "win32":
    os.system("chcp 65001 > nul 2>&1")

import logging
logging.basicConfig(level=logging.WARNING, format="%(name)s - %(message)s")

from backend.agents.supervisor.graph import build_supervisor_graph


def test_explain_scores():
    """explain_scores intent 테스트 - 점수 설명 요청"""
    graph = build_supervisor_graph()
    
    print("=" * 70)
    print("explain_scores Intent 테스트")
    print("=" * 70)
    
    # 테스트 케이스들
    test_cases = [
        {
            "name": "건강 점수 설명 요청",
            "query": "facebook/react의 건강 점수가 왜 76점인지 자세히 설명해줘",
            "expected_intent": "explain_scores",
        },
        {
            "name": "온보딩 점수 설명 요청",
            "query": "이 저장소 온보딩 점수가 낮은 이유가 뭐야? https://github.com/facebook/react",
            "expected_intent": "explain_scores",
        },
        {
            "name": "문서 품질 점수 설명",
            "query": "facebook/react 문서 품질 점수는 어떻게 계산되는 거야?",
            "expected_intent": "explain_scores",
        },
    ]
    
    for i, tc in enumerate(test_cases, 1):
        print(f"\n[테스트 {i}] {tc['name']}")
        print(f"질문: {tc['query']}")
        print("-" * 50)
        
        result = graph.invoke({
            "user_query": tc["query"],
            "history": [],
        })
        
        detected_intent = result.get("intent", "unknown")
        print(f"감지된 intent: {detected_intent}")
        print(f"예상 intent: {tc['expected_intent']}")
        
        # Intent 일치 확인
        if detected_intent == tc["expected_intent"]:
            print("[PASS] Intent 일치")
        else:
            print(f"[WARN] Intent 불일치 (감지: {detected_intent})")
        
        # LLM 응답 출력
        llm_summary = result.get("llm_summary", "")
        print("\nLLM 응답 (앞부분):")
        print("-" * 50)
        # 처음 500자만 출력
        print(llm_summary[:500] if len(llm_summary) > 500 else llm_summary)
        print("..." if len(llm_summary) > 500 else "")
        print()


def test_explain_scores_detailed():
    """상세 점수 설명 테스트 - 전체 응답 확인"""
    graph = build_supervisor_graph()
    
    print("=" * 70)
    print("explain_scores 상세 테스트")
    print("=" * 70)
    
    query = "facebook/react의 전체 건강 점수가 어떻게 계산된 건지 상세히 알려줘. 각 항목별로 점수가 왜 그런지 설명해줘."
    print(f"질문: {query}\n")
    
    result = graph.invoke({
        "user_query": query,
        "history": [],
    })
    
    print(f"감지된 intent: {result.get('intent')}")
    print(f"감지된 레벨: {result.get('user_context', {}).get('level', 'unknown')}")
    print()
    print("-" * 70)
    print("LLM 응답:")
    print("-" * 70)
    print(result.get("llm_summary", ""))


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="explain_scores Intent 테스트")
    parser.add_argument("--detailed", action="store_true", help="상세 테스트 실행")
    args = parser.parse_args()
    
    if args.detailed:
        test_explain_scores_detailed()
    else:
        test_explain_scores()
