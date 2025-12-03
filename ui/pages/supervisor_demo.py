"""
Supervisor Agent 데모 페이지 (Refactored)

자연어 질문을 입력하면:
1. 간단한 파싱으로 대상 리포지토리 식별
2. Supervisor Agent 실행 (Diagnosis)
3. 결과 표시
"""
from __future__ import annotations

import base64
import os
import sys
import time
import uuid
import re
import logging
from typing import Any, Dict, Optional
from dataclasses import asdict, is_dataclass

# 프로젝트 루트 추가
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage

# New Backend Imports
from backend.agents.supervisor.graph import get_supervisor_graph
from backend.core.models import DiagnosisCoreResult
from backend.common.config import GITHUB_TOKEN

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Supervisor Agent Demo",
    layout="wide",
)

# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------

def parse_query(query: str) -> Dict[str, str]:
    """사용자 쿼리에서 owner/repo 추출 (간이 파서)."""
    # 1. URL 패턴
    url_match = re.search(r"github\.com/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)", query)
    if url_match:
        return {"owner": url_match.group(1), "repo": url_match.group(2)}
    
    # 2. owner/repo 패턴 (공백 없이)
    simple_match = re.search(r"\b([a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)\b", query)
    if simple_match:
        return {"owner": simple_match.group(1), "repo": simple_match.group(2)}
    
    return {}

def is_greeting(query: str) -> bool:
    """간단한 인사말 감지."""
    greetings = ["안녕", "반가워", "hi", "hello", "hey", "help", "도움말"]
    return any(g in query.lower() for g in greetings)

def to_dict(obj: Any) -> Any:
    """Dataclass를 dict로 변환 (UI 호환성)."""
    if is_dataclass(obj):
        return asdict(obj)
    return obj

# -------------------------------------------------------------------------
# Graph Visualization (Updated for New Architecture)
# -------------------------------------------------------------------------

def render_graph_visualization(task_type: str):
    """Mermaid.ink API로 그래프 시각화."""
    
    # New Simplified Graph Structure
    mermaid_code = f'''flowchart TD
    subgraph Input
        START((Start))
    end
    
    subgraph Supervisor
        ROUTER[Router<br/>{task_type}]
    end
    
    subgraph Agents
        DIAG[DiagnosisAgent]
        SEC[SecurityAgent]
    end
    
    subgraph Output
        END((End))
    end
    
    START --> ROUTER
    '''
    
    if task_type == "diagnosis":
        mermaid_code += '''
    ROUTER --> DIAG
    DIAG --> END
    style DIAG fill:#4CAF50,stroke:#333,stroke-width:2px,color:#fff
    '''
    elif task_type == "security":
        mermaid_code += '''
    ROUTER --> SEC
    SEC --> END
    style SEC fill:#FF9800,stroke:#333,stroke-width:2px,color:#fff
    '''
    else:
        mermaid_code += '''
    ROUTER --> DIAG
    DIAG --> SEC
    SEC --> END
    '''

    mermaid_code += '''
    style START fill:#9C27B0,stroke:#333,stroke-width:2px,color:#fff
    style ROUTER fill:#2196F3,stroke:#333,stroke-width:2px,color:#fff
    style END fill:#E91E63,stroke:#333,stroke-width:2px,color:#fff
    '''
    
    mermaid_encoded = base64.urlsafe_b64encode(mermaid_code.encode()).decode()
    img_url = f"https://mermaid.ink/img/{mermaid_encoded}?bgColor=white"
    
    st.sidebar.image(img_url, caption="Supervisor Execution Path", use_container_width=True)


# -------------------------------------------------------------------------
# Session State
# -------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = uuid.uuid4().hex

# -------------------------------------------------------------------------
# Main UI
# -------------------------------------------------------------------------

st.title("Supervisor Agent Demo (Refactored)")
st.caption("새로운 아키텍처(Pure Python Core + LangGraph)가 적용된 데모입니다.")

if not GITHUB_TOKEN:
    st.warning("⚠️ GITHUB_TOKEN이 설정되지 않았습니다. API 호출 제한이 발생할 수 있습니다.")

