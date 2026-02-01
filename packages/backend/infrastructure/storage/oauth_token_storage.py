"""
OAuth Token Storage Manager

Manages OAuth tokens with multi-account support.
Tokens are stored in: data/oauth_tokens/<provider>/<account_id>.json

Token File Structure:
{
    "access_token": "ya29...",
    "refresh_token": "1//0g...",
    "expires_at": 1706745600,
    "email": "user@example.com",
    "project_id": "cloudcode-project-id",
    "created_at": 1706742000,
    "updated_at": 1706742000
}

Default Account:
Stored in data/oauth_tokens/<provider>/default.txt containing the account_id.
"""

import json
import os
from typing import List, Optional

from backend.infrastructure.oauth.base.types import (
    OAuthCredentials,
    OAuthProvider,
    OAuthAccountInfo,
)


# Base directory for OAuth token storage (relative to project root)
OAUTH_TOKENS_DIR = "data/oauth_tokens"


def _get_provider_dir(provider: OAuthProvider) -> str:
    """Get the directory path for a provider's tokens."""
    return os.path.join(OAUTH_TOKENS_DIR, provider.value)


def _get_token_file_path(provider: OAuthProvider, account_id: str) -> str:
    """Get the file path for a specific account's token."""
    return os.path.join(_get_provider_dir(provider), f"{account_id}.json")


def _get_default_file_path(provider: OAuthProvider) -> str:
    """Get the file path for the default account marker."""
    return os.path.join(_get_provider_dir(provider), "default.txt")


def _ensure_provider_dir(provider: OAuthProvider) -> None:
    """Ensure the provider's token directory exists."""
    provider_dir = _get_provider_dir(provider)
    os.makedirs(provider_dir, exist_ok=True)


def _list_account_ids(provider: OAuthProvider) -> List[str]:
    """List account IDs without default lookup."""
    provider_dir = _get_provider_dir(provider)
    if not os.path.exists(provider_dir):
        return []

    account_ids = []
    for filename in os.listdir(provider_dir):
        if filename.endswith(".json"):
            account_ids.append(filename[:-5])
    return account_ids


def _read_default_account(provider: OAuthProvider) -> Optional[str]:
    """Read the default account marker from disk only."""
    default_path = _get_default_file_path(provider)
    if not os.path.exists(default_path):
        return None

    try:
        with open(default_path, "r", encoding="utf-8") as f:
            account_id = f.read().strip()
            if account_id:
                token_path = _get_token_file_path(provider, account_id)
                if os.path.exists(token_path):
                    return account_id
        return None
    except Exception:
        return None


def has_accounts(provider: OAuthProvider) -> bool:
    """Check if any accounts exist for a provider."""
    return len(_list_account_ids(provider)) > 0


def _generate_account_id(email: Optional[str]) -> str:
    """
    Generate a unique account ID from email or random string.

    Args:
        email: User's email address

    Returns:
        Account ID (sanitized email or random string)
    """
    if email:
        # Sanitize email for use as filename
        sanitized = email.lower().replace("@", "_at_").replace(".", "_")
        # Remove any remaining problematic characters
        return "".join(c for c in sanitized if c.isalnum() or c == "_")

    # Fallback to timestamp-based ID
    import time

    return f"account_{int(time.time())}"


def generate_account_id(email: Optional[str]) -> str:
    """
    Public wrapper for account ID generation.

    Args:
        email: User's email address

    Returns:
        Account ID string
    """
    return _generate_account_id(email)


def save_token(
    provider: OAuthProvider,
    credentials: OAuthCredentials,
    account_id: Optional[str] = None,
) -> str:
    """
    Save OAuth token for an account.

    Args:
        provider: OAuth provider
        credentials: OAuth credentials to save
        account_id: Optional account ID (auto-generated from email if not provided)

    Returns:
        str: The account ID used for storage
    """
    _ensure_provider_dir(provider)

    if not account_id:
        account_id = _generate_account_id(credentials.email)

    token_path = _get_token_file_path(provider, account_id)

    # Update timestamp
    import time

    credentials.updated_at = int(time.time())

    try:
        with open(token_path, "w", encoding="utf-8") as f:
            json.dump(credentials.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"[INFO] Saved OAuth token for {provider.value}/{account_id}")
        return account_id
    except Exception as e:
        print(f"[ERROR] Failed to save OAuth token: {e}")
        raise


