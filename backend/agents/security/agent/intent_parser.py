"""
Intent Parser
자연어 요청을 파싱하여 에이전트가 이해할 수 있는 구조화된 의도로 변환
"""
import json
import re
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from .state_v2 import TaskIntent


class IntentParser:
    """자연어 요청 의도 파싱기"""

    def __init__(
            self,
            llm_base_url:str,
            llm_api_key:str,
            llm_model:str,
            llm_temperature:float = 0.0,
    ):
        self.llm = ChatOpenAI(
            model=llm_model,
            api_key=llm_api_key,
            base_url=llm_base_url,
            temperature=llm_temperature
        )

        self.intent_prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 보안 분석 에이전트를 위한 의도 파서입니다.
사용자의 자연어 요청을 구조화된 의도로 변환하세요.

**중요**: 사용자가 "의존성"만 요청하면 취약점 조회를 하지 않고, "취약점"을 요청하면 취약점까지 조회합니다.

사용 가능한 액션 (4가지 핵심 타입):
1. extract_dependencies - 리포지토리 전체의 의존성만 추출 (취약점 조회 X)
2. extract_file_dependencies - 특정 파일의 의존성만 추출 (취약점 조회 X)
3. scan_vulnerabilities - 리포지토리 전체의 의존성 + 취약점 조회
4. scan_file_vulnerabilities - 특정 파일의 의존성 + 취약점 조회

기타 액션:
- analyze_all: 전체 보안 분석 (의존성 + 취약점 + 보안점수 + 리포트)
- check_license: 라이센스 준수 확인
- generate_report: 기존 데이터로 리포트 생성
- custom: 커스텀 작업

범위:
- full_repository: 전체 레포지토리 분석
- specific_files: 특정 파일만 분석
- specific_languages: 특정 언어 의존성만 분석

출력 형식:
- full_report: 전체 상세 리포트
- summary: 간단한 요약
- json: JSON 형식
- specific_fields: 요청된 필드만

**액션 선택 가이드**:
- "의존성 추출", "의존성 목록", "dependencies" 키워드만 → extract_dependencies
- "package.json의 의존성", "특정 파일" → extract_file_dependencies
- "취약점", "vulnerabilities", "CVE", "보안 이슈" → scan_vulnerabilities
- "파일의 취약점", "package.json의 보안" → scan_file_vulnerabilities

다음과 같은 JSON 객체를 반환하세요:
{{
    "primary_action": "...",
    "scope": "...",
    "target_files": [...],
    "conditions": [...],
    "output_format": "...",
    "parameters": {{...}},
    "confidence": 0.95
}}"""),
            ("user", "{user_request}")
        ])

        self.parameter_prompt = ChatPromptTemplate.from_messages([
            ("system", """보안 분석 요청에서 파라미터를 추출하세요.

찾을 것:
- Repository: owner/repo 형식 (예: "facebook/react")
- Files: 언급된 특정 파일 이름
- Options: 플래그나 설정
- Thresholds: 숫자 조건
- Focus Areas: 집중할 영역