with st.sidebar:
    st.header("설정")
    if st.button("대화 초기화"):
        st.session_state.messages = []
        st.rerun()
    
    st.divider()
    st.markdown("### Graph Visualization")
    # 그래프는 실행 후 업데이트되므로 placeholder 사용 가능하지만, 
    # 여기서는 가장 최근 실행 기준으로 그리기 위해 session_state 활용 가능.
    # 현재는 실행 시점에 그리는 함수 호출.

# 채팅 히스토리 표시
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("details"):
            with st.expander("상세 결과"):
                st.json(msg["details"])
        if msg.get("error"):
            st.error(msg["error"])

# 입력 처리
prompt = st.chat_input("GitHub 저장소를 입력하세요 (예: Hyeri-hci/ODOCAIagent 분석해줘)")

if prompt:
    # 1. 사용자 메시지 표시
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. 파싱 및 상태 구성
    parsed = parse_query(prompt)
    owner = parsed.get("owner")
    repo = parsed.get("repo")
    
    if not owner or not repo:
        # 인사말 처리 또는 에러 메시지
        if is_greeting(prompt):
            response_msg = "안녕하세요! 분석하고 싶은 GitHub 저장소 주소나 'owner/repo'를 알려주세요."
        else:
            response_msg = "저장소 정보를 찾을 수 없습니다. 'owner/repo' 형식으로 입력해주세요."
        
        st.session_state.messages.append({"role": "assistant", "content": response_msg})
        with st.chat_message("assistant"):
            st.markdown(response_msg)
    else:
        with st.chat_message("assistant"):
            status_placeholder = st.empty()
            status_placeholder.caption(f"🚀 분석 시작: {owner}/{repo}")
            
            try:
                # 그래프 초기화
                graph = get_supervisor_graph()
                
                initial_state = {
                    "messages": [HumanMessage(content=prompt)],
                    "owner": owner,
                    "repo": repo,
                    "repo_ref": "HEAD",
                    "repo_id": f"{owner}/{repo}",
                    "task_type": "diagnosis", # 기본값
                    "run_security": False,
                    "run_recommendation": False,
                }
                
                # 실행
                config = {"configurable": {"thread_id": st.session_state.session_id}}
                result = graph.invoke(initial_state, config=config)
                
                # 결과 처리
                diagnosis_result = result.get("diagnosis_result")
                error_message = result.get("error_message")
                
                # 에러 확인 (DiagnosisAgent 내부 에러 포함)
                if not error_message and isinstance(diagnosis_result, dict) and diagnosis_result.get("error_message"):
                     error_message = diagnosis_result.get("error_message")

                diag_dict = to_dict(diagnosis_result) if diagnosis_result else {}
                
                # LLM 요약 찾기 (마지막 AIMessage)
                messages = result.get("messages", [])
                llm_response = "분석이 완료되었으나 요약을 생성하지 못했습니다."
                if messages and isinstance(messages[-1], AIMessage):
                    llm_response = messages[-1].content
                elif messages and isinstance(messages[-1], dict) and messages[-1].get("type") == "ai": 
                     llm_response = messages[-1].get("content")

                status_placeholder.empty()
                
                if error_message:
                    st.error(f"분석 중 오류가 발생했습니다: {error_message}")
                    llm_response = f"오류가 발생했습니다: {error_message}"
                else:
                    # 응답 표시
                    st.markdown(llm_response)
                    
                    # 상세 정보 표시
                    with st.expander("분석 상세 결과"):
                        st.subheader("Scores")
                        if diag_dict:
                            st.metric("Health Score", diag_dict.get("health_score", 0))
                            st.metric("Onboarding Score", diag_dict.get("onboarding_score", 0))
                            st.json(diag_dict)
                        else:
                            st.warning("진단 결과가 없습니다.")
                        
                    # 사이드바에 그래프 표시
                    render_graph_visualization(result.get("task_type", "diagnosis"))

                # 세션 저장
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": llm_response,
                    "details": diag_dict,
                    "error": error_message
                })
                
            except Exception as e:
                status_placeholder.empty()
                st.error(f"시스템 오류 발생: {e}")
                logger.error(f"Error running supervisor: {e}", exc_info=True)
