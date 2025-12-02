"""
Supervisor Agent 데모 페이지

자연어 질문을 입력하면:
1. 로그 축약본 - 에이전트 판단 과정, 도구 호출 내역
2. 최종 요약 - LLM이 생성한 사용자 친화적 응답
"""
from __future__ import annotations

import base64
import os
import sys
import time
import uuid
import logging
from typing import Any
from urllib.parse import quote

# 프로젝트 루트 추가
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import streamlit as st

st.set_page_config(
    page_title="Supervisor Agent Demo",
    layout="wide",
)

# 로깅 캡처 설정
class StreamlitLogHandler(logging.Handler):
    """Streamlit에 로그를 실시간으로 표시하는 핸들러"""
    
    def __init__(self):
        super().__init__()
        self.logs = []
        
    def emit(self, record):
        try:
            msg = self.format(record)
            self.logs.append(msg)
            if len(self.logs) > 50:
                self.logs = self.logs[-50:]
        except Exception:
            pass
    
    def get_logs(self) -> list[str]:
        return self.logs.copy()


def capture_agent_logs():
    """에이전트 실행 중 로그를 캡처"""
    loggers = [
        "backend.agents.supervisor",
        "backend.agents.diagnosis",
        "backend.common",
    ]
    
    log_handler = StreamlitLogHandler()
    log_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(name)s | %(message)s",
        datefmt="%H:%M:%S"
    ))
    log_handler.setLevel(logging.INFO)
    
    for logger_name in loggers:
        logger = logging.getLogger(logger_name)
        logger.addHandler(log_handler)
        logger.setLevel(logging.INFO)
    
    return log_handler


# 그래프 시각화 함수
def render_graph_visualization(result: dict | None):
    """Mermaid.ink API로 그래프를 PNG 이미지로 시각화"""
    if not result:
        st.caption("실행 결과 없음")
        return
    
    intent = result.get("intent", "")
    sub_intent = result.get("sub_intent", "")
    answer_kind = result.get("answer_kind", "chat")
    has_diagnosis = bool(result.get("diagnosis_result"))
    needs_disambiguation = result.get("_needs_disambiguation", False)
    
    # 실행된 경로 결정 (answer_kind가 disambiguation이면 우선)
    if needs_disambiguation or answer_kind == "disambiguation":
        path = "disambiguation"
    elif intent == "smalltalk" or intent == "help":
        path = "fast"
    elif intent == "overview":
        path = "overview"
    elif sub_intent in ("compare", "onepager"):
        path = "expert"
    elif has_diagnosis:
        path = "diagnosis"
    else:
        path = "summarize"
    
    # Mermaid 다이어그램 생성
    mermaid_code = f'''flowchart TD
    subgraph Input
        START((Query))
    end
    
    subgraph Routing
        INIT[init]
        CLASSIFY[classify<br/>{intent}.{sub_intent}]
    end
    
    subgraph Processing
        DIAG[diagnosis]
        EXPERT[expert<br/>compare/onepager]
        FAST[fast path<br/>smalltalk/help]
    end
    
    subgraph Output
        SUMMARIZE[summarize]
        DISAMB[disambiguation]
        ANSWER((Answer<br/>{answer_kind}))
    end
    
    START --> INIT
    INIT --> CLASSIFY
'''
    
    # 경로별 화살표 추가
    if path == "fast":
        mermaid_code += '''
    CLASSIFY --> FAST
    FAST --> ANSWER
    style FAST fill:#4CAF50,stroke:#333,stroke-width:2px,color:#fff
'''
    elif path == "disambiguation":
        mermaid_code += '''
    CLASSIFY --> DISAMB
    DISAMB --> ANSWER
    style DISAMB fill:#FF9800,stroke:#333,stroke-width:2px,color:#fff
'''
    elif path == "expert":
        mermaid_code += '''
    CLASSIFY --> EXPERT
    EXPERT --> SUMMARIZE
    SUMMARIZE --> ANSWER
    style EXPERT fill:#4CAF50,stroke:#333,stroke-width:2px,color:#fff
'''
    elif path == "diagnosis":
        mermaid_code += '''
    CLASSIFY --> DIAG
    DIAG --> SUMMARIZE
    SUMMARIZE --> ANSWER
    style DIAG fill:#4CAF50,stroke:#333,stroke-width:2px,color:#fff
'''
    else:
        mermaid_code += '''
    CLASSIFY --> SUMMARIZE
    SUMMARIZE --> ANSWER
'''
    
    # 공통 스타일
    mermaid_code += '''
    style START fill:#9C27B0,stroke:#333,stroke-width:2px,color:#fff
    style INIT fill:#2196F3,stroke:#333,stroke-width:2px,color:#fff
    style CLASSIFY fill:#2196F3,stroke:#333,stroke-width:2px,color:#fff
    style SUMMARIZE fill:#4CAF50,stroke:#333,stroke-width:2px,color:#fff
    style ANSWER fill:#E91E63,stroke:#333,stroke-width:2px,color:#fff
'''
    
    # Mermaid.ink API로 이미지 URL 생성
    mermaid_encoded = base64.urlsafe_b64encode(mermaid_code.encode()).decode()
    img_url = f"https://mermaid.ink/img/{mermaid_encoded}?bgColor=white"
    
    # 큰 이미지로 표시
    st.image(img_url, caption="Supervisor Graph 실행 경로", use_container_width=True)
    
    # 다운로드 링크 제공
    col1, col2 = st.columns([1, 3])
    with col1:
        st.markdown(f"[PNG 다운로드]({img_url})")
    
    # 실행 경로 텍스트 설명
    path_desc = {
        "fast": "경량 경로 (LLM 호출 없음)",
        "disambiguation": "엔티티 확인 필요",
        "expert": "전문 러너 실행",
        "diagnosis": "진단 에이전트 실행",
        "overview": "저장소 개요 조회",
        "summarize": "직접 요약",
    }
    with col2:
        st.caption(f"실행 경로: **{path_desc.get(path, path)}**")


# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "analysis_history" not in st.session_state:
    # 분석된 저장소 결과들을 저장 (owner/repo -> result)
    st.session_state.analysis_history = {}
if "example_query" not in st.session_state:
    st.session_state.example_query = None
if "session_id" not in st.session_state:
    st.session_state.session_id = uuid.uuid4().hex
if "debug_events" not in st.session_state:
    st.session_state.debug_events = []  # 디버그 이벤트 저장
if "turn_metrics" not in st.session_state:
    st.session_state.turn_metrics = []  # 턴별 메트릭 저장


# 메인 UI
st.title("Supervisor Agent Demo")
st.caption("자연어로 GitHub 저장소에 대해 질문하면, 에이전트가 분석하고 응답합니다.")

# 사이드바 설정
with st.sidebar:
    st.header("설정")
    
    show_log = st.checkbox("실행 로그 표시", value=True)
    show_scores = st.checkbox("점수 상세 표시", value=False)
    show_tasks = st.checkbox("온보딩 Task 표시", value=False)
    debug_mode = st.checkbox("디버그 모드", value=False, help="이벤트, 에러, 재계획 정보 표시")
    developer_mode = st.checkbox("개발자 모드", value=False, help="answer_kind, last_brief 등 내부 정보 표시")
    show_metrics = st.checkbox("운영 지표 대시보드", value=False, help="SLO, 레이턴시, 에러율 표시")
    show_graph = st.checkbox("그래프 구조 시각화", value=False, help="실행 경로 및 노드 상태 표시")
    
    st.divider()
    
    if st.button("대화 초기화"):
        st.session_state.messages = []
        st.session_state.last_result = None
        st.session_state.analysis_history = {}
        if "example_query" in st.session_state:
            del st.session_state["example_query"]
        st.rerun()
    
    # 분석된 저장소 히스토리 표시
    if st.session_state.analysis_history:
        st.divider()
        st.markdown("**분석된 저장소**")
        for repo_key in st.session_state.analysis_history.keys():
            st.caption(f"- {repo_key}")
    
    # 운영 지표 대시보드
    if show_metrics:
        st.divider()
        st.markdown("**운영 지표**")
        
        turn_metrics = st.session_state.get("turn_metrics", [])
        if turn_metrics:
            # 최근 10개 턴의 평균 메트릭
            latencies = [m.get("latency_ms", 0) for m in turn_metrics[-10:]]
            avg_latency = sum(latencies) / len(latencies) if latencies else 0
            
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.metric("평균 레이턴시", f"{avg_latency:.0f}ms")
            with col_m2:
                success_count = sum(1 for m in turn_metrics if m.get("success", False))
                st.metric("성공률", f"{success_count}/{len(turn_metrics)}")
            
            # SLO 상태
            errors = [m for m in turn_metrics if m.get("error")]
            if errors:
                st.caption(f":red[에러 {len(errors)}건]")
            else:
                st.caption(":green[SLO 정상]")
        else:
            st.caption("데이터 없음")
    
    # 디버그 이벤트 뷰어
    if debug_mode:
        st.divider()
        st.markdown("**디버그 이벤트**")
        
        debug_events = st.session_state.get("debug_events", [])
        if debug_events:
            for event in debug_events[-5:]:
                event_type = event.get("type", "unknown")
                if "error" in event_type.lower():
                    st.caption(f":red[{event_type}]")
                elif "retry" in event_type.lower() or "replan" in event_type.lower():
                    st.caption(f":orange[{event_type}]")
                else:
                    st.caption(f":gray[{event_type}]")
            
            if st.button("이벤트 초기화", key="clear_events"):
                st.session_state.debug_events = []
                st.rerun()
        else:
            st.caption("이벤트 없음")
    
    # 빠른 문제 추적 체크리스트
    st.divider()
    st.markdown("**빠른 문제 추적**")
    
    last_result = st.session_state.get("last_result")
    if last_result:
        # 1. AnswerContract 검증
        answer_contract = last_result.get("answer_contract", {})
        has_answer_contract = bool(answer_contract and answer_contract.get("text"))
        if has_answer_contract:
            st.caption(":green[1. AnswerContract 정상]")
        else:
            st.caption(":red[1. AnswerContract 누락]")
        
        # 2. sources[] 검증
        sources = answer_contract.get("sources", [])
        has_valid_sources = bool(sources and len(sources) > 0)
        if has_valid_sources:
            st.caption(f":green[2. sources: {len(sources)}개]")
        else:
            st.caption(":red[2. sources 비어있음]")
        
        # 3. 이벤트 타임라인 검증 (5종)
        debug_events = st.session_state.get("debug_events", [])
        event_types = [e.get("type", "") for e in debug_events[-10:]]
        required_events = ["init", "classify", "diagnosis", "summarize", "turn_complete"]
        found_events = sum(1 for req in required_events if any(req in et for et in event_types))
        if found_events >= 3:
            st.caption(f":green[3. 이벤트 {found_events}/5종]")
        else:
            st.caption(f":orange[3. 이벤트 {found_events}/5종]")
        
        # 4. 라우팅 2단계 검증
        classification_method = last_result.get("_classification_method", "unknown")
        if classification_method in ("heuristic", "llm"):
            st.caption(f":green[4. 라우팅: {classification_method}]")
        else:
            st.caption(f":orange[4. 라우팅: {classification_method}]")
        
        # 5. 러너 출력 계약 검증
        expert_result = last_result.get("_expert_result")
        diagnosis_result = last_result.get("diagnosis_result")
        if expert_result or diagnosis_result:
            has_status = bool(expert_result and hasattr(expert_result, "success"))
            st.caption(f":green[5. 러너 출력 있음]")
        else:
            # smalltalk/help 등은 러너 없음
            intent = last_result.get("intent", "")
            if intent in ("smalltalk", "help", "overview"):
                st.caption(f":gray[5. 러너 불필요 ({intent})]")
            else:
                st.caption(":orange[5. 러너 출력 없음]")
        
        # 6. 디그레이드/재계획 발동 여부
        errors = last_result.get("_errors", [])
        retries = last_result.get("_retries", [])
        needs_disambiguation = last_result.get("_needs_disambiguation", False)
        
        if errors or retries:
            st.caption(f":orange[6. 재계획: {len(retries)}회]")
        elif needs_disambiguation:
            st.caption(":orange[6. Disambiguation 발동]")
        else:
            st.caption(":green[6. 정상 경로 실행]")
        
        # 상세 보기 버튼
        with st.expander("검증 상세"):
            st.json({
                "has_answer_contract": has_answer_contract,
                "sources_count": len(sources),
                "sources_sample": sources[:3] if sources else [],
                "classification_method": classification_method,
                "intent": last_result.get("intent"),
                "sub_intent": last_result.get("sub_intent"),
                "answer_kind": last_result.get("answer_kind"),
                "needs_disambiguation": needs_disambiguation,
                "error_count": len(errors),
                "retry_count": len(retries),
            })
    else:
        st.caption(":gray[결과 없음 - 먼저 질문하세요]")
    
    # 그래프 구조 시각화
    if show_graph:
        st.divider()
        st.markdown("**그래프 구조**")
        render_graph_visualization(last_result)


