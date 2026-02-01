"""
OAuth Type Definitions

Common types used across OAuth providers.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time


class OAuthProvider(str, Enum):
    """Supported OAuth providers."""
    GOOGLE = "google"


@dataclass
class OAuthCredentials:
    """
    OAuth credentials for a provider account.

    Attributes:
        access_token: Current access token for API calls
        refresh_token: Token used to obtain new access tokens
        expires_at: Unix timestamp when access_token expires
        email: User's email address (if available)
        project_id: Provider-specific project identifier (e.g., Google Cloud project)
        created_at: Unix timestamp when credentials were first obtained
        updated_at: Unix timestamp of last credential update
    """
    access_token: str
    refresh_token: str
    expires_at: int
    email: Optional[str] = None
    project_id: Optional[str] = None
    created_at: int = field(default_factory=lambda: int(time.time()))
    updated_at: int = field(default_factory=lambda: int(time.time()))

    def is_expired(self, buffer_seconds: int = 300) -> bool:
        """
        Check if access token is expired or will expire soon.

        Args:
            buffer_seconds: Consider expired if within this many seconds of expiry.
                           Default 5 minutes (300 seconds).

        Returns:
            True if token is expired or will expire within buffer_seconds.
        """
        return int(time.time()) >= (self.expires_at - buffer_seconds)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "email": self.email,
            "project_id": self.project_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OAuthCredentials":
        """Create from dictionary."""
        return cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=data["expires_at"],
            email=data.get("email"),
            project_id=data.get("project_id"),
            created_at=data.get("created_at", int(time.time())),
            updated_at=data.get("updated_at", int(time.time())),
        )


@dataclass
class OAuthAccountInfo:
    """
    Summary information about an OAuth account.

    Used for listing accounts without exposing full credentials.
    """
    account_id: str
    provider: OAuthProvider
    email: Optional[str] = None
    is_default: bool = False
    connected_at: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "account_id": self.account_id,
            "provider": self.provider.value,
            "email": self.email,
            "is_default": self.is_default,
            "connected_at": self.connected_at,
        }