다음 JSON을 반환하세요:
{{
    "owner": "...",
    "repo": "...",
    "files": [...],
    "thresholds": {{...}},
    "options": {{...}},
    "focus_areas": [...]
}}"""),
            ("user", "{user_request}")
        ])

    async def parse_intent(self, user_request: str) -> TaskIntent:
        """
        자연어 요청의 의도 파악

        Args:
            user_request: 사용자의 자연어 요청

        Returns:
            TaskIntent: 구조화된 의도

        Examples:
            >>> parser = IntentParser()
            >>> intent = await parser.parse_intent("facebook/react의 보안 취약점을 찾아줘")
            >>> print(intent["primary_action"])
            "scan_vulnerabilities"
        """
        try:
            # LLM 호출
            chain = self.intent_prompt | self.llm
            response = await chain.ainvoke({"user_request": user_request})

            # JSON 파싱
            content = response.content

            # JSON 추출 (마크다운 코드 블록 제거)
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            elif '```' in content:
                # 일반 코드 블록
                content = content.split('```')[1].strip()

            intent_data = json.loads(content)

            # TaskIntent 구조로 변환
            intent: TaskIntent = {
                "primary_action": intent_data.get("primary_action", "analyze_all"),
                "scope": intent_data.get("scope", "full_repository"),
                "target_files": intent_data.get("target_files", []),
                "conditions": intent_data.get("conditions", []),
                "output_format": intent_data.get("output_format", "full_report"),
                "parameters": intent_data.get("parameters", {})
            }

            return intent

        except Exception as e:
            # 파싱 실패 시 기본 의도 반환
            print(f"[IntentParser] Failed to parse intent: {e}")
            return self._get_default_intent()

    async def extract_parameters(self, user_request: str) -> Dict[str, Any]:
        """
        요청에서 파라미터 추출

        Args:
            user_request: 사용자의 자연어 요청

        Returns:
            Dict: 추출된 파라미터
        """
        try:
            chain = self.parameter_prompt | self.llm
            response = await chain.ainvoke({"user_request": user_request})

            content = response.content

            # JSON 추출
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            elif '```' in content:
                content = content.split('```')[1].strip()

            params = json.loads(content)
            return params

        except Exception as e:
            print(f"[IntentParser] Failed to extract parameters: {e}")
            return {}

    def _get_default_intent(self) -> TaskIntent:
        """기본 의도 반환 (파싱 실패 시)"""
        return TaskIntent(
            primary_action="analyze_all",
            scope="full_repository",
            target_files=[],
            conditions=[],
            output_format="full_report",
            parameters={}
        )

    def parse_repository_info(self, user_request: str) -> tuple[Optional[str], Optional[str]]:
        """
        요청에서 레포지토리 정보 추출 (정규식)

        Args:
            user_request: 사용자 요청

        Returns:
            (owner, repo) 튜플
        """
        # 패턴: owner/repo 형식
        pattern = r'([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)'
        match = re.search(pattern, user_request)

        if match:
            return match.group(1), match.group(2)

        return None, None

    async def assess_complexity(self, user_request: str) -> str:
        """
        요청의 복잡도 평가

        Args:
            user_request: 사용자 요청

        Returns:
            "simple" | "moderate" | "complex"
        """
        prompt = f"""이 보안 분석 요청의 복잡도를 평가하세요:

요청: "{user_request}"

분류:
- SIMPLE: 표준 레포지토리 분석, 특별한 조건 없음
- MODERATE: 일부 특정 요구사항이나 조건 있음
- COMPLEX: 여러 조건, 커스텀 로직, 복잡한 요구사항

다음 중 하나만 답하세요: SIMPLE, MODERATE, COMPLEX
간단한 이유 (한 줄)

형식:
CLASSIFICATION: [SIMPLE|MODERATE|COMPLEX]
REASON: ...
"""

        try:
            response = await self.llm.ainvoke(prompt)
            content = response.content

            # 분류 추출
            if "SIMPLE" in content.upper():
                return "simple"
            elif "COMPLEX" in content.upper():
                return "complex"
            else:
                return "moderate"

        except Exception as e:
            print(f"[IntentParser] Failed to assess complexity: {e}")
            # 기본값은 moderate
            return "moderate"


# 편의 함수
async def parse_user_request(
    user_request: str,
    llm: Optional[ChatOpenAI] = None
) -> tuple[TaskIntent, Dict[str, Any]]:
    """
    사용자 요청을 파싱하여 의도와 파라미터 반환

    Args:
        user_request: 사용자의 자연어 요청
        llm: LLM 인스턴스 (선택)

    Returns:
        (intent, parameters) 튜플
    """
    parser = IntentParser(llm)
    intent = await parser.parse_intent(user_request)
    parameters = await parser.extract_parameters(user_request)
    return intent, parameters
