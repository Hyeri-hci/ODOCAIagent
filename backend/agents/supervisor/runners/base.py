"""Base ExpertRunner: Unified runner interface with error policy and artifact collection."""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar

from backend.agents.shared.contracts import (
    AnswerContract,
    RunnerOutput,
    RunnerStatus,
    ErrorKind,
    ErrorAction,
    ERROR_POLICY,
    safe_get,
)
from backend.common.events import EventType, emit_event

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ErrorPolicy(Enum):
    """Error handling policy for runners."""
    RETRY = "retry"
    FALLBACK = "fallback"
    ASK_USER = "ask_user"
    ABORT = "abort"


@dataclass
class RunnerResult:
    """Result from an expert runner execution."""
    success: bool
    answer: Optional[AnswerContract] = None
    artifacts_out: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    degraded: bool = False
    meta: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def ok(
        cls,
        answer: AnswerContract,
        artifacts_out: List[str],
        meta: Optional[Dict[str, Any]] = None,
    ) -> "RunnerResult":
        return cls(
            success=True,
            answer=answer,
            artifacts_out=artifacts_out,
            meta=meta or {},
        )
    
    @classmethod
    def degraded_ok(
        cls,
        answer: AnswerContract,
        artifacts_out: List[str],
        reason: str,
    ) -> "RunnerResult":
        return cls(
            success=True,
            answer=answer,
            artifacts_out=artifacts_out,
            degraded=True,
            meta={"degrade_reason": reason},
        )
    
    @classmethod
    def fail(cls, error_message: str) -> "RunnerResult":
        return cls(
            success=False,
            error_message=error_message,
        )


@dataclass
class CollectedArtifact:
    """A collected artifact with its ID and kind."""
    id: str
    kind: str
    data: Any
    required: bool = True


class ArtifactCollector:
    """Collects artifacts required for runner execution."""
    
    def __init__(self, repo_id: str):
        self.repo_id = repo_id
        self.artifacts: Dict[str, CollectedArtifact] = {}
        self.errors: List[str] = []
    
    def add(
        self,
        kind: str,
        data: Any,
        artifact_id: Optional[str] = None,
        required: bool = True,
    ) -> str:
        """Adds an artifact to the collection."""
        aid = artifact_id or f"ARTIFACT:{kind.upper()}:{self.repo_id}"
        self.artifacts[kind] = CollectedArtifact(
            id=aid,
            kind=kind,
            data=data,
            required=required,
        )
        return aid
    
    def add_error(self, kind: str, error: str) -> None:
        """Records an artifact collection error."""
        self.errors.append(f"{kind}: {error}")
    
    def get(self, kind: str) -> Optional[Any]:
        """Gets artifact data by kind."""
        artifact = self.artifacts.get(kind)
        return artifact.data if artifact else None
    
    def get_ids(self) -> List[str]:
        """Gets all artifact IDs."""
        return [a.id for a in self.artifacts.values()]
    
    def get_kinds(self) -> List[str]:
        """Gets all artifact kinds."""
        return [a.kind for a in self.artifacts.values()]
    
    def has_required(self) -> bool:
        """Checks if all required artifacts are present."""
        for kind, artifact in self.artifacts.items():
            if artifact.required and artifact.data is None:
                return False
        return len(self.artifacts) > 0
    
    def missing_required(self) -> List[str]:
        """Returns list of missing required artifact kinds."""
        return [
            kind for kind, artifact in self.artifacts.items()
            if artifact.required and artifact.data is None
        ]


