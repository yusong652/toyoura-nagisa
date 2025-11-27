"""
Model context window limits.

Placeholder configuration for LLM model context window sizes.
TODO: Implement per-model max_tokens lookup based on actual model name.
"""

# Default maximum context window size (tokens)
# Currently using 128k as a conservative default
DEFAULT_MAX_TOKENS = 128_000
