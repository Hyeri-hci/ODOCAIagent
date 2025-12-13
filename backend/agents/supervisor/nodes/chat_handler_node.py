"""
Chat Handler Node
Supervisor에서 채팅 응답을 처리하는 노드입니다.
"""

import logging
import asyncio
from typing import Dict, Any

from backend.agents.supervisor.models import SupervisorState
from backend.agents.supervisor.nodes.react_chat_agent import ReactChatAgent, needs_react_response
from backend.agents.supervisor.nodes.chat_tools import get_chat_tools
from backend.common.config import LLM_MODEL_NAME, LLM_API_BASE, LLM_API_KEY, LLM_TEMPERATURE
from langchain_openai import ChatOpenAI
from backend.llm.factory import fetch_llm_client
from backend.llm.base import ChatRequest, ChatMessage

logger = logging.getLogger(__name__)

async def chat_response_node(state: SupervisorState) -> Dict[str, Any]:
    """
    일반 채팅 응답 (ReAct + 메타인지 통합)
    
    복잡한 질문은 ReAct 에이전트 사용, 단순 질문은 직접 LLM 호출.
    """
    logger.info("Generating chat response")
    
    user_message = state.get("user_message") or ""
    accumulated_context = state.get("accumulated_context", {})
    
    # 저장소 정보 가져오기
    repo_info = accumulated_context.get("last_mentioned_repo", {})
    owner = repo_info.get("owner") or state.get("owner") or "unknown"
    repo = repo_info.get("repo") or state.get("repo") or "unknown"
    
    logger.info(f"[Chat] message='{user_message[:50] if user_message else ''}...', repo={owner}/{repo}")
    
    # user_message가 비어있으면 기본 응답
    if not user_message.strip():
        answer = "안녕하세요! 저장소 분석이나 질문이 있으시면 말씀해주세요."
        return {
            "agent_result": {"type": "chat", "response": answer},
            "final_answer": answer
        }
    
    # ReAct 응답 필요 여부 판단
    needs_react = needs_react_response(user_message, accumulated_context)
    logger.info(f"[Chat] needs_react={needs_react}")
    
    if needs_react:
        logger.info("[Chat] Using ReAct agent for complex question")
        try:
            llm = ChatOpenAI(
                model=LLM_MODEL_NAME,
                base_url=LLM_API_BASE,
                api_key=LLM_API_KEY,
                temperature=float(LLM_TEMPERATURE) if LLM_TEMPERATURE else 0.7
            )
            
            tools = get_chat_tools()
            
            agent = ReactChatAgent(
                llm=llm,
                tools=tools,
                owner=owner,
                repo=repo,
                max_iterations=5
            )
            
            # ReAct 에이전트로 응답 생성
            answer, collected_info = await agent.generate_response(
                user_message,
                context={
                    "accumulated_context": accumulated_context,
                    "repo_info": repo_info
                }
            )
            
            # 수집된 정보에서 결과 추출 (메타인지)
            security_result = None
            diagnosis_result = None
            sources = []
            
            for info in collected_info:
                tool_name = info.get("tool", "")
                result = info.get("result", {})
                
                # 소스 수집
                if result.get("success"):
                    if tool_name == "read_file":
                        file_path = info.get("parameters", {}).get("path", "")
                        if file_path:
                            sources.append({
                                "type": "file",
                                "title": file_path,
                                "url": f"https://github.com/{owner}/{repo}/blob/main/{file_path}"
                            })
                    
                    if tool_name == "call_security_agent" and result.get("security_score") is not None:
                        security_result = {
                            "security_score": result.get("security_score"),
                            "security_grade": result.get("security_grade"),
                            "risk_level": result.get("risk_level", "low"),
                            "vulnerability_count": result.get("vulnerability_count", 0),
                        }
                        logger.info(f"[Chat] Security result extracted: score={security_result.get('security_score')}")
                    
                    elif tool_name == "call_diagnosis_agent" and result.get("health_score") is not None:
                        diagnosis_result = result
                        logger.info(f"[Chat] Diagnosis result extracted: score={diagnosis_result.get('health_score')}")
            
            logger.info(f"[Chat] ReAct completed with {len(collected_info)} tool calls, {len(sources)} sources")
            
            result_data = {
                "agent_result": {
                    "type": "chat",
                    "response": answer,
                    "sources": sources,
                    "tool_calls": len(collected_info),
                },
                "final_answer": answer,
            }
            
            if security_result:
                result_data["security_result"] = security_result
            if diagnosis_result:
                result_data["diagnosis_result"] = diagnosis_result
            
            return result_data
            
        except Exception as e:
            logger.warning(f"[Chat] ReAct failed, falling back to direct LLM: {e}")
    
    # 기존 방식 (단순 질문 또는 ReAct 실패 시)
    try:
        # 시스템 프롬프트 구성 (상세한 ODOC 소개 포함)
        system_prompt = f"""당신은 ODOC(Open-source Doctor, 오픈소스 닥터) AI 어시스턴트입니다.

## ODOC이란?
ODOC은 GitHub와 같은 오픈소스 저장소를 분석하고 진단해주는 AI 기반 도구입니다.
주요 기능은 다음과 같습니다:

### 1. 저장소 건강도 진단 (Project Diagnosis)
- **종합 점수 제공**: 전체적인 저장소 건강도를 0-100점으로 평가
- **세부 지표 분석**: 활동성, 문서화, 코드 구조 등을 종합하여 건강도 진단
- **개선 권장사항**: README, CONTRIBUTING.md, 테스트 커버리지 등 개선점 제안
- **상세 메트릭**: 최근 커밋 수, 기여자 수, 이슈/PR 응답 시간 등

### 2. 보안 취약점 분석 (Security Analysis)
- **의존성 스캔**: 코드나 의존성(dependencies)에서 보안상 문제가 될 수 있는 부분을 찾아냄
- **CVE 검색**: NVD 데이터베이스에서 알려진 취약점 확인
- **위험도 평가**: Critical, High, Medium, Low 등급 분류

### 3. 온보딩 가이드 생성 (Onboarding Guide)
- **학습 플랜**: 신규 기여자가 프로젝트에 쉽게 참여할 수 있도록 온보딩 가이드를 자동으로 만들어줌
- **기여 체크리스트**: PR 제출 전 확인사항
- **Good First Issue**: 초보자에게 적합한 이슈 추천

### 4. 코드 구조 시각화 (Structure Visualization)
- **트리 구조**: 프로젝트의 코드 구조를 시각적으로 표현해 이해를 돕습니다
- **다이어그램**: 주요 디렉토리 및 파일 관계 시각화

## 목표
ossdoctor는 오픈소스 프로젝트의 품질을 높이고, 기여자들이 더 쉽게 참여할 수 있도록 돕는 것을 목표로 하고 있습니다.

## 현재 컨텍스트
- 분석 중인 저장소: {owner}/{repo if repo else '(없음)'}

## 응답 지침
1. ODOC/ossdoctor에 대한 질문 → 위 상세 소개를 바탕으로 **구체적이고 친절하게** 설명
2. 저장소 관련 질문 → 해당 저장소 정보 기반으로 답변
3. 기능 안내 질문 → 각 기능 설명과 함께 사용법 안내
4. 마크다운 형식(헤더, 목록, 굵게 등)을 활용하여 가독성 있게 답변

상세하고 친절하게 답변해주세요."""
        
        llm = fetch_llm_client()
        
        request = ChatRequest(
            messages=[
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=user_message)
            ]
        )
        
        # 비동기 실행
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, llm.chat, request)
        answer = response.content
        
    except Exception as e:
        logger.warning(f"[Chat] LLM call failed: {e}")
        answer = f"질문을 받았습니다: {user_message}\n\n저장소 정보가 필요한 경우 owner와 repo를 지정해주세요."
    
    return {
        "agent_result": {"type": "chat", "response": answer},
        "final_answer": answer
    }
