"""User utility functions for MCP tools.

This module provides common user-related utility functions that can be shared
across different MCP tools, such as getting user email configuration.
"""

import os
from typing import Optional

__all__ = ["get_user_email"]


def get_user_email() -> str:
    """Get the default user email address from environment variable.
    
    Returns:
        str: User email address for Google services (Gmail, Calendar, etc.)
        
    Raises:
        ValueError: If USER_GMAIL_ADDRESS environment variable is not set
        
    Example:
        >>> email = get_user_email()
        >>> print(f"User email: {email}")
    """
    user_email = os.getenv("USER_GMAIL_ADDRESS")
    if not user_email:
        raise ValueError("USER_GMAIL_ADDRESS environment variable not set")
    return user_email


def validate_user_email(email: Optional[str] = None) -> bool:
    """Validate user email configuration.
    
    Args:
        email: Optional email to validate. If None, uses get_user_email()
        
    Returns:
        bool: True if email is valid and configured, False otherwise
    """
    try:
        if email is None:
            email = get_user_email()
        return bool(email and "@" in email and "." in email.split("@")[1])
    except (ValueError, IndexError):
        return False