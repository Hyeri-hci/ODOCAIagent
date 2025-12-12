"""ReAct 패턴 기반 채팅 에이전트."""
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import json
import re
import logging

logger = logging.getLogger(__name__)


THINK_PROMPT = """당신은 Claude처럼 동작하는 코드 분석 AI입니다.

## 역할
사용자 질문에 답하기 위해 필요한 정보를 능동적으로 수집하고,
수집한 정보를 바탕으로 정확하고 상세한 답변을 생성합니다.

## 컨텍스트
- 저장소: {owner}/{repo}
- 질문: {user_message}
- 수집된 정보:
{collected_info}
- 이전 추론:
{previous_thoughts}

## 도구
{tool_list}

## 도구 사용 예시
- README 읽기: {{"tool": "read_file", "parameters": {{"path": "README.md"}}}}
- 디렉토리 구조: {{"tool": "get_directory_structure", "parameters": {{}}}}
- 코드 검색: {{"tool": "search_codebase", "parameters": {{"query": "검색어"}}}}

## 사고 프로세스
1. 질문 분석: 무엇을 알아야 하는가?
2. 정보 격차: 현재 모르는 것은?
3. 도구 선택: 어떤 도구로 정보를 얻을 수 있는가?
4. 종료 판단: 충분한 정보가 모였는가?

## 중요 규칙
- 저장소 정보를 물어보면 먼저 README.md를 읽어라
- 불필요한 도구 호출 금지
- 충분한 정보가 있으면 바로 응답 준비

## 출력 JSON
```json
{{
  "thought": "현재 상황 및 다음 행동 근거",
  "knowledge_gap": "아직 모르는 것 (없으면 null)",
  "ready_to_respond": false,
  "tool": "도구명",
  "parameters": {{"path": "파일경로"}},
  "confidence": 0.0-1.0
}}
```

ready_to_respond가 true일 때:
```json
{{
  "thought": "최종 정리",
  "ready_to_respond": true,
  "confidence": 0.9,
  "response_outline": ["답변 구조 개요"]
}}
```"""


FINALIZE_PROMPT = """당신은 코드 분석 AI입니다. 수집한 정보를 바탕으로 사용자 질문에 답변합니다.

## 원본 질문
{user_message}

## 수집된 정보 (반드시 활용)
{collected_info}

## 추론 과정
{reasoning_trace}

## 답변 지침
1. 수집된 정보를 기반으로 구체적으로 답변
2. README 내용이 있으면 프로젝트 목적, 주요 기능, 사용법 요약
3. 마크다운 포맷 사용 (헤더, 코드 블록, 목록 등)
4. "정보를 찾을 수 없습니다"라고 하지 말고, 수집된 정보 활용
5. 저장소 분석이나 기여 가이드 생성 제안

수집된 정보를 활용하여 상세하고 유용한 답변을 작성하세요."""