def get_token(provider: OAuthProvider, account_id: str) -> Optional[OAuthCredentials]:
    """
    Get OAuth token for a specific account.

    Args:
        provider: OAuth provider
        account_id: Account identifier

    Returns:
        OAuthCredentials if found, None otherwise
    """
    token_path = _get_token_file_path(provider, account_id)

    if not os.path.exists(token_path):
        return None

    try:
        with open(token_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return OAuthCredentials.from_dict(data)
    except Exception as e:
        print(f"[WARNING] Failed to load OAuth token for {account_id}: {e}")
        return None


def update_token(
    provider: OAuthProvider,
    account_id: str,
    credentials: OAuthCredentials,
) -> bool:
    """
    Update an existing OAuth token.

    Args:
        provider: OAuth provider
        account_id: Account identifier
        credentials: New credentials

    Returns:
        True if updated successfully
    """
    token_path = _get_token_file_path(provider, account_id)

    if not os.path.exists(token_path):
        print(f"[WARNING] Cannot update: token not found for {account_id}")
        return False

    try:
        import time

        credentials.updated_at = int(time.time())

        with open(token_path, "w", encoding="utf-8") as f:
            json.dump(credentials.to_dict(), f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to update OAuth token: {e}")
        return False


def delete_token(provider: OAuthProvider, account_id: str) -> bool:
    """
    Delete OAuth token for an account.

    Args:
        provider: OAuth provider
        account_id: Account identifier

    Returns:
        True if deleted successfully
    """
    token_path = _get_token_file_path(provider, account_id)

    if not os.path.exists(token_path):
        return True  # Already doesn't exist

    try:
        os.remove(token_path)
        print(f"[INFO] Deleted OAuth token for {provider.value}/{account_id}")

        # If this was the default account, clear default
        default_account = get_default_account(provider)
        if default_account == account_id:
            clear_default_account(provider)

        return True
    except Exception as e:
        print(f"[ERROR] Failed to delete OAuth token: {e}")
        return False


def list_accounts(provider: OAuthProvider) -> List[OAuthAccountInfo]:
    """
    List all accounts for a provider.

    Args:
        provider: OAuth provider

    Returns:
        List of account info objects
    """
    if not os.path.exists(_get_provider_dir(provider)):
        return []

    accounts = []
    default_account = _read_default_account(provider)

    try:
        for account_id in _list_account_ids(provider):
            token_path = _get_token_file_path(provider, account_id)

            try:
                with open(token_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                accounts.append(
                    OAuthAccountInfo(
                        account_id=account_id,
                        provider=provider,
                        email=data.get("email"),
                        is_default=(account_id == default_account),
                        connected_at=data.get("created_at", 0),
                    )
                )
            except Exception as e:
                print(f"[WARNING] Failed to read account {account_id}: {e}")
                continue

        return accounts
    except Exception as e:
        print(f"[ERROR] Failed to list accounts: {e}")
        return []


def get_default_account(provider: OAuthProvider) -> Optional[str]:
    """
    Get the default account ID for a provider.

    Args:
        provider: OAuth provider

    Returns:
        Account ID if default is set, None otherwise
    """
    default_account = _read_default_account(provider)
    if default_account:
        return default_account

    account_ids = _list_account_ids(provider)
    if account_ids:
        return account_ids[0]
    return None


def set_default_account(provider: OAuthProvider, account_id: str) -> bool:
    """
    Set the default account for a provider.

    Args:
        provider: OAuth provider
        account_id: Account to set as default

    Returns:
        True if set successfully
    """
    # Verify account exists
    token_path = _get_token_file_path(provider, account_id)
    if not os.path.exists(token_path):
        print(f"[ERROR] Cannot set default: account {account_id} does not exist")
        return False

    _ensure_provider_dir(provider)
    default_path = _get_default_file_path(provider)

    try:
        with open(default_path, "w", encoding="utf-8") as f:
            f.write(account_id)
        print(f"[INFO] Set default account for {provider.value}: {account_id}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to set default account: {e}")
        return False


def clear_default_account(provider: OAuthProvider) -> bool:
    """
    Clear the default account setting for a provider.

    Args:
        provider: OAuth provider

    Returns:
        True if cleared successfully
    """
    default_path = _get_default_file_path(provider)

    if not os.path.exists(default_path):
        return True

    try:
        os.remove(default_path)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to clear default account: {e}")
        return False


def get_default_token(provider: OAuthProvider) -> Optional[OAuthCredentials]:
    """
    Get the OAuth token for the default account.

    Convenience function that combines get_default_account() and get_token().

    Args:
        provider: OAuth provider

    Returns:
        OAuthCredentials if default account exists, None otherwise
    """
    default_account = get_default_account(provider)
    if not default_account:
        return None
    return get_token(provider, default_account)
