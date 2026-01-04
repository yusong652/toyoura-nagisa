"""Utility for dynamically creating Literal type for skill names.

Provides type construction helpers for the trigger_skill tool.
"""

import logging
from typing import Literal

from backend.infrastructure.skills import get_skills_loader

logger = logging.getLogger(__name__)


def get_skill_literal_type():
    """
    Create a Literal type containing all available skill names.

    Returns:
        Literal type with skill names, or str as fallback if no skills
    """
    try:
        loader = get_skills_loader()
        names = loader.list_skills()
        if names:
            return Literal[tuple(names)]  # type: ignore
        return str
    except Exception as e:
        logger.warning(f"Failed to load skills for type construction: {e}")
        return str


def get_skill_description() -> str:
    """
    Generate skill parameter description with examples.

    Returns:
        Description string with available skill examples
    """
    try:
        loader = get_skills_loader()
        names = loader.list_skills()
        if names:
            examples = ", ".join(f'"{s}"' for s in names[:3])
            return f'The skill name. E.g., {examples}'
        return "The skill name"
    except Exception:
        return "The skill name"
