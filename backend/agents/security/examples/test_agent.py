"""
에이전트 테스트 (간단 버전)
"""
import sys
import os

# 경로 설정
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from agents.security.agent import SecurityAnalysisAgent


def main():
    """메인 함수"""
    
    # 에이전트 초기화
    print("Initializing Security Analysis Agent...")
    agent = SecurityAnalysisAgent(
        max_iterations=10,
        verbose=True
    )
    
    # 분석 실행
    print("\nAnalyzing repository...")
    print("-" * 60)
    
    result = agent.analyze(
        owner="octocat",
        repository="Hello-World"
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
    
    if result.get('errors'):
        print("\nErrors:")
        for error in result.get('errors', []):
            print(f"  - {error}")
    
    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    main()
