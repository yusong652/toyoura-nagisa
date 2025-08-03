"""
OpenAI Client Constants

Common constants and default values used throughout the OpenAI client implementation.
"""

# Model identifiers
DEFAULT_MODEL = "gpt-4o"
DEFAULT_TITLE_MODEL = "gpt-4o-mini"
DEFAULT_IMAGE_PROMPT_MODEL = "gpt-4o-mini"

# API parameters
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = None  # Use model default
DEFAULT_TOP_P = 1.0
DEFAULT_FREQUENCY_PENALTY = 0.0
DEFAULT_PRESENCE_PENALTY = 0.0

# Timeout and retry settings
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3

# Tool calling settings
MAX_TOOL_ITERATIONS = 10
TOOL_CALL_TIMEOUT = 30.0

# Content generation settings
TITLE_GENERATION_TEMPERATURE = 1.0
TITLE_MAX_LENGTH = 30
IMAGE_PROMPT_TEMPERATURE = 0.8

# Debug settings
DEBUG_TRUNCATE_LENGTH = 500

# Error messages
API_ERROR_PREFIX = "OpenAI API error"
TOOL_EXECUTION_ERROR = "Tool execution failed"
TIMEOUT_ERROR = "Request timeout"

# Content types
SUPPORTED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/gif", "image/webp"]
MAX_IMAGE_SIZE = 20_000_000  # 20MB

# Prompt templates
THINKING_INSTRUCTION = """Think step-by-step in a private section wrapped inside <thinking> and </thinking> tags. This section will be removed before the answer is shown to the user. After the tag, provide the final answer for the user. Never reveal or reference these tags."""