# 응답 유형 배지 표시
ANSWER_KIND_BADGES = {
    "report": ("진단 리포트", "blue"),
    "explain": ("점수 해설", "green"),
    "refine": ("Task 필터링", "orange"),
    "concept": ("개념 설명", "violet"),
    "chat": ("일반 대화", "gray"),
    "greeting": ("인사", "gray"),
    "disambiguation": ("저장소 선택", "red"),
    "compare": ("비교 분석", "blue"),
    "onepager": ("원페이저", "blue"),
}


def get_answer_kind_badge(answer_kind: str) -> str:
    """answer_kind에 해당하는 Streamlit 배지 마크다운 반환"""
    label, color = ANSWER_KIND_BADGES.get(answer_kind, ("💬 응답", "gray"))
    return f":{color}[{label}]"


# 대화 히스토리 표시
chat_container = st.container()

with chat_container:
    messages = st.session_state.messages
    total_msgs = len(messages)
    
    for idx, msg in enumerate(messages):
        is_last = (idx == total_msgs - 1)
        
        with st.chat_message(msg["role"]):
            # assistant 메시지에 배지 표시
            if msg["role"] == "assistant" and msg.get("metadata"):
                meta = msg["metadata"]
                answer_kind = meta.get("answer_kind", "chat")
                badge = get_answer_kind_badge(answer_kind)
                st.markdown(badge)
            
            # 이전 응답은 접기로 표시 (마지막 응답 제외)
            if msg["role"] == "assistant" and not is_last and msg["content"]:
                # 이전 응답은 접어서 표시
                content_preview = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
                with st.expander(f"이전 응답: {content_preview}", expanded=False):
                    st.markdown(msg["content"])
            else:
                st.markdown(msg["content"])
            
            # 로그/상세정보 표시 (assistant 메시지에만)
            if msg["role"] == "assistant" and msg.get("metadata"):
                meta = msg["metadata"]
                
                # 메트릭
                cols = st.columns(4)
                with cols[0]:
                    st.caption(f"실행 시간: {meta.get('elapsed', 'N/A')}")
                with cols[1]:
                    # intent → sub_intent 표시 (새 구조)
                    intent_display = f"{meta.get('intent', 'N/A')}/{meta.get('sub_intent', 'N/A')}"
                    st.caption(f"Intent: {intent_display}")
                with cols[2]:
                    st.caption(f"Level: {meta.get('level', 'N/A')}")
                with cols[3]:
                    st.caption(f"Follow-up: {'예' if meta.get('is_followup') else '아니오'}")
                
                # 개발자 모드: last_brief 표시
                if developer_mode and meta.get("last_brief"):
                    with st.expander("last_brief (맥락 요약)"):
                        st.caption(meta["last_brief"])
                
                # 로그
                if show_log and meta.get("log_summary"):
                    with st.expander("실행 로그"):
                        st.markdown(meta["log_summary"])
                
                # 점수
                if show_scores and meta.get("scores") and isinstance(meta.get("scores"), dict):
                    with st.expander("점수 상세"):
                        st.json(meta["scores"])
                
                # Task 목록
                if show_tasks and meta.get("tasks") and isinstance(meta.get("tasks"), dict):
                    with st.expander("온보딩 Task"):
                        for level_name, level_tasks in meta["tasks"].items():
                            if level_tasks and isinstance(level_tasks, list):
                                st.markdown(f"**{level_name.title()}** ({len(level_tasks)}개)")
                                for task in level_tasks[:3]:
                                    if isinstance(task, dict):
                                        st.markdown(f"- {task.get('title', 'N/A')}")


