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
PROMPTS_DIR = BACKEND_DIR / "config" / "prompts"

# Environment variable overrides
ENV_BASE_PROMPT = "NAGISA_BASE_PROMPT"
ENV_SYSTEM_MD = "NAGISA_SYSTEM_MD"  # Legacy support

# Prompt file paths
DEFAULT_BASE_PROMPT = PROMPTS_DIR / "base_prompt.md"
DEFAULT_EXPRESSION_PROMPT = PROMPTS_DIR / "expression_prompt.md"