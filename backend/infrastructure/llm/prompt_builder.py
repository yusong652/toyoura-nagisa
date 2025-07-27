"""System-prompt builder utilities.

This module centralises the logic for building the system prompt fed into the
LLM.  The first step is simply **reading** the static template file
`base_prompt.md` so that individual LLM clients (GPT, Gemini, Anthropic …) can
reuse the same prompt without duplicating I/O code.

Later we will extend this module to inject dynamic environment context (date,
os/platform, working directory, git/sandbox hints, user memory, etc.) – mirroring
the approach used by gemini-cli – but for now it only supports loading the base
prompt contents.
"""

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache
from typing import Optional

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

# 1. Environment variable override (similar to GEMINI_SYSTEM_MD)
#    If ``NAGISA_SYSTEM_MD`` is set:
#      * "0" / "false" (case-insensitive)  →  disable file loading and use
#        *empty string* as base prompt (caller may append custom content).
#      * "1" / "true"                       →  enable but keep default path
#      * any other non-empty value           →  treat value as **absolute** path
#        to a custom markdown prompt file.
ENV_VAR = "NAGISA_SYSTEM_MD"

# 2. Default prompt file lives next to this module
DEFAULT_PROMPT_PATH = Path(__file__).with_name("base_prompt.md")


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

@lru_cache(maxsize=1)
def load_base_prompt() -> str:
    """Return the contents of *base_prompt.md* as a Unicode string.

    The lookup strategy is:
      1. Check ``$NAGISA_SYSTEM_MD`` env variable (see table above).
      2. Fallback to the default path ``backend/chat/base_prompt.md``.

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