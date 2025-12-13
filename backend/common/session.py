"""
세션 관리 시스템 (인메모리)
대화형 멀티턴 상호작용을 위한 세션 저장소
"""

from typing import Dict, Any, List, Optional, TypedDict
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import uuid
import logging

logger = logging.getLogger(__name__)


# === 대화 턴 구조 ===
class ConversationTurn(TypedDict, total=False):
    """단일 대화 턴"""
    turn: int
    timestamp: str
    user_message: str
    resolved_intent: Dict[str, Any]  # 파싱된 의도
    execution_path: str  # "fast", "full", "reinterpret"
    agent_response: str
    data_generated: List[str]  # ["diagnosis_result", "onboarding_plan"]
    execution_time_ms: int


# === 누적 컨텍스트 ===
class AccumulatedContext(TypedDict, total=False):
    """세션 내에서 누적되는 컨텍스트"""
    # Sub-agent 결과들
    diagnosis_result: Optional[Dict[str, Any]]
    onboarding_plan: Optional[Dict[str, Any]]
    security_scan: Optional[Dict[str, Any]]
    
    # 커스텀 분석
    custom_analyses: List[Dict[str, Any]]
    
    # 분석된 저장소 목록 (비교 분석용)
    analyzed_repos: List[Dict[str, Any]] # [{owner, repo, analyzed_at, health_score}]
    
    # 마지막 주제 및 저장소 (대명사 해결용)
    last_topic: Optional[str]  # "diagnosis", "onboarding", "security"
    last_generated_data: Optional[str]  # 직전 턴에서 생성한 데이터 키
    last_mentioned_repo: Optional[Dict[str, Any]] # {owner, repo, full_name, ...}
    found_repo_info: bool
    
    # 대명사 정보
    last_pronoun_reference: Optional[Dict[str, Any]]


# === 트레이스 (디버깅) ===
class SubagentCall(TypedDict):
    """Sub-agent 호출 기록"""
    agent: str
    start_time: str
    end_time: str
    input_params: Dict[str, Any]
    output_summary: str
    from_cache: bool
    execution_time_ms: int


class TurnTrace(TypedDict):
    """단일 턴의 상세 실행 로그"""
    turn: int
    timestamp: str
    
    # 실행 플로우
    supervisor_state_snapshot: Dict[str, Any]
    subagent_calls: List[SubagentCall]
    
    # 성능
    total_execution_time_ms: int
    llm_calls: int
    
    # 디버깅
    debug_info: Dict[str, Any]


class ErrorLog(TypedDict):
    """에러 로그"""
    timestamp: str
    turn: int
    error_type: str
    error_message: str
    stack_trace: Optional[str]


class SessionTrace(TypedDict):
    """세션 전체 트레이스"""
    turn_traces: List[TurnTrace]
    errors: List[ErrorLog]
    performance: Dict[str, Any]


