"""
Gemini Antigravity tool manager.

Inherits from GoogleToolManager — same SDK conversion pipeline
(Schema.from_json_schema) with all workarounds (schema normalization,
description restoration after anyOf→nullable conversion).
"""

from __future__ import annotations

from backend.infrastructure.llm.providers.google.tool_manager import GoogleToolManager


class GeminiAntigravityToolManager(GoogleToolManager):
    """Tool manager for Gemini Antigravity — delegates to GoogleToolManager."""

    pass
