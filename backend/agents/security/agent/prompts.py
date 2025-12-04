"""
프롬프트 템플릿
"""

PLANNING_PROMPT = """당신은 보안 분석 전문가입니다. GitHub 레포지토리의 보안 분석 계획을 수립하세요.

레포지토리: {owner}/{repository}

현재 상황:
{current_situation}

사용 가능한 도구:
- analyze_dependencies: 의존성 분석
- calculate_security_score: 보안 점수 계산
- suggest_improvements: 개선 사항 제안
- generate_full_report: 전체 레포트 생성

다음 형식으로 계획을 작성하세요 (각 항목은 한 줄로):
1. [작업 설명]
2. [작업 설명]
...

계획:"""

VALIDATION_PROMPT = """다음 계획이 보안 분석에 적절한지 검증하세요.

계획:
{plan}

검증 기준:
1. 의존성 분석이 포함되어 있는가?
2. 보안 점수 계산이 포함되어 있는가?
3. 레포트 생성이 포함되어 있는가?
4. 논리적 순서가 올바른가?

응답 형식:
VALID 또는 INVALID
피드백: [구체적인 피드백]

응답:"""

REACT_AGENT_PROMPT = """당신은 보안 분석 에이전트입니다. 주어진 작업을 수행하세요.

현재 작업: {current_task}
진행 상황: {progress}

사용 가능한 도구:
{tools}

Think-Act-Observe 패턴을 따르세요:

Thought: 무엇을 해야 하는지 생각합니다.
Action: 적절한 도구를 선택하고 실행합니다.
Observation: 결과를 관찰하고 분석합니다.

시작하세요:"""

REFLECTION_PROMPT = """최근 실행 결과를 분석하고 다음 행동을 결정하세요.

최근 결과:
{last_result}

현재 진행 상황:
- 완료된 단계: {iteration}/{total_steps}
- 의존성 분석: {dependencies_status}
- 보안 점수: {security_score_status}

다음 중 하나를 선택하세요:
1. CONTINUE: 계획대로 계속 진행
2. COMPLETE: 모든 작업 완료
3. REPLAN: 계획 재수립 필요

선택과 이유를 설명하세요:

선택:"""

REPORT_GENERATION_PROMPT = """보안 분석 결과를 바탕으로 최종 레포트를 생성하세요.

분석 결과:
- 레포지토리: {owner}/{repository}
- 의존성 개수: {dependency_count}
- 보안 점수: {security_score}
- 보안 등급: {security_grade}

레포트는 다음을 포함해야 합니다:
1. Executive Summary
2. Dependency Analysis
3. Security Assessment
4. Recommendations

레포트를 생성하세요:"""
