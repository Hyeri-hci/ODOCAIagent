"""
Structured Logging 설정.

환경변수:
- LOG_LEVEL: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- LOG_FORMAT: 로그 형식 (text, json)
- LOG_FILE: 로그 파일 경로 (선택)
- LANGSMITH_TRACING: LangSmith 트레이싱 활성화 (true/false)
"""
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Optional


class JsonFormatter(logging.Formatter):
    """
    JSON 형식 로그 포맷터.
    
    구조화된 로깅을 위해 JSON 형식으로 로그를 출력합니다.
    모니터링 시스템(ELK, CloudWatch 등)과의 연동에 유용합니다.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """로그 레코드를 JSON 문자열로 변환."""
        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # 예외 정보 추가
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        
        # 추가 컨텍스트 (extra 필드)
        for key, value in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "exc_info", "exc_text", "thread", "threadName",
                "message", "taskName"
            ):
                log_obj[key] = value
        
        return json.dumps(log_obj, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """
    가독성 높은 텍스트 포맷터.
    
    개발 환경에서 사용하기 좋은 컬러풀한 텍스트 형식입니다.
    """
    
    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"
    
    def format(self, record: logging.LogRecord) -> str:
        """로그 레코드를 컬러 텍스트로 변환."""
        color = self.COLORS.get(record.levelname, "")
        
        # asctime 생성 (formatTime 호출)
        record.asctime = self.formatTime(record, self.datefmt)
        
        # 기본 포맷
        formatted = (
            f"{record.asctime} | {color}{record.levelname:8}{self.RESET} | "
            f"{record.name} | {record.getMessage()}"
        )
        
        # 예외 정보 추가
        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"
        
        return formatted


def get_formatter(format_type: str) -> logging.Formatter:
    """
    로그 형식에 따른 포맷터 반환.
    
    Args:
        format_type: 'json' 또는 'text'
    
    Returns:
        해당 형식의 Formatter 인스턴스
    """
    if format_type.lower() == "json":
        return JsonFormatter()
    else:
        formatter = TextFormatter()
        formatter.datefmt = "%Y-%m-%d %H:%M:%S"
        return formatter


def setup_logging(
    level: Optional[str] = None,
    log_file: Optional[str] = None,
    log_format: Optional[str] = None
) -> None:
    """
    애플리케이션 로깅 설정.
    
    환경변수 또는 파라미터로 설정할 수 있습니다.
    파라미터가 환경변수보다 우선합니다.
    
    Args:
        level: 로그 레벨 (기본값: INFO, 환경변수: LOG_LEVEL)
        log_file: 로그 파일 경로 (환경변수: LOG_FILE)
        log_format: 로그 형식 'text' 또는 'json' (기본값: text, 환경변수: LOG_FORMAT)
    
    Example:
        >>> setup_logging(level="DEBUG", log_format="json")
        >>> logger = logging.getLogger(__name__)
        >>> logger.info("메시지", extra={"user_id": "123", "action": "login"})
    """
    # 환경변수에서 기본값 로드
    level = level or os.getenv("LOG_LEVEL", "INFO")
    log_file = log_file or os.getenv("LOG_FILE")
    log_format = log_format or os.getenv("LOG_FORMAT", "text")
    
    handlers: list[logging.Handler] = []
    formatter = get_formatter(log_format)
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    handlers.append(console_handler)
    
    # File Handler (Optional)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        # 파일은 항상 JSON 형식으로 저장 (분석 용이)
        file_handler.setFormatter(JsonFormatter())
        handlers.append(file_handler)
    
    # Root Logger Config
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        handlers=handlers,
        force=True  # 기존 설정 덮어쓰기
    )
    
    # Suppress noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    # LangSmith 트레이싱 설정 로깅
    if os.getenv("LANGSMITH_TRACING", "").lower() == "true":
        logging.getLogger("backend").info(
            "LangSmith tracing enabled",
            extra={"langsmith_project": os.getenv("LANGSMITH_PROJECT", "default")}
        )


def get_logger(name: str) -> logging.Logger:
    """
    모듈별 로거 생성 헬퍼.
    
    추가 컨텍스트와 함께 로깅할 수 있는 래퍼를 제공합니다.
    
    Args:
        name: 로거 이름 (보통 __name__)
    
    Returns:
        logging.Logger 인스턴스
    
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("분석 시작", extra={"repo": "owner/repo", "session_id": "abc123"})
    """
    return logging.getLogger(name)


class LogContext:
    """
    로그 컨텍스트 매니저.
    
    특정 작업 범위 내에서 공통 컨텍스트를 자동으로 추가합니다.
    
    Example:
        >>> with LogContext(logger, session_id="abc123", repo="owner/repo"):
        ...     logger.info("작업 시작")  # session_id, repo 자동 포함
        ...     do_something()
        ...     logger.info("작업 완료")
    """
    
    def __init__(self, logger: logging.Logger, **context: Any):
        self.logger = logger
        self.context = context
        self._old_factory: Any = None
    
    def __enter__(self) -> "LogContext":
        """컨텍스트 진입 시 LogRecord 팩토리 설정."""
        old_factory = logging.getLogRecordFactory()
        self._old_factory = old_factory
        context = self.context
        
        def record_factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
            record = old_factory(*args, **kwargs)
            for key, value in context.items():
                setattr(record, key, value)
            return record
        
        logging.setLogRecordFactory(record_factory)
        return self
    
    def __exit__(self, *args: Any) -> None:
        """컨텍스트 종료 시 원래 팩토리 복원."""
        if self._old_factory:
            logging.setLogRecordFactory(self._old_factory)