# === 세션 객체 ===
@dataclass
class Session:
    """대화 세션"""
    session_id: str
    owner: str
    repo: str
    ref: str = "main"
    
    # 대화 히스토리 (최근 N턴만)
    conversation_history: List[ConversationTurn] = field(default_factory=list)
    max_history_turns: int = 10
    
    # 누적 컨텍스트
    accumulated_context: AccumulatedContext = field(default_factory=lambda: AccumulatedContext(
        custom_analyses=[],
        analyzed_repos=[],
        last_topic=None,
        last_generated_data=None,
        last_mentioned_repo=None,
        found_repo_info=False,
        last_pronoun_reference=None
    ))
    
    # 메타 정보
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    total_turns: int = 0
    
    # 트레이스 (디버깅)
    trace: SessionTrace = field(default_factory=lambda: SessionTrace(
        turn_traces=[],
        errors=[],
        performance={}
    ))
    
    def add_turn(
        self,
        user_message: str,
        resolved_intent: Dict[str, Any],
        execution_path: str,
        agent_response: str,
        data_generated: List[str],
        execution_time_ms: int
    ):
        """새로운 턴 추가"""
        self.total_turns += 1
        self.last_active = datetime.now()
        
        turn = ConversationTurn(
            turn=self.total_turns,
            timestamp=datetime.now().isoformat(),
            user_message=user_message,
            resolved_intent=resolved_intent,
            execution_path=execution_path,
            agent_response=agent_response,
            data_generated=data_generated,
            execution_time_ms=execution_time_ms
        )
        
        self.conversation_history.append(turn)
        
        # 최근 N턴만 유지
        if len(self.conversation_history) > self.max_history_turns:
            self.conversation_history = self.conversation_history[-self.max_history_turns:]
        
        # last_topic, last_generated_data 업데이트
        if data_generated:
            self.accumulated_context["last_generated_data"] = data_generated[-1]
            
            # topic 추론
            if "diagnosis_result" in data_generated:
                self.accumulated_context["last_topic"] = "diagnosis"
            elif "onboarding_plan" in data_generated:
                self.accumulated_context["last_topic"] = "onboarding"
            elif "security_scan" in data_generated:
                self.accumulated_context["last_topic"] = "security"
    
    def update_context(self, key: str, value: Any):
        """컨텍스트 업데이트"""
        self.accumulated_context[key] = value
        self.last_active = datetime.now()
    
    def add_analyzed_repo(self, repo_info: Dict[str, Any]):
        """분석된 저장소 정보 추가 (중복 방지)"""
        if "analyzed_repos" not in self.accumulated_context:
            self.accumulated_context["analyzed_repos"] = []
            
        repo_key = f"{repo_info.get('owner')}/{repo_info.get('repo')}"
        
        # 기존 목록에서 동일한 저장소 제거 (최신 정보로 갱신하기 위해)
        self.accumulated_context["analyzed_repos"] = [
            r for r in self.accumulated_context["analyzed_repos"]
            if f"{r.get('owner')}/{r.get('repo')}" != repo_key
        ]
        
        # 새 정보 추가
        self.accumulated_context["analyzed_repos"].append(repo_info)
        
        # 최대 10개 유지
        if len(self.accumulated_context["analyzed_repos"]) > 10:
             self.accumulated_context["analyzed_repos"] = self.accumulated_context["analyzed_repos"][-10:]

    def get_context(self, key: str) -> Optional[Any]:
        """컨텍스트 조회"""
        return self.accumulated_context.get(key)
    
    def add_trace(self, turn_trace: TurnTrace):
        """트레이스 추가"""
        self.trace["turn_traces"].append(turn_trace)
    
    def add_error(self, error_log: ErrorLog):
        """에러 로그 추가"""
        self.trace["errors"].append(error_log)
    
    def is_expired(self, ttl_minutes: int = 60) -> bool: # TTL increased to 60m
        """세션 만료 여부"""
        return datetime.now() - self.last_active > timedelta(minutes=ttl_minutes)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환 (직렬화용)"""
        
        def _serialize(obj):
            """중첩된 객체를 JSON 직렬화 가능하게 변환"""
            if obj is None:
                return None
            if isinstance(obj, (str, int, float, bool)):
                return obj
            if isinstance(obj, dict):
                return {k: _serialize(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [_serialize(item) for item in obj]
            if hasattr(obj, 'to_dict'):
                return obj.to_dict()
            if hasattr(obj, '__dict__'):
                return {k: _serialize(v) for k, v in obj.__dict__.items() if not k.startswith('_')}
            # datetime 등 기타 타입
            try:
                return str(obj)
            except:
                return None
        
        return {
            "session_id": self.session_id,
            "owner": self.owner,
            "repo": self.repo,
            "ref": self.ref,
            "conversation_history": _serialize(self.conversation_history),
            "accumulated_context": _serialize(dict(self.accumulated_context)),
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat(),
            "total_turns": self.total_turns,
            "trace": _serialize(self.trace)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Session':
        """딕셔너리에서 세션 복원"""
        session = cls(
            session_id=data["session_id"],
            owner=data["owner"],
            repo=data["repo"],
            ref=data.get("ref", "main")
        )
        session.conversation_history = data.get("conversation_history", [])
        session.accumulated_context = data.get("accumulated_context", {})
        session.created_at = datetime.fromisoformat(data["created_at"])
        session.last_active = datetime.fromisoformat(data["last_active"])
        session.total_turns = data.get("total_turns", 0)
        session.trace = data.get("trace", {})
        return session


# === 세션 저장소 (파일 기반 영구 저장) ===
import os
import json
import shutil

SESSION_DIR = "backend/data/sessions"

class SessionStore:
    """파일 기반 세션 저장소 (영속성 지원)"""
    
    def __init__(self):
        self._ttl_minutes = 60 # 1 hour TTL
        self._ensure_storage()
        logger.info(f"SessionStore initialized (Storage: {SESSION_DIR})")
    
    def _ensure_storage(self):
        """저장소 디렉토리 셋업"""
        os.makedirs(SESSION_DIR, exist_ok=True)
        
    def _get_path(self, session_id: str) -> str:
        return os.path.join(SESSION_DIR, f"{session_id}.json")
    
    def create_session(
        self,
        owner: str,
        repo: str,
        ref: str = "main"
    ) -> Session:
        """새 세션 생성"""
        session_id = str(uuid.uuid4())
        session = Session(
            session_id=session_id,
            owner=owner,
            repo=repo,
            ref=ref
        )
        self._save_session(session)
        logger.info(f"Session created: {session_id} for {owner}/{repo}")
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """세션 조회"""
        path = self._get_path(session_id)
        if not os.path.exists(path):
            logger.warning(f"Session file not found: {session_id}")
            return None
            
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            session = Session.from_dict(data)
            
            # 만료 체크
            if session.is_expired(self._ttl_minutes):
                logger.info(f"Session expired: {session_id}")
                self.delete_session(session_id)
                return None
            
            return session
        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return None
    
    def update_session(self, session: Session):
        """세션 업데이트"""
        session.last_active = datetime.now()
        self._save_session(session)
    
    def _save_session(self, session: Session):
        """세션을 파일로 저장"""
        path = self._get_path(session.session_id)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save session {session.session_id}: {e}")
    
    def delete_session(self, session_id: str) -> bool:
        """세션 삭제"""
        path = self._get_path(session_id)
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.info(f"Session deleted: {session_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete session {session_id}: {e}")
        return False
    
    def cleanup_expired_sessions(self):
        """만료된 세션 정리"""
        count = 0
        if not os.path.exists(SESSION_DIR):
            return
            
        for filename in os.listdir(SESSION_DIR):
            if not filename.endswith(".json"):
                 continue
            
            sid = filename[:-5]
            session = self.get_session(sid) # get_session inside checks expiry
            if session is None:
                # Already deleted or invalid
                count += 1
                
        if count > 0:
            logger.info(f"Cleaned up {count} expired sessions")
    
    def get_all_sessions(self) -> List[Session]:
        """모든 세션 조회 (디버깅용)"""
        sessions = []
        if os.path.exists(SESSION_DIR):
            for filename in os.listdir(SESSION_DIR):
                if filename.endswith(".json"):
                    sid = filename[:-5]
                    session = self.get_session(sid)
                    if session:
                        sessions.append(session)
        return sessions
    
    def get_session_count(self) -> int:
        """활성 세션 수"""
        return len(self.get_all_sessions())


# === 싱글톤 인스턴스 ===
_session_store_instance: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    """세션 저장소 싱글톤 인스턴스 반환"""
    global _session_store_instance
    if _session_store_instance is None:
        _session_store_instance = SessionStore()
    return _session_store_instance
