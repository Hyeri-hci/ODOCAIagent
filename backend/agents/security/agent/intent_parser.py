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
            ("system", """You are an intent parser for a security analysis agent.
Parse the user's natural language request into a structured intent.

Available Actions:
- analyze_all: Complete security analysis (dependencies + vulnerabilities + license + report)
- extract_dependencies: Extract dependencies only
- scan_vulnerabilities: Scan for vulnerabilities
- check_license: Check license compliance
- generate_report: Generate report from existing data
- analyze_file: Analyze specific file(s)
- custom: Custom task

Scopes:
- full_repository: Analyze entire repository
- specific_files: Analyze specific files only
- specific_languages: Analyze specific language dependencies

Output Format:
- full_report: Complete detailed report
- summary: Brief summary
- json: JSON format
- specific_fields: Only requested fields

Return a JSON object with:
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
            ("system", """Extract parameters from the security analysis request.

Find:
- Repository: owner/repo format (e.g., "facebook/react")
- Files: Specific file names if mentioned
- Options: Any flags or settings
- Thresholds: Numeric conditions
- Focus Areas: What to focus on

Return JSON:
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
        prompt = f"""Assess the complexity of this security analysis request:

Request: "{user_request}"

Classification:
- SIMPLE: Standard repository analysis, no special conditions
- MODERATE: Some specific requirements or conditions
- COMPLEX: Multiple conditions, custom logic, or complex requirements

Answer with only: SIMPLE, MODERATE, or COMPLEX
Brief reason (one line)

Format:
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
