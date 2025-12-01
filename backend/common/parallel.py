"""Parallel execution utilities based on concurrent.futures."""
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
    """Runs multiple functions in parallel and returns a dictionary of results."""
    results: Dict[str, T] = {}
    errors: Dict[str, Exception] = {}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_key = {
            executor.submit(func): key
            for key, func in tasks.items()
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                results[key] = future.result()
                logger.debug("Parallel task completed: %s", key)
            except Exception as exc:
                logger.warning("Parallel task failed: %s - %s", key, exc)
                errors[key] = exc
    
    # If any errors occurred, raise the first one
    if errors:
        first_key = next(iter(errors))
        raise errors[first_key]
    
    return results


def run_parallel_safe(
    tasks: Dict[str, Callable[[], T]],
    max_workers: int = DEFAULT_MAX_WORKERS,
    default: T = None,  # type: ignore
) -> Tuple[Dict[str, T], Dict[str, Exception]]:
    """Runs in parallel and continues on error. Returns: (results, errors) tuple."""
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
