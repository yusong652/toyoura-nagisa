"""
Configuration and constants for prompt system.
"""

from pathlib import Path

# Base path configuration
BASE_DIR = Path(__file__).parent.parent.parent.parent  # backend/
CHAT_DIR = BASE_DIR / "chat"
TOOL_DB_PATH = BASE_DIR / "tool_db"
LOCATION_DB_PATH = BASE_DIR / "location_data"
PROMPTS_DIR = BASE_DIR / "config" / "prompts"

# Environment variable overrides
ENV_BASE_PROMPT = "NAGISA_BASE_PROMPT"
ENV_SYSTEM_MD = "NAGISA_SYSTEM_MD"  # Legacy support

# Prompt file paths
DEFAULT_BASE_PROMPT = PROMPTS_DIR / "base_prompt.md"
DEFAULT_TOOL_PROMPT = PROMPTS_DIR / "tool_prompt.md"
DEFAULT_EXPRESSION_PROMPT = PROMPTS_DIR / "expression_prompt.md"
DEFAULT_MEMORY_TEMPLATE = PROMPTS_DIR / "memory_context_template.md"