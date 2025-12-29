"""
Shared helper functions for message handlers.
"""


def truncate_message(message, max_length=5000):
    # type: (str, int) -> str
    """
    Truncate message if too long to prevent WebSocket/JSON size issues.

    Args:
        message: Original message string
        max_length: Maximum message length (default: 5000 characters)

    Returns:
        Truncated message with indicator if truncation occurred
    """
    if len(message) <= max_length:
        return message
    return message[:max_length] + f"\n... (truncated from {len(message)} chars)"
