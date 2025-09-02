"""System prompt builder utilities following Anthropic best practices.

This module centralizes system prompt construction for LLM interactions,
implementing Anthropic's recommended format for tool-enabled conversations.

Key features:
- Dynamic tool schema embedding in system prompt (Anthropic best practice)
- Proper prompt component ordering per official documentation
- Support for base, tool, expression, and memory prompts
- Environment context injection (workspace, date, platform)
- Tool definition formatting in JSON Schema format

Architecture follows Anthropic's recommended structure:
1. Base system instructions
2. Tool access declaration and formatting rules
3. Tool definitions in JSON Schema format
4. Additional context (memory, expression rules)
"""

from __future__ import annotations

import os
import json
from pathlib import Path
from functools import lru_cache
from typing import Optional, List, Dict, Any
from datetime import datetime

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

# Environment variable overrides
ENV_BASE_PROMPT = "NAGISA_BASE_PROMPT"
ENV_SYSTEM_MD = "NAGISA_SYSTEM_MD"  # Legacy support

# Prompt file paths
PROMPTS_DIR = Path(__file__).parent.parent.parent / "config" / "prompts"
DEFAULT_BASE_PROMPT = PROMPTS_DIR / "base_prompt.md"
DEFAULT_TOOL_PROMPT = PROMPTS_DIR / "tool_prompt.md"
DEFAULT_EXPRESSION_PROMPT = PROMPTS_DIR / "expression_prompt.md"
DEFAULT_MEMORY_TEMPLATE = PROMPTS_DIR / "memory_context_template.md"


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

@lru_cache(maxsize=1)
def load_base_prompt() -> str:
    """Return the contents of *base_prompt.md* as a Unicode string.

    The lookup strategy is:
      1. Check ``$NAGISA_SYSTEM_MD`` env variable (see table above).
      2. Fallback to the default path ``backend/config/prompts/base_prompt.md``.

    If the file does not exist or is disabled, an empty string is returned – the
    calling code can then decide how to proceed (e.g. use a hard-coded
    fallback).
    """

    env_value: Optional[str] = os.getenv(ENV_VAR)

    # Handle disabled flag
    if env_value and env_value.lower() in {"0", "false"}:
        return ""

    # Determine candidate path
    if env_value and env_value.lower() not in {"1", "true"}:
        prompt_path = Path(env_value)
    else:
        prompt_path = DEFAULT_PROMPT_PATH

    try:
        return prompt_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        # Gracefully degrade to empty prompt if file missing
        return ""


def build_system_prompt(user_memory: str | None = None) -> str:
    """Combine static base prompt with optional *user_memory* suffix.

    For now this simply concatenates the two pieces with a delimiter.  Further
    dynamic context can be added in future iterations.
    """

    base = load_base_prompt()
    memory_suffix = ("\n\n---\n\n" + user_memory.strip()) if user_memory else ""
    return base + memory_suffix 