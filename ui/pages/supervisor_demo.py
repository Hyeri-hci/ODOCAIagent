"""
Supervisor Agent 데모 페이지

자연어 질문을 입력하면:
1. 로그 축약본 - 에이전트 판단 과정, 도구 호출 내역
2. 최종 요약 - LLM이 생성한 사용자 친화적 응답
"""
from __future__ import annotations

import os
import sys
import time
import uuid
import logging
from typing import Any

# 프로젝트 루트 추가
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import streamlit as st

st.set_page_config(
    page_title="Supervisor Agent Demo",
    layout="wide",
)


# ============================================================================
# 로깅 캡처 설정
# ============================================================================
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


# ============================================================================
# 세션 상태 초기화
# ============================================================================
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


# ============================================================================
# 메인 UI
# ============================================================================
st.title("Supervisor Agent Demo")
st.caption("자연어로 GitHub 저장소에 대해 질문하면, 에이전트가 분석하고 응답합니다.")

# 사이드바 설정
with st.sidebar:
    st.header("설정")
    
    show_log = st.checkbox("실행 로그 표시", value=True)
    show_scores = st.checkbox("점수 상세 표시", value=False)
    show_tasks = st.checkbox("온보딩 Task 표시", value=False)
    debug_mode = st.checkbox("디버그 모드", value=False)
    developer_mode = st.checkbox("개발자 모드", value=False, help="answer_kind, last_brief 등 내부 정보 표시")
    
    st.divider()
    
    # 예시 질문 버튼
    st.markdown("**예시 질문**")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("상태 분석", use_container_width=True, help="facebook/react 상태 분석해줘"):
            st.session_state.example_query = "facebook/react 상태 분석해줘"
            st.rerun()
    with col2:
        if st.button("기여하기", use_container_width=True, help="초보자인데 vue에 기여하고 싶어요"):
            st.session_state.example_query = "초보자인데 vuejs/vue에 기여하고 싶어요"
            st.rerun()
    
    col3, col4 = st.columns(2)
    with col3:
        if st.button("개념 설명", use_container_width=True, help="온보딩 용이성이 뭐야?"):
            st.session_state.example_query = "온보딩 용이성이 뭐야?"
            st.rerun()
    with col4:
        if st.button("PR 가이드", use_container_width=True, help="PR은 어떻게 보내?"):
            st.session_state.example_query = "PR은 어떻게 보내?"
            st.rerun()
    
    st.divider()
    
    st.markdown("**지원 질문 유형**")
    st.markdown("""
**저장소 분석** (repo 필요)
- :blue[Health]: "facebook/react 상태 분석해줘"
- :green[온보딩]: "초보자인데 vue에 기여하고 싶어요"
- :orange[비교]: "react와 vue를 비교해줘"

**개념 Q&A** (repo 불필요)
- :violet[지표 설명]: "온보딩 용이성이 뭐야?"
- :violet[프로세스]: "PR은 어떻게 보내?"

**후속 질문** (이전 결과 참조)
- :gray[필터링]: "더 쉬운 거 없어?"
- :gray[상세]: "이 점수는 어떻게 계산된 거야?"
    """)
    
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


# ============================================================================
# 응답 유형 배지 표시
# ============================================================================
ANSWER_KIND_BADGES = {
    "report": ("📊 진단 리포트", "blue"),
    "explain": ("💡 점수 해설", "green"),
    "refine": ("🔍 Task 필터링", "orange"),
    "concept": ("📚 개념 설명", "violet"),
    "chat": ("💬 일반 대화", "gray"),
}


def get_answer_kind_badge(answer_kind: str) -> str:
    """answer_kind에 해당하는 Streamlit 배지 마크다운 반환"""
    label, color = ANSWER_KIND_BADGES.get(answer_kind, ("💬 응답", "gray"))
    return f":{color}[{label}]"


# ============================================================================
# 대화 히스토리 표시
# ============================================================================
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


# ============================================================================
# 채팅 입력 (하단 고정)
# ============================================================================

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
    
    log_handler = capture_agent_logs()
    
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
                }
                
                # 이전 결과가 있으면 컨텍스트 전달
                if st.session_state.last_result:
                    prev = st.session_state.last_result
                    if prev.get("repo"):
                        initial_state["last_repo"] = prev.get("repo")
                    # diagnosis_result가 dict인 경우만 처리
                    diag = prev.get("diagnosis_result")
                    if isinstance(diag, dict) and diag.get("onboarding_tasks"):
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
                    if prev.get("task_type"):
                        initial_state["last_intent"] = prev.get("task_type")
                
                # 분석 히스토리 전달 (이전에 분석한 저장소들)
                if st.session_state.analysis_history:
                    initial_state["analysis_history"] = st.session_state.analysis_history
                
                # 진행 상황 콜백 설정
                def progress_callback(step: str, detail: str = ""):
                    update_status(step, detail)
                
                initial_state["_progress_callback"] = progress_callback
                
                # 그래프 실행
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
                
                # 메시지 저장
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": llm_summary,
                    "metadata": metadata
                })
                
            except Exception as e:
                status_placeholder.empty()
                error_str = str(e)
                
                # GitHub NOT_FOUND 오류 처리
                if "NOT_FOUND" in error_str or "Could not resolve" in error_str:
                    # 저장소 이름 추출 시도
                    import re
                    repo_match = re.search(r"'([^']+/[^']+)'", error_str)
                    repo_name = repo_match.group(1) if repo_match else "입력한 저장소"
                    
                    error_msg = f"저장소를 찾을 수 없습니다: `{repo_name}`\n\n정확한 저장소 이름을 확인해주세요. 예: `facebook/react`, `microsoft/vscode`"
                    st.warning(error_msg)
                else:
                    error_msg = f"오류 발생: {e}"
                    st.error(error_msg)
                
                if debug_mode:
                    import traceback
                    st.code(traceback.format_exc())
                
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_msg,
                    "metadata": {}
                })
    
    st.rerun()
