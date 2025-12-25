"""
Core prompt loading and management functions.
"""

import os

from .config import PROMPTS_DIR, BASE_DIR


def _load_prompt_file(filename: str) -> str:
    """Load specified prompt file from config/prompts directory"""
    prompt_path = PROMPTS_DIR / filename
    try:
        return prompt_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def get_base_prompt(profile: str = "general") -> str:
    """
    Load base system prompt based on agent profile.

    Args:
        profile: Agent profile type (e.g., "general", "pfc", "coding", "lifestyle")

    Returns:
        Base system prompt string

    Priority:
        1. Environment variable NAGISA_BASE_PROMPT (overrides all)
        2. Profile-specific prompt file (e.g., pfc -> pfc_expert_prompt.md)
        3. Default base_prompt.md
    """
    base_prompt_from_env = os.getenv("NAGISA_BASE_PROMPT")
    if base_prompt_from_env is not None:
        return base_prompt_from_env.strip()

    # Profile-specific prompt mapping
    profile_prompts = {
        "pfc": "pfc_expert_prompt.md",  # Maps to AgentProfile.PFC = "pfc"
        "pfc_explorer": "pfc_explorer.md",  # PFC documentation SubAgent
        "pfc_diagnostic": "pfc_diagnostic.md",  # PFC multimodal diagnostic SubAgent
        "general": "base_prompt.md",
    }

    # Get profile-specific prompt file, fallback to base_prompt.md
    prompt_file = profile_prompts.get(profile, "base_prompt.md")
    prompt = _load_prompt_file(prompt_file)

    # If profile-specific file doesn't exist, fallback to base
    if not prompt and profile != "general":
        prompt = _load_prompt_file("base_prompt.md")

    return prompt


def get_expression_prompt() -> str:
    """Load expression/keyword instruction prompt"""
    return _load_prompt_file("expression_prompt.md")

