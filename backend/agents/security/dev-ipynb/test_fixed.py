# Security Agent V2 테스트 코드 (수정됨)
# Jupyter Notebook에서 실행하세요

import os
from dotenv import load_dotenv
from backend.agents.security.agent.security_agent_v2 import SecurityAgentV2

load_dotenv()

# 에이전트 생성 (파라미터 수정)
agent = SecurityAgentV2(
    llm_base_url=os.getenv("LLM_BASE_URL"),
    llm_api_key=os.getenv("LLM_API_KEY"),
    llm_model=os.getenv("LLM_MODEL"),
    llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),  # float로 변환
    execution_mode="intelligent"
)

# Jupyter에서는 await 직접 사용 가능
result = await agent.analyze(
    user_request="facebook/react의 의존성들을 찾아줘"
)

# 결과 확인
print("\n" + "="*70)
print("분석 결과")
print("="*70)
print(f"성공 여부: {result.get('success', False)}")
print(f"의존성 개수: {result.get('results', {}).get('dependencies', {}).get('total', 0)}")
print(f"취약점 개수: {result.get('results', {}).get('vulnerabilities', {}).get('total', 0)}")
print(f"보안 등급: {result.get('results', {}).get('security_grade', 'N/A')}")

# 상세 정보
if result.get('results', {}).get('dependencies'):
    print("\n발견된 의존성:")
    deps = result['results']['dependencies'].get('details', {})
    for ecosystem, packages in deps.items():
        print(f"  {ecosystem}: {len(packages)}개")
