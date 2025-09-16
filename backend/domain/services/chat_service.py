"""
Chat Service - Business logic for chat stream operations.

This service handles chat streaming operations including message processing,
conversation history management, and response generation.
"""
from typing import AsyncGenerator, List, Any, Dict, Optional
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
    
    def parse_request_data(self, data: Dict[str, Any]) -> MessageParseResult:
        """
        Parse and validate chat request data.

        Extracts and validates message data from incoming chat requests,
        ensuring proper format and session identification.

        Args:
            data: Raw request data dictionary containing:
                - message content and metadata
                - session_id for conversation context
                - agent_profile for tool selection

        Returns:
            MessageParseResult: Unified message parsing result with structure:
                - content: Optional[List[Dict[str, Any]]] - Message content items or None if invalid
                - timestamp: Optional[int] - Message timestamp
                - id: Optional[str] - Message unique identifier
                - session_id: str - Session UUID for conversation context (required)
                - agent_profile: str - Agent profile for tool selection ("general", "coding", "lifestyle", etc.)

        Example:
            result = chat_service.parse_request_data(request_json)
            if not result['content']:
                return error_response
        """
        return parse_message_data(data)
    
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
    
    async def create_streaming_response(
        self,
        session_id: str,
        agent_profile: str = "general",
        enable_memory: bool = True,
        user_message_id: Optional[str] = None
    ) -> StreamingResponse:
        """
        Create streaming response for chat conversation.
        
        Generates a streaming HTTP response that provides real-time
        LLM-generated content with optional TTS audio synthesis.
        
        Args:
            session_id: Session UUID for conversation context
            agent_profile: Agent profile for tool selection ("general", "coding", "lifestyle", etc.)
            enable_memory: Whether to enable memory injection (controlled by frontend toggle)
            user_message_id: Optional user message ID for status tracking
                
        Returns:
            StreamingResponse: FastAPI streaming response with:
                - media_type: "text/event-stream" for SSE protocol
                - content: AsyncGenerator yielding chat stream events
                - headers: Proper SSE headers for client consumption
        
        Example:
            response = await chat_service.create_streaming_response(
                session_id, agent_profile="general", enable_memory=True
            )
            return response
        
        Note:
            Uses the existing generate_chat_stream function for actual
            stream generation, maintaining compatibility with current
            streaming infrastructure.
        """
        return StreamingResponse(
            generate_chat_stream(
                session_id,
                enable_memory=enable_memory,
                agent_profile=agent_profile,
                user_message_id=user_message_id
            ),
            media_type="text/event-stream"
        )