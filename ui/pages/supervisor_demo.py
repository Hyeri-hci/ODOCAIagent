"""
Supervisor Agent Demo (v2.0 Restored)

자연어 질문을 입력하면:
1. 로그 축약본 - 에이전트 판단 과정, 도구 호출 내역
2. 최종 요약 - LLM이 생성한 사용자 친화적 응답
3. 상세 리포트 - 점수, 강점, 개선 필요 사항, 추천 태스크
"""
from __future__ import annotations

import base64
import os
import sys
import time
import uuid
import re
import logging
from typing import Any, Dict, List, Optional
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

# Helper Functions

def parse_query(query: str) -> Dict[str, str]:
    """사용자 쿼리에서 owner/repo 추출 (간이 파서)."""
    url_match = re.search(r"github\.com/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)", query)
    if url_match:
        return {"owner": url_match.group(1), "repo": url_match.group(2)}
    
    simple_match = re.search(r"\b([a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)\b", query)
    if simple_match:
        return {"owner": simple_match.group(1), "repo": simple_match.group(2)}
    
    return {}

def is_greeting(query: str) -> bool:
    greetings = ["안녕", "반가워", "hi", "hello", "hey", "help", "도움말"]
    return any(g in query.lower() for g in greetings)

def to_dict(obj: Any) -> Any:
    if is_dataclass(obj):
        return asdict(obj)
    return obj

def get_answer_kind_badge(answer_kind: str) -> str:
    badges = {
        "report": ("진단 리포트", "blue"),
        "explain": ("점수 해설", "green"),
        "refine": ("Task 필터링", "orange"),
        "concept": ("개념 설명", "violet"),
        "chat": ("일반 대화", "gray"),
        "greeting": ("인사", "gray"),
        "disambiguation": ("저장소 선택", "red"),
        "compare": ("비교 분석", "blue"),
        "onepager": ("원페이저", "blue"),
        "ask_user": ("권한 확인 필요", "red"),
        "diagnosis": ("진단 리포트", "blue"),
    }
    label, color = badges.get(answer_kind, ("응답", "gray"))
    return f":{color}[{label}]"

# Graph Visualization

def render_graph_visualization(task_type: str, active_nodes: List[str] = None):
    """Mermaid.ink API로 그래프 시각화 (동적 하이라이팅)."""
    if active_nodes is None:
        active_nodes = []
        
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
    
    # Define edges based on task_type
    if task_type == "diagnosis":
        mermaid_code += '''
    ROUTER --> DIAG
    DIAG --> END
    '''
    elif task_type == "security":
        mermaid_code += '''
    ROUTER --> SEC
    SEC --> END
    '''
    else:
        mermaid_code += '''
    ROUTER --> DIAG
    DIAG --> SEC
    SEC --> END
    '''

    # Styling
    mermaid_code += '''
    style START fill:#9C27B0,stroke:#333,stroke-width:2px,color:#fff
    style ROUTER fill:#2196F3,stroke:#333,stroke-width:2px,color:#fff
    style END fill:#E91E63,stroke:#333,stroke-width:2px,color:#fff
    '''
    
    # Dynamic Highlighting
    if "DiagnosisAgent" in active_nodes:
        mermaid_code += 'style DIAG fill:#4CAF50,stroke:#333,stroke-width:4px,color:#fff\n'
    else:
        mermaid_code += 'style DIAG fill:#eee,stroke:#333,stroke-width:1px,color:#999\n'
        
    if "SecurityAgent" in active_nodes:
        mermaid_code += 'style SEC fill:#FF9800,stroke:#333,stroke-width:4px,color:#fff\n'
    else:
        mermaid_code += 'style SEC fill:#eee,stroke:#333,stroke-width:1px,color:#999\n'
    
    mermaid_encoded = base64.urlsafe_b64encode(mermaid_code.encode()).decode()
    img_url = f"https://mermaid.ink/img/{mermaid_encoded}?bgColor=white"
    
    st.image(img_url, caption="Supervisor Execution Path", use_container_width=True)


# Session State

if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = uuid.uuid4().hex
if "turn_metrics" not in st.session_state:
    st.session_state.turn_metrics = []
if "debug_events" not in st.session_state:
    st.session_state.debug_events = []
if "last_active_nodes" not in st.session_state:
    st.session_state.last_active_nodes = []

# Main UI

st.title("Supervisor Agent Demo (v2.0 Restored)")
st.caption("새로운 아키텍처(Pure Python Core + LangGraph) 기반으로 v2.0 UI 기능을 복원했습니다.")

if not GITHUB_TOKEN:
    st.warning("GITHUB_TOKEN이 설정되지 않았습니다. API 호출 제한이 발생할 수 있습니다.")

