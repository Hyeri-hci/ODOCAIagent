"""
Event/Artifact System - Observability infrastructure for the Agentic Orchestrator.

Logs all node starts/ends, routing decisions, intent detections, and final responses as events.
Designed to be compatible with OpenTelemetry span structures.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Literal, Optional

logger = logging.getLogger(__name__)


# Context Variables for session/span tracking

_current_session_id: ContextVar[Optional[str]] = ContextVar("session_id", default=None)
_current_turn_id: ContextVar[Optional[str]] = ContextVar("turn_id", default=None)
_current_span_id: ContextVar[Optional[str]] = ContextVar("span_id", default=None)
_parent_span_id: ContextVar[Optional[str]] = ContextVar("parent_span_id", default=None)


def get_session_id() -> Optional[str]:
    return _current_session_id.get()


def set_session_id(session_id: str) -> None:
    _current_session_id.set(session_id)


def get_turn_id() -> Optional[str]:
    return _current_turn_id.get()


def set_turn_id(turn_id: str) -> None:
    _current_turn_id.set(turn_id)


def generate_session_id() -> str:
    return f"sess_{uuid.uuid4().hex[:12]}"


def generate_turn_id() -> str:
    return f"turn_{uuid.uuid4().hex[:8]}"


def generate_span_id() -> str:
    return f"span_{uuid.uuid4().hex[:16]}"


# Event Types

class EventType(str, Enum):
    """Defines the types of events that can be emitted."""
    # Supervisor Level
    SUPERVISOR_INTENT_DETECTED = "supervisor.intent_detected"
    SUPERVISOR_PLAN_BUILT = "supervisor.plan_built"
    SUPERVISOR_ROUTE_SELECTED = "supervisor.route_selected"
    
    # Node Level
    NODE_STARTED = "node.started"
    NODE_FINISHED = "node.finished"
    
    # Artifact Level
    ARTIFACT_CREATED = "artifact.created"
    ARTIFACT_REFERENCED = "artifact.referenced"
    
    # LLM Level
    LLM_CALL_STARTED = "llm.call_started"
    LLM_CALL_FINISHED = "llm.call_finished"
    
    # Answer Level
    ANSWER_GENERATED = "answer.generated"
    ANSWER_VALIDATED = "answer.validated"
    
    # Error Level
    ERROR_OCCURRED = "error.occurred"
    ERROR_RECOVERED = "error.recovered"


# Event Data Structure

@dataclass
class Event:
    """Represents a single event in the system."""
    type: EventType
    timestamp: float = field(default_factory=time.time)
    session_id: Optional[str] = None
    turn_id: Optional[str] = None
    span_id: Optional[str] = None
    parent_span_id: Optional[str] = None
    actor: str = "supervisor"  # e.g., supervisor | node:<name> | llm
    
    # Event data
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    artifacts_in: List[str] = field(default_factory=list)
    artifacts_out: List[str] = field(default_factory=list)
    
    # Performance metrics
    duration_ms: Optional[float] = None
    token_count: Optional[int] = None
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value if isinstance(self.type, EventType) else self.type,
            "timestamp": self.timestamp,
            "timestamp_iso": datetime.fromtimestamp(self.timestamp).isoformat(),
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "actor": self.actor,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "artifacts_in": self.artifacts_in,
            "artifacts_out": self.artifacts_out,
            "duration_ms": self.duration_ms,
            "token_count": self.token_count,
            "metadata": self.metadata,
        }


# Event Store (In-Memory)

class EventStore:
    """An in-memory store for events."""
    
    def __init__(self, max_events: int = 10000):
        self._events: List[Event] = []
        self._max_events = max_events
        self._listeners: List[Callable[[Event], None]] = []
    
    def append(self, event: Event) -> None:
        # Prune old events if max size is exceeded
        if len(self._events) >= self._max_events:
            self._events = self._events[-(self._max_events // 2):]
        
        self._events.append(event)
        
        # Notify listeners
        for listener in self._listeners:
            try:
                listener(event)
            except Exception as e:
                logger.warning(f"Event listener error: {e}")
    
    def get_by_session(self, session_id: str) -> List[Event]:
        return [e for e in self._events if e.session_id == session_id]
    
    def get_by_turn(self, session_id: str, turn_id: str) -> List[Event]:
        return [
            e for e in self._events 
            if e.session_id == session_id and e.turn_id == turn_id
        ]
    
    def get_span_tree(self, session_id: str, turn_id: str) -> Dict[str, List[Event]]:
        """Returns events in a span tree structure (Jaeger compatible)."""
        events = self.get_by_turn(session_id, turn_id)
        tree: Dict[str, List[Event]] = {}
        for e in events:
            parent = e.parent_span_id or "root"
            if parent not in tree:
                tree[parent] = []
            tree[parent].append(e)
        return tree
    
    def add_listener(self, listener: Callable[[Event], None]) -> None:
        self._listeners.append(listener)
    
    def clear(self) -> None:
        self._events.clear()


# Global event store instance
_event_store = EventStore()


def get_event_store() -> EventStore:
    return _event_store


# Artifact Store (Content-addressable storage)

@dataclass
class Artifact:
    """Represents a stored artifact."""
    id: str  # sha256 based
    kind: str  # e.g., diagnosis_raw, python_metrics, summary
    session_id: str
    turn_id: Optional[str]
    content: Any
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ArtifactStore:
    """Content-addressable storage for artifacts."""
    
    def __init__(self):
        self._artifacts: Dict[str, Artifact] = {}
        self._by_session: Dict[str, List[str]] = {}  # session_id -> artifact_ids
    
    def _compute_hash(self, content: Any) -> str:
        """Computes a hash based on the content."""
        if isinstance(content, (dict, list)):
            serialized = json.dumps(content, sort_keys=True, default=str)
        else:
            serialized = str(content)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]
    
    def persist(
        self, 
        session_id: str, 
        kind: str, 
        content: Any,
        turn_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Saves an artifact and returns its ID."""
        content_hash = self._compute_hash(content)
        artifact_id = f"{kind}_{content_hash}"
        
        artifact = Artifact(
            id=artifact_id,
            kind=kind,
            session_id=session_id,
            turn_id=turn_id or get_turn_id(),
            content=content,
            metadata=metadata or {}
        )
        
        self._artifacts[artifact_id] = artifact
        
        if session_id not in self._by_session:
            self._by_session[session_id] = []
        if artifact_id not in self._by_session[session_id]:
            self._by_session[session_id].append(artifact_id)
        
        return artifact_id
    
    def get(self, artifact_id: str) -> Optional[Artifact]:
        return self._artifacts.get(artifact_id)
    
    def exists(self, artifact_id: str) -> bool:
        return artifact_id in self._artifacts
    
    def get_by_session(self, session_id: str) -> List[Artifact]:
        artifact_ids = self._by_session.get(session_id, [])
        return [self._artifacts[aid] for aid in artifact_ids if aid in self._artifacts]
    
    def get_by_kind(self, session_id: str, kind: str) -> List[Artifact]:
        return [a for a in self.get_by_session(session_id) if a.kind == kind]


