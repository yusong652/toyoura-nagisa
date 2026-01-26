"""
Chat Service - Business logic for chat stream operations.

This service handles chat streaming operations including message processing,
conversation history management, and response generation.
"""

from dataclasses import dataclass
from typing import Any

from backend.domain.models.message_factory import message_factory
from backend.domain.models.messages import UserMessage
from backend.infrastructure.storage.session_manager import load_all_message_history
from backend.shared.utils.helpers import MessageParseResult, parse_message_data
from fastapi import Request


@dataclass
class PreparedUserMessage:
    """
    Result of preparing a user message for Agent execution.

    Contains the UserMessage object and associated configuration,
    ready to be passed to Agent.execute().
    """

    session_id: str
    message_id: str
    instruction: UserMessage
    enable_memory: bool


def get_chat_service() -> "ChatService":
    """
    Dependency injection factory for ChatService.

    Returns:
        ChatService: Chat streaming service instance
    """
    return ChatService()


class ChatService:
    """
    Service layer for chat stream operations.

    Provides high-level operations for processing chat messages,
    managing conversation history, and generating streaming responses.
    """

    async def parse_request(self, request: Request) -> tuple[MessageParseResult, bool]:
        """
        Parse FastAPI request and extract message data with memory configuration.

        Combines JSON parsing, message data validation, and memory setting extraction
        into a single operation, using configuration defaults.

        Args:
            request: FastAPI Request object

        Returns:
            tuple[MessageParseResult, bool]: Parsed message data and enable_memory flag

        Raises:
            HTTPException: If request data is invalid or malformed
        """
        from backend.config import get_memory_config
        from fastapi import HTTPException

        try:
            data = await request.json()
            result = parse_message_data(data)

            if not result["content"]:
                raise HTTPException(status_code=400, detail="Invalid message data format")

            # Get enable_memory from request or use config default
            memory_config = get_memory_config()
            enable_memory = data.get("enable_memory", memory_config.save_conversations)

            return result, enable_memory
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(
                status_code=400,
                detail=f"Request parsing failed: {str(e)}",
            ) from e

    def load_and_prepare_history(self, session_id: str) -> list[Any]:
        """
        Load conversation history and prepare for LLM processing.

        Retrieves stored conversation history for the session and converts
        raw message data into proper message objects using the message factory.

        Args:
            session_id: Session UUID to load history for

        Returns:
            List[Any]: List of processed message objects ready for LLM:
                - Each item is a properly formatted message object
                - Historical context maintained in chronological order

        Note:
            Uses message_factory to ensure consistent message format
            across different message types (text, image, tool results).
        """
        loaded_history = load_all_message_history(session_id)
        return [message_factory(msg) if isinstance(msg, dict) else msg for msg in loaded_history]

    async def prepare_user_message(self, request_data: dict) -> PreparedUserMessage:
        """
        Prepare user message for Agent execution.

        Parses and preprocesses the user message (including file mentions and
        status reminders), returning a PreparedUserMessage ready for Agent.execute().

        NOTE: This method does NOT save the message to database. Message persistence
        is handled by Agent.execute() to maintain Agent as the first-class citizen
        responsible for the complete message lifecycle.

        Args:
            request_data: Dictionary containing WebSocket message data with structure:
                - message: str - The chat message content
                - session_id: str - Session identifier
                - enable_memory: bool - Memory injection setting
                - files: List - Attached files (if any)

        Returns:
            PreparedUserMessage containing:
                - session_id: Session identifier
                - message_id: Message unique identifier
                - instruction: UserMessage object ready for Agent
                - enable_memory: Memory persistence setting

        Raises:
            ValueError: If message data is invalid or missing required fields
        """
        # 1. Parse request data using unified parsing logic
        try:
            parsed_data = parse_message_data(request_data)
        except Exception as e:
            raise ValueError(f"WebSocket message parsing failed: {str(e)}") from e

        # 2. Extract and validate session ID
        session_id = parsed_data["session_id"]
        if not session_id:
            raise ValueError("Session ID is required in the message data")

        # 3. Inject system status reminders into content
        await self._inject_status_reminders(session_id, parsed_data)

        # 4. Reset interrupt flag for new conversation turn
        from backend.infrastructure.monitoring import get_status_monitor

        status_monitor = get_status_monitor(session_id)
        status_monitor.reset_user_interrupted()

        # 5. Build UserMessage object
        content = parsed_data.get("content", [])
        message_id = parsed_data.get("id") or ""
        timestamp = parsed_data.get("timestamp")

        # Convert timestamp to datetime if provided
        from datetime import datetime

        dt_timestamp = None
        if timestamp:
            try:
                dt_timestamp = datetime.fromtimestamp(timestamp / 1000)
            except (TypeError, ValueError):
                pass

        instruction = UserMessage(content=content, id=message_id, timestamp=dt_timestamp)

        return PreparedUserMessage(
            session_id=session_id,
            message_id=message_id,
            instruction=instruction,
            enable_memory=parsed_data.get("enable_memory", True),
        )

    async def _inject_status_reminders(self, session_id: str, parsed_data: MessageParseResult) -> None:
        """
        Inject system status reminders, memory context, and file mentions into user message content.

        Delegates to ReminderInjector for unified reminder collection and injection.

        Args:
            session_id: Session ID for retrieving status monitor
            parsed_data: Parsed message data (modified in-place)
        """
        try:
            from backend.application.reminder import ReminderInjector

            from backend.domain.models.agent_profiles import get_agent_config

            agent_profile = get_agent_config().name
            mentioned_files = parsed_data.get("mentioned_files", [])
            content = parsed_data.get("content", [])
            enable_memory = parsed_data.get("enable_memory", False)

            injector = ReminderInjector(session_id, agent_profile)
            await injector.inject_to_user_message(content, mentioned_files or None, enable_memory=enable_memory)

        except Exception as e:
            # Non-critical: Log and continue without reminders
            print(f"[WARNING] Failed to inject status reminders: {e}")
            import traceback

            traceback.print_exc()
