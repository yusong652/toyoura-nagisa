"""
Google Gemini Antigravity provider implementation.

Uses Code Assist endpoints with fallback (daily -> autopush -> prod).
"""

from .base import BaseAntigravityClient
from .claude import ClaudeAntigravityClient
from .gemini import GeminiAntigravityClient

__all__ = [
    "BaseAntigravityClient",
    "GeminiAntigravityClient",
    "ClaudeAntigravityClient",
]
