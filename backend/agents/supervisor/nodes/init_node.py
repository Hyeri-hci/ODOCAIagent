"""Init Node: Session initialization and validation."""
from __future__ import annotations

from typing import Any, Dict

from backend.agents.supervisor.models import SupervisorState
from backend.common.events import (
    EventType,
    emit_event,
    generate_session_id,
    generate_turn_id,
    set_session_id,
    set_turn_id,
    get_session_id,
    get_turn_id,
)


def init_node(state: SupervisorState) -> Dict[str, Any]:
    """Initializes session context and validates input."""
    existing_session_id = state.get("_session_id")
    if existing_session_id:
        set_session_id(existing_session_id)
    else:
        session_id = generate_session_id()
        set_session_id(session_id)
    
    turn_id = generate_turn_id()
    set_turn_id(turn_id)
    
    emit_event(
        EventType.NODE_STARTED,
        actor="supervisor",
        inputs={"node_name": "init_node"},
        outputs={
            "session_id": get_session_id(),
            "turn_id": get_turn_id(),
        }
    )
    
    return {
        "_session_id": get_session_id(),
        "_turn_id": turn_id,
    }
