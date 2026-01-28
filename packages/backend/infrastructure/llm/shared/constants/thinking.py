"""
Thinking level configuration mappings for LLM providers.

Unified thinking level definitions and provider-specific mappings.
All providers should import from here to ensure consistency.
"""

from typing import Dict, Any, Optional

# =============================================================================
# Unified Thinking Levels
# =============================================================================
# These are the standard thinking levels used across the application:
# - "default": No thinking / disabled (provider uses default behavior)
# - "low": Minimal thinking effort
# - "high": Maximum thinking effort

THINKING_LEVELS = ("default", "low", "high")

# Default thinking level when not specified
DEFAULT_THINKING_LEVEL = "high"


# =============================================================================
# OpenAI Mappings (reasoning.effort)
# =============================================================================
# OpenAI uses "effort" parameter: "low", "medium", "high"
# We map our levels to OpenAI's effort values

OPENAI_THINKING_LEVEL_TO_EFFORT: Dict[str, Optional[str]] = {
    "default": None,  # Don't pass reasoning param
    "low": "low",
    "high": "high",
}


# =============================================================================
# Anthropic Mappings (thinking.budget_tokens)
# =============================================================================
# Anthropic uses budget_tokens for thinking
# Requirement: max_tokens must be > budget_tokens

ANTHROPIC_THINKING_LEVEL_TO_BUDGET: Dict[str, int] = {
    "low": 4096,
    "high": 16384,
}


# =============================================================================
# Google Gemini Mappings
# =============================================================================
# Gemini 3.x: uses ThinkingLevel enum (LOW, HIGH)
# Gemini 2.5: uses thinking_budget (integer, -1 = auto)
#
# Note: These are string values. The actual enum conversion happens in client.py
# because it requires importing google.genai.types which may not be available.

GOOGLE_THINKING_LEVEL_MAP: Dict[str, str] = {
    "low": "LOW",
    "high": "HIGH",
}

GOOGLE_THINKING_LEVEL_TO_BUDGET: Dict[str, int] = {
    "low": 1024,
    "high": -1,  # -1 = dynamic (auto)
}
