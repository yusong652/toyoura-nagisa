"""
Chat and streaming message schemas.

This module defines WebSocket messages for chat interactions, real-time
streaming, and message creation in the aiNagisa conversation system.
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
        agent_profile: Agent profile to use (general, coding, lifestyle, pfc, disabled)
        enable_memory: Whether to use long-term memory for this message
        tts_enabled: Whether to enable text-to-speech for the response
        files: Attached files (images, documents, etc.)
    """
    type: MessageType = MessageType.CHAT_MESSAGE
    message: str
    context: Optional[Dict[str, Any]] = None
    stream_response: bool = True
    agent_profile: str = "general"
    enable_memory: bool = True
    tts_enabled: bool = False
    files: List[Dict[str, Any]] = []


class ChatStreamChunk(BaseWebSocketMessage):
    """
    Chat stream chunk message schema.

    Sent by backend during streaming response generation. Contains individual
    chunks of the AI response as they are generated.

    Attributes:
        content: Text content of this chunk
        chunk_type: Type of chunk (text, tool_call, status, etc.)
        is_final: Whether this is the last chunk in the stream
    """
    type: MessageType = MessageType.CHAT_STREAM_CHUNK
    content: str
    chunk_type: str = "text"  # text, tool_call, status, etc.
    is_final: bool = False


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


class StreamingChunkMessage(BaseWebSocketMessage):
    """
    Streaming chunk message for real-time thinking/text display (legacy).

    Provides real-time streaming of LLM response chunks including thinking
    content, text generation, and function calls. Enables progressive display
    of AI reasoning and response generation.

    Note: This is the legacy individual chunk format. Consider using
    StreamingUpdateMessage for new implementations as it provides
    accumulated content blocks.

    Attributes:
        chunk_type: Type of content ("thinking", "text", "function_call")
        content: The actual text content of this chunk
        metadata: Additional context (e.g., has_signature, args for function calls)
    """
    type: MessageType = MessageType.STREAMING_CHUNK
    chunk_type: str  # "thinking" | "text" | "function_call"
    content: str
    metadata: Dict[str, Any] = {}


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

    Example:
        {
            "type": "STREAMING_UPDATE",
            "message_id": "msg-123",
            "session_id": "session-456",
            "content": [
                {"type": "thinking", "thinking": "Current complete thinking content..."},
                {"type": "text", "text": "Current complete text content..."}
            ],
            "streaming": true
        }
    """
    type: MessageType = MessageType.STREAMING_UPDATE
    content: List[Dict[str, Any]]  # ContentBlock array: [{"type": "thinking", "thinking": "..."}, ...]
    streaming: bool = True
