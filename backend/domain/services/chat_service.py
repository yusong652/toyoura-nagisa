"""
Chat Service - Business logic for chat stream operations.

This service handles chat streaming operations including message processing,
conversation history management, and response generation.
"""
from typing import AsyncGenerator, List, Any, Dict, Tuple, Optional
from fastapi.responses import StreamingResponse
from backend.infrastructure.llm import LLMClientBase
from backend.infrastructure.tts.base import BaseTTS
from backend.infrastructure.storage.session_manager import load_all_message_history
from backend.domain.models.message_factory import message_factory
from backend.shared.utils.helpers import parse_message_data, process_user_message
from backend.presentation.streaming.chat_stream import generate_chat_stream


class ChatService:
    """
    Service layer for chat stream operations.
    
    Provides high-level operations for processing chat messages,
    managing conversation history, and generating streaming responses.
    """
    
    def parse_request_data(self, data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str], str]:
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
            Tuple[Optional[Dict[str, Any]], Optional[str], str]: Parsed data, session ID and agent profile:
                - parsed_data: Dict containing validated message data or None if invalid
                - session_id: str - Session UUID for conversation context or None if missing
                - agent_profile: str - Agent profile for tool selection ("general", "coding", "lifestyle", etc.)
        
        Example:
            parsed_data, session_id, agent_profile = chat_service.parse_request_data(request_json)
            if not parsed_data:
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
        parsed_data: Dict[str, Any],
        session_id: str,
        history_msgs: List[Any]
    ) -> None:
        """
        Process and store user message in session history.
        
        Handles user message processing including validation, formatting,
        and persistence to session storage for conversation continuity.
        
        Args:
            parsed_data: Validated message data with structure:
                - content: Message text content
                - type: Message type identifier
                - metadata: Additional message context
            session_id: Session UUID for message association
            history_msgs: Current conversation history for context
            
        Note:
            Modifies session storage by adding the processed message
            to the conversation history. Uses existing helper function
            for consistent message processing.
        """
        process_user_message(parsed_data, session_id, history_msgs)
    
    async def create_streaming_response(
        self,
        session_id: str,
        llm_client: LLMClientBase,
        tts_engine: BaseTTS,
        agent_profile: str = "general",
        enable_memory: bool = True,
        additional_messages: List[Any] = None
    ) -> StreamingResponse:
        """
        Create streaming response for chat conversation.
        
        Generates a streaming HTTP response that provides real-time
        LLM-generated content with optional TTS audio synthesis.
        
        Args:
            session_id: Session UUID for conversation context
            llm_client: LLM client for text generation with structure:
                - Supports streaming text generation
                - Tool calling capabilities
                - Conversation history processing
            tts_engine: TTS engine for audio synthesis with structure:
                - Audio generation from text
                - Voice configuration support
                - Streaming audio output
            agent_profile: Agent profile for tool selection ("general", "coding", "lifestyle", etc.)
            enable_memory: Whether to enable memory injection (controlled by frontend toggle)
            additional_messages: Optional extra messages for context
                
        Returns:
            StreamingResponse: FastAPI streaming response with:
                - media_type: "text/event-stream" for SSE protocol
                - content: AsyncGenerator yielding chat stream events
                - headers: Proper SSE headers for client consumption
        
        Example:
            response = await chat_service.create_streaming_response(
                session_id, llm_client, tts_engine
            )
            return response
        
        Note:
            Uses the existing generate_chat_stream function for actual
            stream generation, maintaining compatibility with current
            streaming infrastructure.
        """
        if additional_messages is None:
            additional_messages = []
            
        return StreamingResponse(
            generate_chat_stream(
                session_id, 
                additional_messages, 
                llm_client, 
                tts_engine, 
                agent_profile=agent_profile,
                enable_memory=enable_memory
            ),
            media_type="text/event-stream"
        )