# 채팅 입력 (하단 고정)
# 예시 질문 버튼에서 설정한 쿼리 처리
example_query = st.session_state.example_query
if example_query:
    st.session_state.example_query = None  # 리셋
    prompt = example_query
else:
    prompt = st.chat_input("질문을 입력하세요 (예: facebook/react 상태 분석해줘)")

if prompt:
    # 사용자 메시지 추가
    st.session_state.messages.append({
        "role": "user",
        "content": prompt
    })
    
    # 사용자 메시지 표시
    with chat_container:
        with st.chat_message("user"):
            st.markdown(prompt)
    
    # 에이전트 실행
    from backend.agents.supervisor.graph import build_supervisor_graph
    from backend.common.events import get_event_store, EventType
    
    log_handler = capture_agent_logs()
    
    # 이벤트 캡처를 위한 리스너 설정
    captured_events = []
    def event_listener(event):
        captured_events.append({
            "type": event.type.value if hasattr(event.type, "value") else str(event.type),
            "actor": event.actor,
            "timestamp": event.timestamp,
            "inputs": event.inputs,
            "outputs": event.outputs,
        })
    
    event_store = get_event_store()
    event_store.add_listener(event_listener)
    
    with chat_container:
        with st.chat_message("assistant"):
            # 진행 상황 표시 영역 (한 줄만 유지, 덮어쓰기)
            status_placeholder = st.empty()
            start_time = time.time()
            
            def update_status(step: str, detail: str = ""):
                """진행 상황 업데이트 (한 줄만 표시)"""
                if detail:
                    status_placeholder.caption(f":gray[{step}: {detail}]")
                else:
                    status_placeholder.caption(f":gray[{step}]")
            
            try:
                graph = build_supervisor_graph()
                update_status("사용자 의도 분석 중", "Intent 분류...")
                
                # 이전 결과에서 컨텍스트 가져오기 (멀티턴 지원)
                initial_state = {
                    "user_query": prompt.strip(),
                    "history": [
                        {"role": m["role"], "content": m["content"]} 
                        for m in st.session_state.messages[:-1]
                    ],
                    # 세션 ID 전달 (세션 연속성 보장)
                    "_session_id": st.session_state.session_id,
                }
                
                # 이전 결과가 있으면 컨텍스트 전달 (Follow-up 지원 강화)
                if st.session_state.last_result:
                    prev = st.session_state.last_result
                    
                    # 이전 저장소 정보 전달
                    if prev.get("repo"):
                        initial_state["last_repo"] = prev.get("repo")
                    
                    # diagnosis_result 직접 전달 (Follow-up 핵심)
                    diag = prev.get("diagnosis_result")
                    if isinstance(diag, dict):
                        initial_state["diagnosis_result"] = diag
                        
                        # onboarding_tasks를 flat list로 변환
                        onboarding_tasks = diag.get("onboarding_tasks", {})
                        task_list = []
                        for difficulty in ["beginner", "intermediate", "advanced"]:
                            for task in onboarding_tasks.get(difficulty, []):
                                task_copy = dict(task) if isinstance(task, dict) else {}
                                if "difficulty" not in task_copy:
                                    task_copy["difficulty"] = difficulty
                                task_list.append(task_copy)
                        initial_state["last_task_list"] = task_list
                    
                    # 이전 answer_kind 전달 (Follow-up 타입 결정)
                    if prev.get("answer_kind"):
                        initial_state["last_answer_kind"] = prev.get("answer_kind")
                    if prev.get("last_brief"):
                        initial_state["last_brief"] = prev.get("last_brief")
                    if prev.get("intent"):
                        initial_state["last_intent"] = prev.get("intent")
                
                # 분석 히스토리 전달 (이전에 분석한 저장소들)
                if st.session_state.analysis_history:
                    initial_state["analysis_history"] = st.session_state.analysis_history
                
                # 진행 상황 콜백 설정
                def progress_callback(step: str, detail: str = ""):
                    update_status(step, detail)
                
                initial_state["_progress_callback"] = progress_callback
                
                # 그래프 실행 (thread_id로 세션 상태 유지)
                result = graph.invoke(
                    initial_state,
                    config={
                        "configurable": {
                            "thread_id": st.session_state.session_id,
                        }
                    },
                )
                elapsed = time.time() - start_time
                
                update_status("응답 생성 완료", f"{elapsed:.1f}초")
                status_placeholder.empty()  # 진행 상황 제거
                
                st.session_state.last_result = result
                
                # 분석 히스토리에 저장 (저장소별로 결과 캐싱)
                repo = result.get("repo")
                if repo and isinstance(repo, dict):
                    repo_key = f"{repo.get('owner')}/{repo.get('name')}"
                    st.session_state.analysis_history[repo_key] = {
                        "repo": repo,
                        "diagnosis": result.get("diagnosis_result"),
                        "task_type": result.get("task_type"),
                    }
                
                compare_repo = result.get("compare_repo")
                if compare_repo and isinstance(compare_repo, dict):
                    compare_key = f"{compare_repo.get('owner')}/{compare_repo.get('name')}"
                    compare_diag = result.get("compare_diagnosis_result")
                    if isinstance(compare_diag, dict):
                        st.session_state.analysis_history[compare_key] = {
                            "repo": compare_repo,
                            "diagnosis": compare_diag,
                            "task_type": result.get("task_type"),
                        }
                
                # 배지 표시 (응답 위에)
                answer_kind = result.get("answer_kind", "chat")
                badge = get_answer_kind_badge(answer_kind)
                st.markdown(badge)
                
                # 응답 표시
                llm_summary = result.get("llm_summary", "")
                if llm_summary:
                    st.markdown(llm_summary)
                else:
                    st.warning("응답이 생성되지 않았습니다.")
                
                # 로그 요약 생성
                log_lines = []
                log_lines.append(f"1. Intent 분류: `{result.get('task_type', 'N/A')}`")
                
                repo = result.get("repo")
                if repo:
                    log_lines.append(f"2. 저장소: `{repo.get('owner')}/{repo.get('name')}`")
                
                compare_repo = result.get("compare_repo")
                if compare_repo:
                    log_lines.append(f"   비교 대상: `{compare_repo.get('owner')}/{compare_repo.get('name')}`")
                
                if result.get("is_followup"):
                    log_lines.append(f"3. Follow-up: `{result.get('followup_type', 'N/A')}`")
                
                diagnosis = result.get("diagnosis_result")
                if diagnosis and isinstance(diagnosis, dict):
                    scores = diagnosis.get("scores", {})
                    log_lines.append(f"4. Diagnosis 완료")
                    log_lines.append(f"   - Health: `{scores.get('health_score', 'N/A')}`")
                
                compare_diagnosis = result.get("compare_diagnosis_result")
                if compare_diagnosis and isinstance(compare_diagnosis, dict):
                    compare_scores = compare_diagnosis.get("scores", {})
                    log_lines.append(f"5. 비교 대상 Health: `{compare_scores.get('health_score', 'N/A')}`")
                
                # 메타데이터 구성
                user_ctx = result.get("user_context")
                level = user_ctx.get("level", "N/A") if isinstance(user_ctx, dict) else "N/A"
                
                metadata = {
                    "elapsed": f"{elapsed:.1f}초",
                    "intent": result.get("intent", result.get("task_type", "N/A")),
                    "sub_intent": result.get("sub_intent", "N/A"),
                    "answer_kind": result.get("answer_kind", "chat"),
                    "last_brief": result.get("last_brief", ""),
                    "level": level,
                    "is_followup": result.get("is_followup", False),
                    "log_summary": "\n".join(log_lines),
                    "scores": diagnosis.get("scores") if diagnosis and isinstance(diagnosis, dict) else None,
                    "tasks": diagnosis.get("onboarding_tasks") if diagnosis and isinstance(diagnosis, dict) else None,
                }
                
                # 메트릭 표시
                cols = st.columns(4)
                with cols[0]:
                    st.caption(f"실행 시간: {metadata['elapsed']}")
                with cols[1]:
                    intent_display = f"{metadata['intent']}/{metadata['sub_intent']}"
                    st.caption(f"Intent: {intent_display}")
                with cols[2]:
                    st.caption(f"Level: {metadata['level']}")
                with cols[3]:
                    st.caption(f"Follow-up: {'예' if metadata['is_followup'] else '아니오'}")
                
                # 개발자 모드: last_brief 표시
                if developer_mode and metadata.get("last_brief"):
                    with st.expander("last_brief (맥락 요약)"):
                        st.caption(metadata["last_brief"])
                
                # 로그 표시
                if show_log:
                    with st.expander("실행 로그"):
                        st.markdown(metadata["log_summary"])
                
                if show_scores and metadata.get("scores"):
                    with st.expander("점수 상세"):
                        st.json(metadata["scores"])
                
                if show_tasks and metadata.get("tasks"):
                    with st.expander("온보딩 Task"):
                        for level_name, level_tasks in metadata["tasks"].items():
                            if level_tasks and isinstance(level_tasks, list):
                                st.markdown(f"**{level_name.title()}** ({len(level_tasks)}개)")
                                for task in level_tasks[:3]:
                                    if isinstance(task, dict):
                                        st.markdown(f"- {task.get('title', 'N/A')}")
                
                # 디버그 모드: 추가 정보 표시
                if debug_mode:
                    with st.expander("디버그 정보"):
                        # Plan/Step 정보
                        plan_info = result.get("_plan_info", {})
                        if plan_info:
                            st.markdown("**Plan 실행 정보**")
                            st.json(plan_info)
                        
                        # 에러/재시도 정보
                        errors = result.get("_errors", [])
                        retries = result.get("_retries", [])
                        
                        if errors:
                            st.markdown("**에러 발생**")
                            for err in errors:
                                st.error(f"{err.get('type', 'unknown')}: {err.get('message', '')}")
                        
                        if retries:
                            st.markdown("**재시도 이력**")
                            for retry in retries:
                                st.warning(f"Step {retry.get('step_id')}: {retry.get('count')}회 재시도")
                        
                        # answer_id (아이덤포턴시)
                        answer_id = result.get("answer_id")
                        if answer_id:
                            st.caption(f"Answer ID: `{answer_id}`")
                        
                        # sources 검증
                        sources = result.get("answer_contract", {}).get("sources", [])
                        if sources:
                            st.caption(f"Sources: {len(sources)}개")
                        else:
                            st.caption(":red[Sources: 없음 (검증 실패)]")
                        
                        # 캡처된 이벤트 타임라인
                        if captured_events:
                            st.markdown("**이벤트 타임라인**")
                            for evt in captured_events:
                                evt_type = evt.get("type", "unknown")
                                evt_actor = evt.get("actor", "unknown")
                                st.caption(f"- `{evt_type}` ({evt_actor})")
                
                # 캡처된 이벤트를 디버그 이벤트에 저장
                for evt in captured_events:
                    st.session_state.debug_events.append({
                        "type": evt.get("type", "unknown"),
                        "actor": evt.get("actor", "unknown"),
                        "timestamp": evt.get("timestamp", time.time()),
                    })
                
                # 턴 완료 이벤트 추가
                st.session_state.debug_events.append({
                    "type": f"turn_complete:{metadata['intent']}/{metadata['sub_intent']}",
                    "timestamp": time.time(),
                    "latency_ms": elapsed * 1000,
                })
                
                # 턴 메트릭 저장
                st.session_state.turn_metrics.append({
                    "timestamp": time.time(),
                    "latency_ms": elapsed * 1000,
                    "intent": metadata["intent"],
                    "sub_intent": metadata["sub_intent"],
                    "success": True,
                    "error": None,
                })
                
                # 메시지 저장
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": llm_summary,
                    "metadata": metadata
                })
                
            except Exception as e:
                status_placeholder.empty()
                error_str = str(e)
                elapsed_error = time.time() - start_time
                
                # GitHub NOT_FOUND 오류 처리
                if "NOT_FOUND" in error_str or "Could not resolve" in error_str:
                    # 저장소 이름 추출 시도
                    import re
                    repo_match = re.search(r"'([^']+/[^']+)'", error_str)
                    repo_name = repo_match.group(1) if repo_match else "입력한 저장소"
                    
                    error_msg = f"저장소를 찾을 수 없습니다: `{repo_name}`\n\n정확한 저장소 이름을 확인해주세요. 예: `facebook/react`, `microsoft/vscode`"
                    st.warning(error_msg)
                    error_type = "not_found"
                elif "rate limit" in error_str.lower():
                    error_msg = "GitHub API 요청 한도에 도달했습니다. 잠시 후 다시 시도해 주세요."
                    st.warning(error_msg)
                    error_type = "rate_limit"
                elif "timeout" in error_str.lower():
                    error_msg = "요청 시간이 초과되었습니다. 네트워크 상태를 확인하고 다시 시도해 주세요."
                    st.warning(error_msg)
                    error_type = "timeout"
                else:
                    error_msg = f"오류 발생: {e}"
                    st.error(error_msg)
                    error_type = "unknown"
                
                # 디버그 모드: 상세 에러 정보
                if debug_mode:
                    import traceback
                    with st.expander("에러 상세 (디버그)"):
                        st.code(traceback.format_exc())
                        st.caption(f"에러 유형: `{error_type}`")
                        st.caption(f"소요 시간: `{elapsed_error:.2f}초`")
                    
                    # 디버그 이벤트 저장
                    st.session_state.debug_events.append({
                        "type": f"error:{error_type}",
                        "timestamp": time.time(),
                        "message": error_str[:100],
                    })
                
                # 턴 메트릭 저장 (에러 포함)
                st.session_state.turn_metrics.append({
                    "timestamp": time.time(),
                    "latency_ms": elapsed_error * 1000,
                    "intent": "unknown",
                    "sub_intent": "unknown",
                    "success": False,
                    "error": error_type,
                })
                
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_msg,
                    "metadata": {"error": error_type}
                })
            
            finally:
                # 이벤트 리스너 정리
                event_store.remove_listener(event_listener)
    
    st.rerun()
