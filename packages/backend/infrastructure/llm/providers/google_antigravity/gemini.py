"""
Gemini Antigravity client.
"""

from __future__ import annotations

from .base import BaseAntigravityClient
from .gemini_tool_manager import GeminiAntigravityToolManager


class GeminiAntigravityClient(BaseAntigravityClient):
    """Gemini Antigravity OAuth client using Code Assist endpoints."""

    def __init__(self, *args: object, **kwargs: object):
        super().__init__(*args, **kwargs)
        self.tool_manager = GeminiAntigravityToolManager()
