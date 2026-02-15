"""
WebSocket message type enumeration.

This module defines all supported WebSocket message types for the toyoura-nagisa
real-time communication system.
"""
from enum import Enum


class MessageType(str, Enum):
    """WebSocket message type enumeration"""
    # Connection management
    HEARTBEAT = "HEARTBEAT"
    HEARTBEAT_ACK = "HEARTBEAT_ACK"
    CONNECTION_ESTABLISHED = "CONNECTION_ESTABLISHED"

    # Location services
    LOCATION_REQUEST = "LOCATION_REQUEST"
    LOCATION_RESPONSE = "LOCATION_RESPONSE"

    # Chat and streaming
    CHAT_MESSAGE = "CHAT_MESSAGE"
    CHAT_STREAM_START = "CHAT_STREAM_START"
    CHAT_STREAM_END = "CHAT_STREAM_END"
    STREAMING_UPDATE = "STREAMING_UPDATE"  # Real-time content update (accumulated complete content)

    # File operations
    FILE_UPLOAD_START = "FILE_UPLOAD_START"
    FILE_UPLOAD_CHUNK = "FILE_UPLOAD_CHUNK"
    FILE_UPLOAD_COMPLETE = "FILE_UPLOAD_COMPLETE"

    # System messages
    ERROR = "ERROR"
    STATUS_UPDATE = "STATUS_UPDATE"

    # Message management
    MESSAGE_CREATE = "MESSAGE_CREATE"


    # Session management
    TITLE_UPDATE = "TITLE_UPDATE"
    SESSION_MODE_UPDATE = "SESSION_MODE_UPDATE"
    SESSION_LLM_CONFIG_UPDATE = "SESSION_LLM_CONFIG_UPDATE"

    # Tool confirmation (bash, edit, write, etc.)
    TOOL_CONFIRMATION_REQUEST = "TOOL_CONFIRMATION_REQUEST"
    TOOL_CONFIRMATION_RESPONSE = "TOOL_CONFIRMATION_RESPONSE"

    # User interrupt control
    USER_INTERRUPT = "USER_INTERRUPT"

    # Foreground-to-background conversion (ctrl+b)
    MOVE_TO_BACKGROUND = "MOVE_TO_BACKGROUND"

    # Background process notifications
    BACKGROUND_PROCESS_STARTED = "BACKGROUND_PROCESS_STARTED"
    BACKGROUND_PROCESS_OUTPUT_UPDATE = "BACKGROUND_PROCESS_OUTPUT_UPDATE"
    BACKGROUND_PROCESS_COMPLETED = "BACKGROUND_PROCESS_COMPLETED"
    BACKGROUND_PROCESS_KILLED = "BACKGROUND_PROCESS_KILLED"

    # PFC task notifications
    PFC_TASK_UPDATE = "PFC_TASK_UPDATE"

    # User shell commands (! prefix in CLI)
    USER_SHELL_EXECUTE = "USER_SHELL_EXECUTE"
    USER_SHELL_RESULT = "USER_SHELL_RESULT"

    # User PFC console commands (> prefix in CLI)
    USER_PFC_CONSOLE_EXECUTE = "USER_PFC_CONSOLE_EXECUTE"
    USER_PFC_CONSOLE_RESULT = "USER_PFC_CONSOLE_RESULT"

    # Message queue management
    QUEUE_UPDATE = "QUEUE_UPDATE"
    MESSAGE_PROCESSING_START = "MESSAGE_PROCESSING_START"
    MESSAGE_QUEUED = "MESSAGE_QUEUED"

    # Future extensions
    VOICE_MESSAGE = "VOICE_MESSAGE"
    IMAGE_GENERATION = "IMAGE_GENERATION"
