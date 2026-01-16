"""
Default configuration values shared across LLM providers.

Common default values and settings that can be used by all provider implementations.
"""

DEFAULT_FEW_SHOT_MAX_LENGTH = 5
DEFAULT_CONTEXT_MESSAGE_COUNT = 6
DEFAULT_MAX_HISTORY_LENGTH = 10

# Title generation defaults
DEFAULT_TITLE_MAX_LENGTH = 50
DEFAULT_TITLE_GENERATION_TEMPERATURE = 0.3

# API timeout defaults
DEFAULT_API_TIMEOUT = 60

# Model configuration defaults
DEFAULT_MAX_OUTPUT_TOKENS = 8192
DEFAULT_TEMPERATURE = 0.7

# Default temperature for web search
DEFAULT_WEB_SEARCH_TEMPERATURE = 0.1
