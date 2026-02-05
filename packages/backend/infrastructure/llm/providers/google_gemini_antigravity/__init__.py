"""
Google Gemini Antigravity provider implementation.

Uses Code Assist endpoints with fallback (daily -> autopush -> prod).
"""

from .base import BaseAntigravityClient
from .claude import GoogleClaudeAntigravityClient
from .gemini import GoogleGeminiAntigravityClient

__all__ = [
    "BaseAntigravityClient",
    "GoogleGeminiAntigravityClient",
    "GoogleClaudeAntigravityClient",
]
