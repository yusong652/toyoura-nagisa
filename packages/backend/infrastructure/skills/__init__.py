"""
Skills System for toyoura-nagisa.

This module provides a Skills system similar to Claude Code's skills architecture,
implementing a three-level progressive disclosure pattern:
- Level 1: Metadata (injected into system prompt via placeholder)
- Level 2: Instructions (loaded on skill trigger via trigger_skill tool)
- Level 3: Resources (loaded as needed via standard Read tool)
"""

from .loader import SkillsLoader, get_skills_loader
from .models import SkillMetadata

__all__ = ["SkillsLoader", "SkillMetadata", "get_skills_loader"]
