"""
Chat Service - Business logic for chat stream operations.

This service handles chat streaming operations including message processing,
conversation history management, and response generation.
"""
from typing import AsyncGenerator, List, Any, Dict, Optional
from fastapi import Request
from fastapi.responses import StreamingResponse
from backend.infrastructure.storage.session_manager import load_all_message_history
from backend.domain.models.message_factory import message_factory
from backend.shared.utils.helpers import parse_message_data, process_user_message, MessageParseResult
from backend.presentation.streaming.chat_stream import generate_chat_stream


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
        from fastapi import HTTPException
        from backend.config import get_memory_config

        try:
            data = await request.json()
            result = parse_message_data(data)

            if not result['content']:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid message data format"
                )

            # Get enable_memory from request or use config default
            memory_config = get_memory_config()
            enable_memory = data.get("enable_memory", memory_config.save_conversations)

            return result, enable_memory
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(
                status_code=400,
                detail=f"Request parsing failed: {str(e)}"
            )

    async def parse_websocket_request(self, data: dict) -> tuple[MessageParseResult, bool]:
        """
        Parse WebSocket message data and extract configuration.

        Replicates HTTP request parsing functionality for WebSocket messages,
        providing consistent message processing across both transport protocols.

        Args:
            data: Dictionary containing WebSocket message data with structure:
                - message: str - The chat message content
                - session_id: str - Session identifier
                - agent_profile: str - Agent profile type
                - type: str - Message type (usually 'text')
                - message_id: str - Message unique identifier
                - enable_memory: bool - Memory injection setting
                - tts_enabled: bool - TTS processing setting
                - files: List - Attached files (if any)

        Returns:
            tuple[MessageParseResult, bool]: Parsed message data and enable_memory flag

        Raises:
            ValueError: If message data is invalid or malformed

        Note:
            This method provides the same parsing logic as parse_request but
            operates on dictionary data instead of FastAPI Request objects.
        """
        from backend.config import get_memory_config

        try:
            result = parse_message_data(data)

            if not result['content']:
                raise ValueError("Invalid message data format")

            # Get enable_memory from data or use config default
            memory_config = get_memory_config()
            enable_memory = data.get("enable_memory", memory_config.save_conversations)

            return result, enable_memory

        except Exception as e:
            raise ValueError(f"WebSocket request parsing failed: {str(e)}")

    def load_and_prepare_history(self, session_id: str) -> List[Any]:
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
        return [
            message_factory(msg) if isinstance(msg, dict) else msg 
            for msg in loaded_history
        ]
    
    def process_user_message_for_session(
        self,
        result: MessageParseResult,
        history_msgs: List[Any]
    ) -> None:
        """
        Process and store user message in session history.

        Handles user message processing including validation, formatting,
        and persistence to session storage for conversation continuity.

        Args:
            result: Unified MessageParseResult with structure:
                - content: Optional[List[Dict[str, Any]]] - Message content items
                - timestamp: Optional[int] - Message timestamp
                - id: Optional[str] - Message unique identifier
                - session_id: str - Session UUID for message association
                - agent_profile: str - Agent profile type
            history_msgs: Current conversation history for context

        Note:
            Modifies session storage by adding the processed message
            to the conversation history. Uses existing helper function
            for consistent message processing.
        """
        process_user_message(result, history_msgs)

    def save_user_message_to_session(self, result: MessageParseResult) -> None:
        """
        Save user message to session history.

        Combines history loading and user message processing into a single operation,
        eliminating the need for API layer to handle these separately.

        Args:
            result: Unified MessageParseResult with complete message data including session_id

        Note:
            This function encapsulates the common pattern of loading history
            and saving user messages, simplifying API layer code.
        """
        # Load current history
        history_msgs = self.load_and_prepare_history(result['session_id'])

        # Process and save user message
        self.process_user_message_for_session(result, history_msgs)

    async def create_streaming_response(
        self,
        result: MessageParseResult,
        enable_memory: bool = True
    ) -> StreamingResponse:
        """
        Create streaming response for chat conversation.

        Generates a streaming HTTP response that provides real-time
        LLM-generated content with optional memory injection.

        Args:
            result: MessageParseResult containing all message data including:
                - session_id: Session UUID for conversation context
                - agent_profile: Agent profile for tool selection
                - id: User message ID for status tracking
            enable_memory: Whether to enable memory injection

        Returns:
            StreamingResponse: FastAPI streaming response with:
                - media_type: "text/event-stream" for SSE protocol
                - content: AsyncGenerator yielding chat stream events
                - headers: Proper SSE headers for client consumption

        Example:
            response = await chat_service.create_streaming_response(
                result, enable_memory=True
            )
            return response

        Note:
            Uses the existing generate_chat_stream function for actual
            stream generation, eliminating parameter redundancy.
        """
        return StreamingResponse(
            generate_chat_stream(
                result['session_id'],
                enable_memory=enable_memory,
                agent_profile=result['agent_profile'],
                user_message_id=result.get('id')
            ),
            media_type="text/event-stream"
        )