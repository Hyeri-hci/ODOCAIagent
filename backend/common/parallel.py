"""concurrent.futures 기반 병렬 실행 유틸."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Tuple, TypeVar
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")
DEFAULT_MAX_WORKERS = 4


def run_parallel(
    tasks: Dict[str, Callable[[], T]],
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> Dict[str, T]:
    """여러 함수를 병렬 실행하고 결과 딕셔너리 반환."""
    results: Dict[str, T] = {}
    errors: Dict[str, Exception] = {}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 모든 작업 제출
        future_to_key = {
            executor.submit(func): key
            for key, func in tasks.items()
        }
        
        # 완료된 순서대로 결과 수집
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                results[key] = future.result()
                logger.debug("Parallel task completed: %s", key)
            except Exception as exc:
                logger.warning("Parallel task failed: %s - %s", key, exc)
                errors[key] = exc
    
    # 에러가 있으면 첫 번째 에러 raise
    if errors:
        first_key = next(iter(errors))
        raise errors[first_key]
    
    return results


def run_parallel_safe(
    tasks: Dict[str, Callable[[], T]],
    max_workers: int = DEFAULT_MAX_WORKERS,
    default: T = None,  # type: ignore
) -> Tuple[Dict[str, T], Dict[str, Exception]]:
    """병렬 실행 (에러 발생 시에도 계속 진행). 반환: (결과, 에러) 튜플."""
    results: Dict[str, T] = {}
    errors: Dict[str, Exception] = {}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_key = {
            executor.submit(func): key
            for key, func in tasks.items()
        }
        
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                results[key] = future.result()
            except Exception as exc:
                logger.warning("Parallel task failed: %s - %s", key, exc)
                errors[key] = exc
                results[key] = default
    
    return results, errors
