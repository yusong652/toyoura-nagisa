"""
Conversation service module.

Modular components used by Agent for conversation handling:
- StreamingProcessor: Handles LLM streaming response processing
- ToolExecutor: Handles tool classification, execution, and cascade blocking
- ConfirmationStrategy: Handles user confirmation for tool execution
- StreamingState: State container for streaming responses
"""
from backend.application.services.conversation.models import (
    ConversationResult,
    StreamingState
)
from backend.application.services.conversation.streaming_processor import StreamingProcessor
from backend.application.services.conversation.tool_executor import ToolExecutor
from backend.application.services.conversation.confirmation import (
    ConfirmationStrategy,
    ConfirmationInfo
)

__all__ = [
    "ConversationResult",
    "StreamingState",
    "StreamingProcessor",
    "ToolExecutor",
    "ConfirmationStrategy",
    "ConfirmationInfo",
]
