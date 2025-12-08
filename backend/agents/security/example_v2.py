"""
Security Agent V2 사용 예제
"""
import asyncio
from agent.security_agent_v2 import SecurityAgentV2, quick_analysis


async def example_1_full_analysis():
    """예제 1: 전체 보안 분석"""
    print("\n" + "="*70)
    print("Example 1: Full Security Analysis")
    print("="*70)

    agent = SecurityAgentV2(execution_mode="intelligent")

    result = await agent.analyze(
        user_request="facebook/react 레포지토리의 전체 보안 분석을 수행해줘",
        github_token=None  # 실제로는 토큰 필요
    )

    print("\n결과:")
    print(f"성공: {result.get('success')}")
    print(f"의존성: {result.get('results', {}).get('dependencies', {}).get('total')}")
    print(f"취약점: {result.get('results', {}).get('vulnerabilities', {}).get('total')}")
    print(f"보안 등급: {result.get('results', {}).get('security_grade')}")


async def example_2_dependency_only():
    """예제 2: 의존성만 추출"""
    print("\n" + "="*70)
    print("Example 2: Extract Dependencies Only")
    print("="*70)

    agent = SecurityAgentV2(execution_mode="auto")

    result = await agent.analyze(
        user_request="torvalds/linux의 의존성만 추출해줘"
    )

    print("\n결과:")
    print(f"의존성 개수: {result.get('results', {}).get('dependencies', {}).get('total')}")


async def example_3_vulnerability_scan():
    """예제 3: 취약점 스캔"""
    print("\n" + "="*70)
    print("Example 3: Vulnerability Scan")
    print("="*70)

    agent = SecurityAgentV2(execution_mode="intelligent")

    result = await agent.analyze(
        user_request="django/django에서 심각도가 HIGH 이상인 취약점을 찾아줘"
    )

    print("\n결과:")
    vulns = result.get('results', {}).get('vulnerabilities', {})
    print(f"전체 취약점: {vulns.get('total')}")
    print(f"Critical: {vulns.get('critical')}")
    print(f"High: {vulns.get('high')}")


async def example_4_quick_analysis():
    """예제 4: 빠른 분석 (편의 함수)"""
    print("\n" + "="*70)
    print("Example 4: Quick Analysis")
    print("="*70)

    result = await quick_analysis(
        user_request="numpy/numpy 보안 분석",
        mode="auto"
    )

    print("\n결과:")
    print(f"성공: {result.get('success')}")


async def example_5_specific_files():
    """예제 5: 특정 파일만 분석"""
    print("\n" + "="*70)
    print("Example 5: Analyze Specific Files")
    print("="*70)

    agent = SecurityAgentV2()

    result = await agent.analyze(
        user_request="facebook/react의 package.json과 package-lock.json만 분석해줘"
    )

    print("\n결과:")
    print(f"분석된 파일: {result.get('intent', {}).get('target_files')}")


async def example_6_custom_request():
    """예제 6: 커스텀 요청"""
    print("\n" + "="*70)
    print("Example 6: Custom Request")
    print("="*70)

    agent = SecurityAgentV2(
        execution_mode="intelligent",
        max_iterations=30,  # 복잡한 작업에 더 많은 반복 허용
        enable_reflection=True  # 메타인지 활성화
    )

    result = await agent.analyze(
        user_request="""
        microsoft/typescript 레포지토리를 분석하는데,
        1. 의존성 중 deprecated된 패키지 찾기
        2. 라이센스 위반 여부 체크
        3. 보안 점수 계산
        4. 상세 보고서 생성
        """
    )

    print("\n결과:")
    print(result.get('report', 'No report generated'))


async def example_7_fast_mode():
    """예제 7: Fast 모드 (규칙 기반)"""
    print("\n" + "="*70)
    print("Example 7: Fast Mode (Rule-Based)")
    print("="*70)

    agent = SecurityAgentV2(execution_mode="fast")

    result = await agent.analyze_simple(
        primary_action="extract_dependencies",
        owner="expressjs",
        repository="express"
    )

    print("\n결과:")
    print(f"의존성: {result.get('results', {}).get('dependencies', {}).get('total')}")


async def main():
    """모든 예제 실행"""
    examples = [
        ("Full Analysis", example_1_full_analysis),
        ("Dependency Only", example_2_dependency_only),
        ("Vulnerability Scan", example_3_vulnerability_scan),
        ("Quick Analysis", example_4_quick_analysis),
        ("Specific Files", example_5_specific_files),
        ("Custom Request", example_6_custom_request),
        ("Fast Mode", example_7_fast_mode)
    ]

    print("\n" + "="*70)
    print("Security Agent V2 - Examples")
    print("="*70)

    for name, example_func in examples:
        try:
            print(f"\n\nRunning: {name}")
            await example_func()
        except Exception as e:
            print(f"Error in {name}: {e}")

    print("\n" + "="*70)
    print("All examples completed")
    print("="*70)


if __name__ == "__main__":
    # 특정 예제만 실행
    asyncio.run(example_1_full_analysis())

    # 또는 모든 예제 실행
    # asyncio.run(main())
