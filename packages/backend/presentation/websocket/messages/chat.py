"""
Chat and streaming message schemas.

This module defines WebSocket messages for chat interactions, real-time
streaming, and message creation in the toyoura-nagisa conversation system.
"""
from typing import Optional, Dict, Any, List
from backend.presentation.websocket.messages.base import BaseWebSocketMessage
from backend.presentation.websocket.messages.types import MessageType


class ChatMessageRequest(BaseWebSocketMessage):
    """
    Chat message request schema.

    Sent by frontend when user submits a chat message. Contains the user's
    message text along with configuration for response generation.

    Attributes:
        message: User's input text
        context: Additional context for message processing
        stream_response: Whether to stream the response in real-time
        agent_profile: Agent profile to use (pfc_expert, disabled)
        enable_memory: Whether to use long-term memory for this message
        files: Attached files (images, documents, etc.)
        mentioned_files: File paths mentioned via @ syntax (for content injection)
    """
    type: MessageType = MessageType.CHAT_MESSAGE
    message: str
    context: Optional[Dict[str, Any]] = None
    stream_response: bool = True
    agent_profile: str = "pfc_expert"
    enable_memory: bool = True
    files: List[Dict[str, Any]] = []
    mentioned_files: List[str] = []


class MessageCreateMessage(BaseWebSocketMessage):
    """
    Message creation message schema for dynamic bot message creation.

    Sent by backend to instruct frontend to create a new message container
    in the chat UI before streaming content begins.

    Attributes:
        role: Message role ("user", "assistant", "system")
        initial_text: Optional initial text to display
        streaming: Whether message will receive streaming updates
    """
    type: MessageType = MessageType.MESSAGE_CREATE
    role: str = "assistant"  # "user" | "assistant" | "system"
    initial_text: Optional[str] = None
    streaming: bool = True


class StreamingUpdateMessage(BaseWebSocketMessage):
    """
    Streaming update message for real-time content display with accumulated content.

    Sends complete accumulated content blocks instead of individual chunks,
    making frontend logic simpler and consistent with session refresh data structure.
    Frontend receives complete thinking/text content and simply replaces message content.

    This approach ensures data structure consistency between:
    - Real-time streaming (accumulated content blocks)
    - Stored messages (content[] array format)
    - Session refresh (loads content[] from database)

    Attributes:
        content: Complete content blocks array [{"type": "thinking", "thinking": "..."}, ...]
        streaming: Whether message is still streaming (true) or complete (false)
        usage: Optional token usage statistics from LLM API response
            - prompt_tokens: Input tokens (context window usage)
            - completion_tokens: Output tokens (AI response)
            - total_tokens: Total tokens used
            - tokens_left: Remaining tokens in context window (calculated)

    Example:
        {
            "type": "STREAMING_UPDATE",
            "message_id": "msg-123",
            "session_id": "session-456",
            "content": [
                {"type": "thinking", "thinking": "Current complete thinking content..."},
                {"type": "text", "text": "Current complete text content..."}
            ],
            "streaming": true,
            "usage": {
                "prompt_tokens": 15420,
                "completion_tokens": 850,
                "total_tokens": 16270,
                "tokens_left": 112580
            }
        }
    """
    type: MessageType = MessageType.STREAMING_UPDATE
    content: List[Dict[str, Any]]  # ContentBlock array: [{"type": "thinking", "thinking": "..."}, ...]
    streaming: bool = True
    interrupted: bool = False  # True if streaming was interrupted by user
    usage: Optional[Dict[str, int]] = None  # Token usage: {prompt_tokens, completion_tokens, total_tokens, tokens_left}
