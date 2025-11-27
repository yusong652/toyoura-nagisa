"""
Performance measurement utilities.

Provides decorators and utilities for measuring execution time.
"""

import time
import functools
import inspect
from typing import Callable, Any, Tuple


def measure_time(func: Callable) -> Callable:
    """
    Decorator that measures execution time and returns the result along with timing.
    
    For async functions, returns (result, execution_time_ms).
    For regular functions, returns (result, execution_time_ms).
    
    Args:
        func: Function to measure
        
    Returns:
        Decorated function that returns (result, execution_time_ms)
    """
    if inspect.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Tuple[Any, float]:
            start_time = time.time()
            result = await func(*args, **kwargs)
            end_time = time.time()
            execution_time_ms = (end_time - start_time) * 1000
            return result, execution_time_ms
        return async_wrapper
    else:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Tuple[Any, float]:
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            execution_time_ms = (end_time - start_time) * 1000
            return result, execution_time_ms
        return sync_wrapper