"""
Tool Confirmation Module.

Provides confirmation strategy for different tool types.
"""
from backend.application.services.conversation.confirmation.strategy import (
    ConfirmationStrategy,
    ConfirmationInfo
)

__all__ = ['ConfirmationStrategy', 'ConfirmationInfo']
