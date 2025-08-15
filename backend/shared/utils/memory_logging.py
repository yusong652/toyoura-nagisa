"""
Memory injection logging utilities.

Provides consistent logging functions for memory injection operations.
"""

from backend.domain.models.memory_context import MemoryInjectionResult


def log_memory_injection_result(injection_result: MemoryInjectionResult, total_retrieval_time_ms: float) -> None:
    """
    Log memory injection results with consistent formatting.
    
    Args:
        injection_result: MemoryInjectionResult object with injection details
        total_retrieval_time_ms: Total retrieval time in milliseconds
    """
    if injection_result.success and injection_result.injected_count > 0:
        # Print useful memory context information
        print(f"[MEMORY] Injected {injection_result.injected_count} memories ({injection_result.context_tokens} tokens) in {total_retrieval_time_ms:.1f}ms")
        if injection_result.formatted_context:
            # Show the actual injected context (first 200 chars)
            context_preview = injection_result.formatted_context[:200] + "..." if len(injection_result.formatted_context) > 200 else injection_result.formatted_context
            print(f"[MEMORY] Context: {context_preview}")
    else:
        # Print debug information for 0 memory case
        print(f"[MEMORY] Found 0 memories in {total_retrieval_time_ms:.1f}ms - {injection_result.error or 'No relevant memories found'}")