# 사이드바: 설정 및 지표
with st.sidebar:
    st.header("설정")
    if st.button("대화 초기화"):
        st.session_state.messages = []
        st.session_state.turn_metrics = []
        st.session_state.debug_events = []
        st.session_state.last_active_nodes = []
        st.rerun()
    
    st.divider()
    
    # 운영 지표 (Mocked/Calculated)
    st.markdown("**운영 지표**")
    metrics = st.session_state.turn_metrics
    if metrics:
        latencies = [m["latency"] for m in metrics]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        success_count = len([m for m in metrics if m["success"]])
        
        col1, col2 = st.columns(2)
        col1.metric("평균 레이턴시", f"{avg_latency:.0f}ms")
        col2.metric("성공률", f"{success_count}/{len(metrics)}")
        st.caption(":green[SLO 정상]")
    else:
        st.caption("데이터 없음")

    st.divider()
    
    # 디버그 이벤트 (Simplified)
    st.markdown("**디버그 이벤트**")
    events = st.session_state.debug_events
    if events:
        for evt in events[-5:]:
            st.caption(f"- `{evt['type']}` ({evt['timestamp']})")
        if st.button("이벤트 초기화"):
            st.session_state.debug_events = []
            st.rerun()
    else:
        st.caption("이벤트 없음")

    st.divider()
    
    # 빠른 문제 추적 (Checklist)
    st.markdown("**빠른 문제 추적**")
    last_msg = st.session_state.messages[-1] if st.session_state.messages else {}
    has_result = bool(last_msg.get("details"))
    has_error = bool(last_msg.get("error"))
    
    st.caption(f"{':green' if has_result else ':gray'}[1. AnswerContract 정상]")
    st.caption(f"{':green' if has_result else ':gray'}[2. sources: {1 if has_result else 0}개]")
    st.caption(f"{':green' if len(events) > 0 else ':gray'}[3. 이벤트 {len(events)}개]")
    st.caption(":green[4. 라우팅: heuristic]") 
    st.caption(f"{':green' if has_result else ':red' if has_error else ':gray'}[5. 러너 출력 있음]")
    
    if has_result or has_error:
        with st.expander("검증 상세 (Raw Debug)"):
            if has_error:
                st.error(last_msg.get("error"))
            st.json(last_msg.get("details"))
            st.json(last_msg.get("metadata"))

    st.divider()
    st.markdown("### Graph Visualization")
    # 그래프는 마지막 실행 기준
    last_task_type = "diagnosis"
    if st.session_state.messages:
        last_meta = st.session_state.messages[-1].get("metadata", {})
        last_task_type = last_meta.get("task_type", "diagnosis")
    
    render_graph_visualization(last_task_type, st.session_state.last_active_nodes)


