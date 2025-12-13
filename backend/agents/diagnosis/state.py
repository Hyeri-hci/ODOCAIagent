"""
Diagnosis Agent State
"""
from typing import TypedDict, Optional, Dict, Any, Literal
from backend.agents.diagnosis.intent_parser import DiagnosisIntentV2

class DiagnosisGraphState(TypedDict):
    """Diagnosis Agent V2 State"""
    
    owner: str
    repo: str
    ref: str
    use_cache: bool
    execution_time_ms: int
    
    user_message: Optional[str]
    supervisor_intent: Optional[Dict[str, Any]]
    diagnosis_intent: Optional[DiagnosisIntentV2]
    cache_key: Optional[str]
    cached_result: Optional[Dict[str, Any]]
    execution_path: Optional[Literal["fast_path", "full_path", "reinterpret_path"]]
    result: Optional[Dict[str, Any]]
    error: Optional[str]