# Global artifact store instance
_artifact_store = ArtifactStore()


def get_artifact_store() -> ArtifactStore:
    return _artifact_store


# Event Emission Helpers

def emit_event(
    event_type: EventType,
    *,
    actor: str = "supervisor",
    inputs: Optional[Dict[str, Any]] = None,
    outputs: Optional[Dict[str, Any]] = None,
    artifacts_in: Optional[List[str]] = None,
    artifacts_out: Optional[List[str]] = None,
    duration_ms: Optional[float] = None,
    token_count: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Event:
    """Creates and stores an event."""
    event = Event(
        type=event_type,
        session_id=get_session_id(),
        turn_id=get_turn_id(),
        span_id=_current_span_id.get(),
        parent_span_id=_parent_span_id.get(),
        actor=actor,
        inputs=inputs or {},
        outputs=outputs or {},
        artifacts_in=artifacts_in or [],
        artifacts_out=artifacts_out or [],
        duration_ms=duration_ms,
        token_count=token_count,
        metadata=metadata or {},
    )
    
    _event_store.append(event)
    
    # Debug logging (controlled by environment variable)
    if os.getenv("ODOC_EVENT_DEBUG", "").lower() in ("1", "true"):
        logger.debug(f"[EVENT] {event_type.value}: {json.dumps(event.to_dict(), default=str)}")
    
    return event


def persist_artifact(
    kind: str, 
    content: Any, 
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """Persists an artifact and emits a corresponding event."""
    session_id = get_session_id()
    if not session_id:
        session_id = generate_session_id()
        set_session_id(session_id)
    
    artifact_id = _artifact_store.persist(
        session_id=session_id,
        kind=kind,
        content=content,
        metadata=metadata
    )
    
    emit_event(
        EventType.ARTIFACT_CREATED,
        outputs={"artifact_id": artifact_id, "kind": kind},
        artifacts_out=[artifact_id]
    )
    
    return artifact_id


def ensure_artifacts_exist(artifact_ids: List[str]) -> bool:
    """Checks if all given artifact IDs exist in the store."""
    for aid in artifact_ids:
        if not _artifact_store.exists(aid):
            logger.warning(f"Artifact not found: {aid}")
            return False
    return True


# Span Context Manager

class SpanContext:
    """A context manager for a trace span (used with `with`)."""
    
    def __init__(self, name: str, actor: str = "supervisor"):
        self.name = name
        self.actor = actor
        self.span_id = generate_span_id()
        self.parent_span_id: Optional[str] = None
        self.start_time: float = 0
        self._prev_span_id: Optional[str] = None
        self._prev_parent_span_id: Optional[str] = None
    
    def __enter__(self) -> "SpanContext":
        self._prev_span_id = _current_span_id.get()
        self._prev_parent_span_id = _parent_span_id.get()
        
        self.parent_span_id = self._prev_span_id
        _current_span_id.set(self.span_id)
        _parent_span_id.set(self.parent_span_id)
        
        self.start_time = time.time()
        emit_event(
            EventType.NODE_STARTED,
            actor=self.actor,
            inputs={"node_name": self.name}
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        duration_ms = (time.time() - self.start_time) * 1000
        
        outputs = {"node_name": self.name}
        if exc_type is not None:
            outputs["error"] = str(exc_val)
            emit_event(
                EventType.ERROR_OCCURRED,
                actor=self.actor,
                outputs=outputs,
                duration_ms=duration_ms
            )
        
        emit_event(
            EventType.NODE_FINISHED,
            actor=self.actor,
            outputs=outputs,
            duration_ms=duration_ms
        )
        
        _current_span_id.set(self._prev_span_id)
        _parent_span_id.set(self._prev_parent_span_id)


def span(name: str, actor: str = "supervisor") -> SpanContext:
    """Creates a new span context manager."""
    return SpanContext(name, actor)


# Turn Context Manager

class TurnContext:
    """A context manager for a conversation turn."""
    
    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or generate_session_id()
        self.turn_id = generate_turn_id()
        self._prev_session_id: Optional[str] = None
        self._prev_turn_id: Optional[str] = None
    
    def __enter__(self) -> "TurnContext":
        self._prev_session_id = get_session_id()
        self._prev_turn_id = get_turn_id()
        
        set_session_id(self.session_id)
        set_turn_id(self.turn_id)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._prev_session_id:
            set_session_id(self._prev_session_id)
        if self._prev_turn_id:
            set_turn_id(self._prev_turn_id)


def turn_context(session_id: Optional[str] = None) -> TurnContext:
    """Creates a new turn context manager."""
    return TurnContext(session_id)
