"""
비동기 유틸리티 - 재시도, 에러 처리, 부분 결과 활용
"""

import asyncio
import logging
from typing import Callable, Any, Optional, TypeVar, Dict
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


async def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    backoff_base: int = 2,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable] = None
) -> Any:
    """
    지수 백오프를 사용한 재시도
    
    Args:
        func: 실행할 비동기 함수
        max_retries: 최대 재시도 횟수
        backoff_base: 백오프 기본값 (초)
        exceptions: 재시도할 예외 타입들
        on_retry: 재시도 시 호출할 콜백
    
    Returns:
        함수 실행 결과
    
    Raises:
        마지막 재시도 실패 시 예외
    """
    
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            return await func()
        except exceptions as e:
            last_exception = e
            
            if attempt == max_retries - 1:
                logger.error(
                    f"Failed after {max_retries} attempts: {e}",
                    exc_info=True
                )
                raise
            
            wait_time = backoff_base ** attempt
            logger.warning(
                f"Attempt {attempt + 1}/{max_retries} failed: {e}. "
                f"Retrying in {wait_time}s..."
            )
            
            if on_retry:
                await on_retry(attempt, e)
            
            await asyncio.sleep(wait_time)
    
    raise last_exception


def async_with_fallback(fallback_value: Any = None):
    """
    에러 발생 시 fallback 값 반환하는 데코레이터
    
    Usage:
        @async_with_fallback(fallback_value={})
        async def some_function():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(
                    f"{func.__name__} failed, using fallback: {e}",
                    exc_info=True
                )
                return fallback_value
        return wrapper
    return decorator


async def gather_with_partial_results(
    *coroutines,
    return_exceptions: bool = True
) -> Dict[str, Any]:
    """
    여러 코루틴을 병렬 실행하고 부분 결과 활용
    
    Args:
        *coroutines: 실행할 코루틴들
        return_exceptions: 예외를 결과에 포함할지 여부
    
    Returns:
        {
            "results": [성공한 결과들],
            "errors": [발생한 에러들],
            "success_count": int,
            "error_count": int
        }
    """
    
    results = await asyncio.gather(*coroutines, return_exceptions=return_exceptions)
    
    successful = []
    errors = []
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            errors.append({
                "index": i,
                "error": str(result),
                "type": type(result).__name__
            })
            logger.error(f"Coroutine {i} failed: {result}")
        else:
            successful.append(result)
    
    return {
        "results": successful,
        "errors": errors,
        "success_count": len(successful),
        "error_count": len(errors),
        "total": len(results)
    }


async def timeout_with_default(
    coro: Callable,
    timeout_seconds: float,
    default_value: Any = None
) -> Any:
    """
    타임아웃 적용 및 기본값 반환
    
    Args:
        coro: 실행할 코루틴
        timeout_seconds: 타임아웃 (초)
        default_value: 타임아웃 시 반환할 기본값
    
    Returns:
        코루틴 결과 또는 기본값
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.warning(
            f"Operation timed out after {timeout_seconds}s, "
            f"returning default value"
        )
        return default_value
    except Exception as e:
        logger.error(f"Operation failed: {e}", exc_info=True)
        return default_value


class GracefulDegradation:
    """부분 결과를 활용한 우아한 성능 저하"""
    
    def __init__(self):
        self.partial_results: Dict[str, Any] = {}
        self.errors: Dict[str, Exception] = {}
    
    async def try_execute(
        self,
        key: str,
        func: Callable,
        required: bool = False
    ) -> Optional[Any]:
        """
        함수 실행 시도
        
        Args:
            key: 결과를 저장할 키
            func: 실행할 비동기 함수
            required: 필수 여부 (실패 시 예외 발생)
        
        Returns:
            실행 결과 또는 None
        """
        try:
            result = await func()
            self.partial_results[key] = result
            logger.info(f"Successfully executed: {key}")
            return result
        except Exception as e:
            self.errors[key] = e
            logger.error(f"Failed to execute {key}: {e}", exc_info=True)
            
            if required:
                raise
            
            return None
    
    def get_result(self, key: str, default: Any = None) -> Any:
        """결과 조회"""
        return self.partial_results.get(key, default)
    
    def has_minimum_required(self, required_keys: list) -> bool:
        """최소 필수 결과 확인"""
        return all(key in self.partial_results for key in required_keys)
    
    def get_summary(self) -> Dict[str, Any]:
        """실행 요약"""
        return {
            "successful": list(self.partial_results.keys()),
            "failed": list(self.errors.keys()),
            "success_count": len(self.partial_results),
            "error_count": len(self.errors),
            "errors": {k: str(v) for k, v in self.errors.items()}
        }


# === GitHub API 전용 재시도 ===

async def github_api_retry(
    func: Callable,
    max_retries: int = 3
) -> Any:
    """
    GitHub API 호출 재시도 (Rate Limit 고려)
    
    Rate Limit 에러 시:
    - 429: 1분 대기 후 재시도
    - 403: 30초 대기 후 재시도
    - 기타: 지수 백오프
    """
    
    async def on_retry(attempt: int, error: Exception):
        """재시도 시 처리"""
        error_msg = str(error).lower()
        
        if "rate limit" in error_msg or "429" in error_msg:
            logger.warning("Rate limit hit, waiting 60s...")
            await asyncio.sleep(60)
        elif "403" in error_msg:
            logger.warning("Forbidden error, waiting 30s...")
            await asyncio.sleep(30)
    
    return await retry_with_backoff(
        func=func,
        max_retries=max_retries,
        backoff_base=2,
        on_retry=on_retry
    )
