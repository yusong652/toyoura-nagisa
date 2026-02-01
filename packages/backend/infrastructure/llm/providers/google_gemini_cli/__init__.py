"""
Google Gemini CLI provider implementation.

Uses Code Assist (cloudcode-pa) endpoints with OAuth tokens.
"""

from .client import GoogleGeminiCliClient

__all__ = ["GoogleGeminiCliClient"]
