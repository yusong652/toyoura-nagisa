"""
Google Gemini Antigravity provider implementation.

Uses Code Assist endpoints with fallback (daily -> autopush -> prod).
"""

from .client import GoogleGeminiAntigravityClient

__all__ = ["GoogleGeminiAntigravityClient"]
