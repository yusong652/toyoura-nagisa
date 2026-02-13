"""
Configuration and constants for prompt system.
"""

from pathlib import Path

# Base path configuration
# Navigate from packages/backend/shared/utils/prompt/config.py to project root
# packages/backend/shared/utils/prompt -> packages/backend/shared/utils -> packages/backend/shared -> packages/backend -> packages -> project_root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent
BASE_DIR = PROJECT_ROOT  # Project root for workspace/pfc_workspace
BACKEND_DIR = PROJECT_ROOT / "packages" / "backend"  # Backend directory for config files
CHAT_DIR = PROJECT_ROOT / "chat"
TOOL_DB_PATH = BACKEND_DIR / "tool_db"  # Legacy, may not exist
LOCATION_DB_PATH = BACKEND_DIR / "location_data"  # Legacy, may not exist


def get_prompt_directories() -> list[Path]:
    """Return prompt directory candidates in resolution order."""
    return [
        PROJECT_ROOT / "config" / "prompts",
        BACKEND_DIR / "config" / "prompts",
    ]


def get_prompts_dir() -> Path:
    """Return the first existing prompt directory, or the primary target path."""
    for candidate in get_prompt_directories():
        if candidate.exists():
            return candidate
    return get_prompt_directories()[0]


PROMPTS_DIR = get_prompts_dir()

# Environment variable overrides
ENV_BASE_PROMPT = "NAGISA_BASE_PROMPT"
ENV_SYSTEM_MD = "NAGISA_SYSTEM_MD"  # Legacy support

# Prompt file paths
DEFAULT_BASE_PROMPT = PROMPTS_DIR / "base_prompt.md"
DEFAULT_EXPRESSION_PROMPT = PROMPTS_DIR / "expression_prompt.md"
