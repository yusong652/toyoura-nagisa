"""
Conversation service module.

This module provides the ChatOrchestrator service for managing
conversation turns with recursive tool calling logic.

Modular components:
- StreamingProcessor: Handles LLM streaming response processing
- ToolExecutor: Handles tool classification, execution, and cascade blocking
- ConfirmationStrategy: Handles user confirmation for tool execution
"""
from backend.application.services.conversation.models import (
    ConversationResult,
    StreamingState
)
from backend.application.services.conversation.chat_orchestrator import ChatOrchestrator
from backend.application.services.conversation.streaming_processor import StreamingProcessor
from backend.application.services.conversation.tool_executor import ToolExecutor
from backend.application.services.conversation.confirmation import (
    ConfirmationStrategy,
    ConfirmationInfo
)

__all__ = [
    "ChatOrchestrator",
    "ConversationResult",
    "StreamingState",
    "StreamingProcessor",
    "ToolExecutor",
    "ConfirmationStrategy",
    "ConfirmationInfo",
]