class ReactChatAgent:
    """ReAct 패턴 기반 채팅 에이전트"""
    
    def __init__(
        self,
        llm: ChatOpenAI,
        tools: Dict[str, Any],
        owner: str,
        repo: str,
        max_iterations: int = 5
    ):
        self.llm = llm
        self.tools = tools
        self.owner = owner
        self.repo = repo
        self.max_iterations = max_iterations
        
        self.think_prompt = ChatPromptTemplate.from_messages([
            ("system", THINK_PROMPT),
            ("user", "다음에 무엇을 해야 하나요?")
        ])
        
        self.finalize_prompt = ChatPromptTemplate.from_messages([
            ("system", FINALIZE_PROMPT),
            ("user", "위 정보를 바탕으로 답변을 작성하세요.")
        ])
    
    async def generate_response(self, message: str, context: Dict[str, Any] = None) -> tuple:
        """ReAct 사이클로 응답 생성. (응답, 수집정보) 튜플 반환."""
        state = {
            "user_message": message,
            "context": context or {},
            "collected_info": [],
            "thoughts": [],
            "iteration": 0
        }
        
        logger.info(f"[ReactChat] Starting for: {message[:50]}...")
        
        for i in range(self.max_iterations):
            state["iteration"] = i + 1
            
            # THINK
            thought = await self._think(state)
            state["thoughts"].append(thought)
            
            if thought.get("ready_to_respond"):
                logger.info(f"[ReactChat] Ready to respond after {i+1} iterations")
                break
            
            # ACT
            tool_name = thought.get("tool")
            if not tool_name or tool_name not in self.tools:
                logger.warning(f"[ReactChat] Invalid tool: {tool_name}")
                break
            
            result = await self._act(tool_name, thought.get("parameters", {}))
            
            # OBSERVE
            state["collected_info"].append({
                "tool": tool_name,
                "result": result
            })
            
            logger.info(f"[ReactChat] Iteration {i+1}: {tool_name} -> {'success' if result.get('success') else 'failed'}")
        
        # FINALIZE
        answer = await self._finalize(state)
        
        # 수집된 정보도 함께 반환 (메타인지)
        return answer, state["collected_info"]
    
    async def _think(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """사고 단계"""
        from .chat_tools import get_tool_descriptions
        
        collected_str = self._format_collected_info(state["collected_info"])
        thoughts_str = self._format_thoughts(state["thoughts"])
        
        try:
            chain = self.think_prompt | self.llm
            response = await chain.ainvoke({
                "owner": self.owner,
                "repo": self.repo,
                "user_message": state["user_message"],
                "collected_info": collected_str or "(없음)",
                "previous_thoughts": thoughts_str or "(없음)",
                "tool_list": get_tool_descriptions()
            })
            
            return self._extract_json(response.content)
        except Exception as e:
            logger.warning(f"[ReactChat] Think failed: {e}")
            return {"ready_to_respond": True, "thought": "정보 수집 실패"}
    
    async def _act(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """도구 실행"""
        tool = self.tools.get(tool_name)
        if not tool:
            return {"success": False, "error": f"Tool not found: {tool_name}"}
        
        try:
            # owner/repo 자동 주입
            params = {"owner": self.owner, "repo": self.repo, **parameters}
            
            # read_file 호출 시 path 기본값 설정
            if tool_name == "read_file" and "path" not in params:
                params["path"] = "README.md"
                logger.info(f"[ReactChat] Using default path: README.md")
            
            result = await tool(**params)
            return result
        except Exception as e:
            logger.warning(f"[ReactChat] Act failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _finalize(self, state: Dict[str, Any]) -> str:
        """최종 응답 생성"""
        collected_str = self._format_collected_info(state["collected_info"])
        reasoning_str = self._format_thoughts(state["thoughts"])
        
        try:
            chain = self.finalize_prompt | self.llm
            response = await chain.ainvoke({
                "user_message": state["user_message"],
                "collected_info": collected_str or "(수집된 정보 없음)",
                "reasoning_trace": reasoning_str or "(추론 없음)"
            })
            return response.content
        except Exception as e:
            logger.warning(f"[ReactChat] Finalize failed: {e}")
            return "응답 생성 중 오류가 발생했습니다. 다시 시도해주세요."
    
    def _format_collected_info(self, info_list: List[Dict]) -> str:
        if not info_list:
            return ""
        
        lines = []
        for item in info_list:
            tool = item.get("tool", "unknown")
            result = item.get("result", {})
            
            if result.get("success"):
                # 주요 정보만 추출
                summary = self._summarize_result(result)
                lines.append(f"- [{tool}] {summary}")
            else:
                lines.append(f"- [{tool}] 실패: {result.get('error', 'unknown')}")
        
        return "\n".join(lines)
    
    def _format_thoughts(self, thoughts: List[Dict]) -> str:
        if not thoughts:
            return ""
        
        lines = []
        for i, t in enumerate(thoughts, 1):
            thought_text = t.get("thought", "")[:200]
            lines.append(f"{i}. {thought_text}")
        
        return "\n".join(lines)
    
    def _summarize_result(self, result: Dict[str, Any]) -> str:
        """결과 요약 - 파일 내용은 최대 2000자까지 포함"""
        if "content" in result:
            content = result["content"]
            # README 등 파일 내용은 최대 2000자까지 포함
            if len(content) > 2000:
                return f"파일 내용 (처음 2000자):\n{content[:2000]}..."
            return f"파일 내용:\n{content}"
        if "items" in result:
            items = result["items"]
            summary = f"{len(items)}개 항목"
            if items:
                summary += ": " + ", ".join([str(i.get("path", i)) for i in items[:5]])
            return summary
        if "results" in result:
            return f"{len(result['results'])}개 검색 결과"
        if "issues" in result:
            return f"{len(result['issues'])}개 이슈"
        if "health_score" in result:
            return f"건강점수: {result['health_score']}"
        if "security_score" in result:
            return f"보안점수: {result['security_score']}"
        
        return json.dumps(result, ensure_ascii=False)[:500]
    
    def _extract_json(self, content: str) -> Dict[str, Any]:
        """LLM 응답에서 JSON 추출"""
        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        elif '```' in content:
            parts = content.split('```')
            if len(parts) >= 2:
                content = parts[1].strip()
        
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"ready_to_respond": True, "thought": content[:200]}


def needs_react_response(message: str, context: Dict[str, Any] = None) -> bool:
    """
    ReAct 응답이 필요한지 판단
    
    저장소 컨텍스트가 있고 **저장소 관련** 구체적인 질문이면 ReAct로 정보 수집.
    일반 지식 질문이나 시스템 질문은 단순 LLM으로 처리.
    """
    if context is None:
        context = {}
    
    msg_lower = message.lower()
    
    # 저장소 컨텍스트 확인
    repo_info = context.get("last_mentioned_repo", {})
    has_repo = bool(repo_info.get("owner") and repo_info.get("repo"))
    
    # === 1. 일반 지식 질문 필터 (저장소 검색 불필요) ===
    general_knowledge_patterns = [
        "이 뭐", "뭐야", "무엇인가", "무엇이야", "란 뭐", "이란",  # 정의 질문
        "odoc", "ossdoctor", "oss doctor",  # 시스템 관련 질문
        "너는", "넌", "당신",  # AI 관련 질문
        "어떤 ai", "gpt", "claude", "llm",  # AI 모델 질문
    ]
    
    if any(pattern in msg_lower for pattern in general_knowledge_patterns):
        # 저장소명이 함께 언급되지 않은 일반 질문
        repo_in_message = repo_info.get("repo", "").lower() if repo_info else ""
        if not repo_in_message or repo_in_message not in msg_lower:
            logger.info(f"[needs_react] General knowledge question, skip ReAct: {message[:30]}")
            return False
    
    # === 2. 이미 캐시된 정보로 답변 가능한 경우 ===
    cached_data_keywords = ["점수", "등급", "결과", "요약", "몇", "얼마", "몇점", "건강도"]
    if any(kw in msg_lower for kw in cached_data_keywords):
        # 진단 결과가 이미 있으면 캐시 사용
        if context.get("diagnosis_result") or context.get("accumulated_context", {}).get("diagnosis_result"):
            logger.info(f"[needs_react] Cached diagnosis available: {message[:30]}")
            return False
    
    # === 3. 구조 요청은 contributor 에이전트 또는 캐시 사용 ===
    structure_keywords = ["구조", "structure", "트리", "tree", "폴더", "folder"]
    if any(kw in msg_lower for kw in structure_keywords):
        # 구조는 contributor 에이전트가 담당, ReAct가 아님
        logger.info(f"[needs_react] Structure request, handled by contributor: {message[:30]}")
        return False
    
    # === 4. ReAct가 필요한 저장소 관련 질문 ===
    # 저장소 파일/코드 탐색이 필요한 경우만
    react_keywords = [
        # 파일 탐색
        "파일", "코드", "소스", "모듈", "클래스", "함수",
        # 특정 정보 검색
        "찾아", "검색", "어디에", "위치",
        # 설정/개발 환경 (저장소 파일 참조 필요)
        "설치 방법", "빌드 방법", "설정 방법", "환경 설정",
        # 기여 관련 (CONTRIBUTING.md 등 참조)
        "기여 방법", "pr 방법", "이슈 작성"
    ]
    
    # 저장소 컨텍스트 + ReAct 키워드가 있어야 ReAct 사용
    if has_repo and any(kw in msg_lower for kw in react_keywords):
        logger.info(f"[needs_react] Repo-specific question with ReAct keyword: {message[:30]}")
        return True
    
    # === 5. 기본: 단순 LLM으로 처리 ===
    logger.info(f"[needs_react] Fallback to simple LLM: {message[:30]}")
    return False