class ExpertRunner(ABC):
    """Base class for all expert runners."""
    
    runner_name: str = "base"
    required_artifacts: List[str] = []
    optional_artifacts: List[str] = []
    max_retries: int = 1
    retry_delay: float = 0.5
    
    def __init__(self, repo_id: str, user_context: Optional[Dict[str, Any]] = None):
        self.repo_id = repo_id
        self.user_context = user_context or {}
        self.collector = ArtifactCollector(repo_id)
        self._start_time: float = 0
    
    def set_artifact(self, kind: str, data: Any) -> None:
        """Sets an artifact directly (for pre-fetched data injection)."""
        self.collector.add(kind, data, required=True)
    
    def run(self) -> RunnerResult:
        """Main execution entry point with error handling."""
        self._start_time = time.time()
        
        emit_event(
            EventType.RUNNER_STARTED,
            actor=f"runner:{self.runner_name}",
            inputs={"repo_id": self.repo_id},
        )
        
        try:
            # Phase 1: Collect artifacts
            self._collect_artifacts()
            
            # Phase 2: Validate minimum requirements
            if not self._validate_artifacts():
                return self._handle_insufficient_artifacts()
            
            # Phase 3: Execute with retry policy
            result = self._execute_with_retry()
            
            # Phase 4: Validate output contract
            if result.success and result.answer:
                self._validate_answer_contract(result.answer)
            
            elapsed_ms = (time.time() - self._start_time) * 1000
            
            emit_event(
                EventType.RUNNER_FINISHED,
                actor=f"runner:{self.runner_name}",
                outputs={
                    "success": result.success,
                    "degraded": result.degraded,
                    "artifact_count": len(result.artifacts_out),
                    "elapsed_ms": elapsed_ms,
                },
            )
            
            result.meta["elapsed_ms"] = elapsed_ms
            return result
            
        except Exception as e:
            logger.exception(f"[{self.runner_name}] Unexpected error: {e}")
            return self._handle_error(e)
    
    @abstractmethod
    def _collect_artifacts(self) -> None:
        """Collects required and optional artifacts. Subclasses implement this."""
        pass
    
    @abstractmethod
    def _execute(self) -> RunnerResult:
        """Main execution logic. Subclasses implement this."""
        pass
    
    def _validate_artifacts(self) -> bool:
        """Validates that minimum artifacts are available."""
        return self.collector.has_required()
    
    def _execute_with_retry(self) -> RunnerResult:
        """Executes with retry policy."""
        last_error: Optional[Exception] = None
        
        for attempt in range(self.max_retries + 1):
            try:
                result = self._execute()
                if result.success:
                    return result
                
                # Execution returned failure, apply error policy
                policy = self._get_error_policy(result.error_message)
                
                if policy == ErrorPolicy.RETRY and attempt < self.max_retries:
                    logger.warning(f"[{self.runner_name}] Retry {attempt + 1}/{self.max_retries}")
                    time.sleep(self.retry_delay)
                    continue
                
                if policy == ErrorPolicy.FALLBACK:
                    return self._fallback_execute()
                
                if policy == ErrorPolicy.ASK_USER:
                    return self._ask_user_response(result.error_message)
                
                return result
                
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    logger.warning(f"[{self.runner_name}] Exception, retrying: {e}")
                    time.sleep(self.retry_delay)
                    continue
        
        # All retries exhausted
        return RunnerResult.fail(str(last_error) if last_error else "Execution failed")
    
    def _get_error_policy(self, error_message: Optional[str]) -> ErrorPolicy:
        """Determines error policy based on error message."""
        if not error_message:
            return ErrorPolicy.ABORT
        
        msg = error_message.lower()
        
        if "rate limit" in msg or "timeout" in msg:
            return ErrorPolicy.RETRY
        if "not found" in msg or "permission" in msg or "private" in msg:
            return ErrorPolicy.ASK_USER
        if "no data" in msg or "insufficient" in msg:
            return ErrorPolicy.FALLBACK
        
        return ErrorPolicy.FALLBACK
    
    def _fallback_execute(self) -> RunnerResult:
        """Fallback execution with relaxed requirements. Override in subclasses."""
        return RunnerResult.fail("Fallback not implemented")
    
    def _ask_user_response(self, error_message: Optional[str]) -> RunnerResult:
        """Creates a response asking user for clarification."""
        text = f"""요청을 처리하는 데 문제가 발생했습니다.

**문제**: {error_message or '알 수 없는 오류'}

**다음 행동**
- 저장소 URL이 올바른지 확인해 주세요
- 저장소가 공개인지 확인해 주세요
- 다른 저장소로 시도해 보세요"""
        
        answer = AnswerContract(
            text=text,
            sources=["SYS:ERROR:ASK_USER"],
            source_kinds=["system_error"],
        )
        return RunnerResult.degraded_ok(
            answer=answer,
            artifacts_out=["SYS:ERROR:ASK_USER"],
            reason="ask_user_triggered",
        )
    
    def _handle_insufficient_artifacts(self) -> RunnerResult:
        """Handles case where required artifacts are missing."""
        missing = self.collector.missing_required()
        errors = self.collector.errors
        
        # Try fallback first
        fallback_result = self._fallback_execute()
        if fallback_result.success:
            return fallback_result
        
        # Build error response
        text = f"""분석에 필요한 데이터를 가져오지 못했습니다.

**누락된 데이터**: {', '.join(missing) if missing else '없음'}
**오류**: {'; '.join(errors) if errors else '없음'}

**다음 행동**
- 저장소 URL이 올바른지 확인해 주세요
- 잠시 후 다시 시도해 주세요"""
        
        answer = AnswerContract(
            text=text,
            sources=["SYS:ERROR:INSUFFICIENT_ARTIFACTS"],
            source_kinds=["system_error"],
        )
        return RunnerResult.degraded_ok(
            answer=answer,
            artifacts_out=["SYS:ERROR:INSUFFICIENT_ARTIFACTS"],
            reason="insufficient_artifacts",
        )
    
    def _handle_error(self, error: Exception) -> RunnerResult:
        """Handles unexpected errors."""
        error_kind = self._classify_error(error)
        policy = ERROR_POLICY.get(error_kind, ErrorAction.ABORT)
        
        if policy == ErrorAction.ASK_USER:
            return self._ask_user_response(str(error))
        
        return RunnerResult.fail(str(error))
    
    def _classify_error(self, error: Exception) -> ErrorKind:
        """Classifies an exception to ErrorKind."""
        msg = str(error).lower()
        
        if "permission" in msg or "forbidden" in msg or "401" in msg or "403" in msg:
            return ErrorKind.PERMISSION
        if "not found" in msg or "404" in msg:
            return ErrorKind.NOT_FOUND
        if "timeout" in msg or "timed out" in msg:
            return ErrorKind.TIMEOUT
        if "rate limit" in msg or "429" in msg:
            return ErrorKind.RATE_LIMIT
        
        return ErrorKind.UNKNOWN
    
    def _validate_answer_contract(self, answer: AnswerContract) -> None:
        """Validates that answer has sources (sources == [] 방지)."""
        if not answer.sources:
            logger.warning(f"[{self.runner_name}] AnswerContract has empty sources!")
            # Auto-fill with collected artifacts
            if self.collector.get_ids():
                answer.sources = self.collector.get_ids()
                answer.source_kinds = self.collector.get_kinds()
            else:
                answer.sources = [f"RUNNER:{self.runner_name.upper()}:{self.repo_id}"]
                answer.source_kinds = ["runner_output"]
    
    def _build_answer(
        self,
        text: str,
        extra_sources: Optional[List[str]] = None,
        extra_kinds: Optional[List[str]] = None,
    ) -> AnswerContract:
        """Builds AnswerContract with collected artifact sources."""
        sources = self.collector.get_ids()
        kinds = self.collector.get_kinds()
        
        if extra_sources:
            sources.extend(extra_sources)
        if extra_kinds:
            kinds.extend(extra_kinds)
        
        # Ensure sources are not empty
        if not sources:
            sources = [f"RUNNER:{self.runner_name.upper()}:{self.repo_id}"]
            kinds = ["runner_output"]
        
        return AnswerContract(
            text=text,
            sources=sources,
            source_kinds=kinds,
        )
