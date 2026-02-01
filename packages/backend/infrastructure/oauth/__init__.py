"""
OAuth Infrastructure Module

Provides OAuth authentication flows for various providers.
"""

from backend.infrastructure.oauth.base.types import (
    OAuthCredentials,
    OAuthProvider,
    OAuthAccountInfo,
)

__all__ = [
    "OAuthCredentials",
    "OAuthProvider",
    "OAuthAccountInfo",
]
