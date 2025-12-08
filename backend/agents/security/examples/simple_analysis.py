"""
간단한 보안 분석 예제
"""
import sys
import os

# 경로 설정
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from agents.security.agent import SecurityAnalysisAgent, visualize_graph


def main():
    """메인 함수"""
    
    # 그래프 시각화
    print("Agent Graph Structure:")
    visualize_graph()
    
    # 에이전트 초기화
    print("\n\nInitializing Security Analysis Agent...")
    agent = SecurityAnalysisAgent(
        max_iterations=10,
        verbose=True
    )
    
    # 분석 실행 (작은 레포지토리로 테스트)
    print("\n\nAnalyzing repository...")
    result = agent.analyze(
        owner="octocat",  # GitHub의 테스트 계정
        repository="Hello-World"  # 작은 테스트 레포지토리
    )
    
    # 결과 출력
    print("\n\n" + "="*60)
    print("FINAL RESULTS")
    print("="*60)
    print(f"Success: {result.get('success')}")
    print(f"Repository: {result.get('owner')}/{result.get('repository')}")
    print(f"Dependencies: {result.get('dependency_count')}")
    print(f"Security Grade: {result.get('security_grade')}")
    print(f"Errors: {len(result.get('errors', []))}")
    print(f"Warnings: {len(result.get('warnings', []))}")
    print()
    
    if result.get('recommendations'):
        print(f"Recommendations ({len(result.get('recommendations'))}): ")
        for i, rec in enumerate(result.get('recommendations', [])[:5], 1):
            print(f"  {i}. {rec}")
    
    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    main()
