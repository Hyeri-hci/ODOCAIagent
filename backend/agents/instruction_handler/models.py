"""Instruction Handler Agent Models."""
from dataclasses import dataclass
from backend.core.models import ProjectRules, UserGuidelines

@dataclass
class InstructionRequest:
    """사용자 자연어 지침 요청."""
    raw_instruction: str
    context: Optional[str] = None

@dataclass
class InstructionResult:
    """지침 변환 결과."""
    project_rules_update: Optional[ProjectRules]
    session_guidelines_update: Optional[UserGuidelines]
    clarification_needed: bool
    message: str