# 채팅 히스토리 표시
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        # 배지 표시 (Assistant만)
        if msg["role"] == "assistant":
            meta = msg.get("metadata", {})
            badge = get_answer_kind_badge(meta.get("answer_kind", "chat"))
            st.markdown(badge)
        
        st.markdown(msg["content"])
        
        # 상세 리포트 (Assistant만)
        if msg["role"] == "assistant" and msg.get("details"):
            details = msg["details"]
            scores = details.get("scores", {})
            labels = details.get("labels", {})
            
            with st.expander("분석 상세 결과", expanded=True):
                st.subheader("Scores")
                if scores:
                    # 점수표
                    score_data = {
                        "지표": ["건강 점수", "문서 품질", "활동성/유지보수", "온보딩 용이성"],
                        "점수": [
                            scores.get("health_score", 0),
                            scores.get("documentation_quality", 0),
                            scores.get("activity_maintainability", 0),
                            scores.get("onboarding_score", 0)
                        ],
                        "상태": [
                            labels.get("health_level", "-"),
                            "-",
                            "-",
                            labels.get("onboarding_level", "-")
                        ]
                    }
                    st.table(score_data)
                else:
                    st.warning("점수 데이터가 없습니다.")

                # 강점 및 개선 필요
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**강점**")
                    if scores.get("health_score", 0) >= 70:
                        st.markdown("- 전반적으로 건강한 프로젝트입니다.")
                    if scores.get("documentation_quality", 0) >= 80:
                        st.markdown("- 문서화가 매우 잘 되어 있습니다.")
                    if scores.get("activity_maintainability", 0) >= 70:
                        st.markdown("- 활동성이 높고 유지보수가 잘 되고 있습니다.")
                
                with col2:
                    st.markdown("**개선 필요**")
                    docs_issues = labels.get("docs_issues", [])
                    act_issues = labels.get("activity_issues", [])
                    
                    for issue in docs_issues:
                        st.markdown(f"- 문서: {issue}")
                    for issue in act_issues:
                        st.markdown(f"- 활동성: {issue}")
                    
                    if not docs_issues and not act_issues:
                        st.markdown("- 특별히 발견된 문제가 없습니다.")

                # 다음 행동 (Task 추천)
                st.subheader("다음 행동")
                st.markdown("**'기여하고 싶어요' - 초보자 Task 추천**")
                
                # Mockup tasks based on missing sections
                missing = details.get("docs_result", {}).get("missing_sections", [])
                if missing:
                    for m in missing[:3]:
                        st.markdown(f"- README에 **{m}** 섹션을 추가해보세요.")
                else:
                    st.markdown("- 현재 문서 상태가 좋습니다. 이슈 트래커를 확인해보세요.")

                st.markdown("**[추가 Task 필요]**")
                
                # 근거 설명
                st.subheader("근거 설명")
                st.markdown(f"제공된 결과는 저장소의 건강 상태({scores.get('health_score')})와 문서화 수준({scores.get('documentation_quality')})을 종합적으로 평가했습니다.")


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
        if is_greeting(prompt):
            response_msg = "안녕하세요! 분석하고 싶은 GitHub 저장소 주소나 'owner/repo'를 알려주세요."
            answer_kind = "greeting"
        else:
            response_msg = "저장소 정보를 찾을 수 없습니다. 'owner/repo' 형식으로 입력해주세요."
            answer_kind = "chat"
        
        st.session_state.messages.append({
            "role": "assistant", 
            "content": response_msg,
            "metadata": {"answer_kind": answer_kind}
        })
        with st.chat_message("assistant"):
            st.markdown(get_answer_kind_badge(answer_kind))
            st.markdown(response_msg)
    else:
        with st.chat_message("assistant"):
            status_placeholder = st.empty()
            status_placeholder.caption(f"분석 시작: {owner}/{repo}")
            
            start_time = time.time()
            
            try:
                # 이벤트 기록
                st.session_state.debug_events.append({
                    "type": "node.started",
                    "timestamp": time.strftime("%H:%M:%S")
                })
                
                # 그래프 초기화
                graph = get_supervisor_graph()
                
                initial_state = {
                    "messages": [HumanMessage(content=prompt)],
                    "owner": owner,
                    "repo": repo,
                    "repo_ref": "HEAD",
                    "repo_id": f"{owner}/{repo}",
                    "task_type": "diagnosis",
                    "run_security": False,
                    "run_recommendation": False,
                }
                
                # 실행
                config = {"configurable": {"thread_id": st.session_state.session_id}}
                result = graph.invoke(initial_state, config=config)
                
                elapsed = (time.time() - start_time) * 1000
                
                # 결과 처리
                diagnosis_result = result.get("diagnosis_result")
                error_message = result.get("error_message")
                
                # DiagnosisAgent 내부 에러 체크
                if not error_message and isinstance(diagnosis_result, dict) and diagnosis_result.get("error_message"):
                     error_message = diagnosis_result.get("error_message")

                diag_dict = to_dict(diagnosis_result) if diagnosis_result else {}
                
                # 활성 노드 추적 (결과 기반)
                active_nodes = []
                if diagnosis_result:
                    active_nodes.append("DiagnosisAgent")
                if result.get("security_result"):
                    active_nodes.append("SecurityAgent")
                st.session_state.last_active_nodes = active_nodes
                
                # LLM 요약 찾기
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
                    success = False
                else:
                    success = True
                    # 배지 표시
                    st.markdown(get_answer_kind_badge("diagnosis"))
                    
                    # 응답 표시
                    st.markdown(llm_response)
                    
                    # 상세 리포트 (즉시 표시)
                    with st.expander("분석 상세 결과", expanded=True):
                        st.subheader("Scores")
                        scores = diag_dict.get("scores", {})
                        labels = diag_dict.get("labels", {})
                        
                        if scores:
                            score_data = {
                                "지표": ["건강 점수", "문서 품질", "활동성/유지보수", "온보딩 용이성"],
                                "점수": [
                                    scores.get("health_score", 0),
                                    scores.get("documentation_quality", 0),
                                    scores.get("activity_maintainability", 0),
                                    scores.get("onboarding_score", 0)
                                ],
                                "상태": [
                                    labels.get("health_level", "-"),
                                    "-",
                                    "-",
                                    labels.get("onboarding_level", "-")
                                ]
                            }
                            st.table(score_data)
                        
                        # 강점/약점 등은 위와 동일 로직 (생략 가능하나 UI 일관성 위해 유지)
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("**강점**")
                            if scores.get("health_score", 0) >= 70:
                                st.markdown("- 전반적으로 건강한 프로젝트입니다.")
                        with col2:
                            st.markdown("**개선 필요**")
                            docs_issues = labels.get("docs_issues", [])
                            for issue in docs_issues:
                                st.markdown(f"- 문서: {issue}")

                # 메트릭 저장
                st.session_state.turn_metrics.append({
                    "latency": elapsed,
                    "success": success
                })
                
                # 이벤트 기록
                st.session_state.debug_events.append({
                    "type": "node.finished",
                    "timestamp": time.strftime("%H:%M:%S")
                })

                # 세션 저장
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": llm_response,
                    "details": diag_dict,
                    "error": error_message,
                    "metadata": {
                        "answer_kind": "diagnosis" if success else "chat",
                        "task_type": "diagnosis"
                    }
                })
                
                # 리런하여 사이드바 업데이트
                st.rerun()
                
            except Exception as e:
                status_placeholder.empty()
                st.error(f"시스템 오류 발생: {e}")
                logger.error(f"Error running supervisor: {e}", exc_info=True)
