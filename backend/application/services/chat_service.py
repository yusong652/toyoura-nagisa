"""
Chat Service - Business logic for chat stream operations.

This service handles chat streaming operations including message processing,
conversation history management, and response generation.
"""
from typing import List, Any
from fastapi import Request
from backend.infrastructure.storage.session_manager import load_all_message_history
from backend.domain.models.message_factory import message_factory
from backend.shared.utils.helpers import parse_message_data, process_user_message, MessageParseResult


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
        process_user_message(result, history_msgs)


    async def process_user_message(self, request_data: dict) -> dict:
        """
        Unified user message processing with pending rejection handling.

        Combines message parsing, pending rejection state checking, and message saving
        into a single operation, providing a clean interface for message handlers.

        Args:
            request_data: Dictionary containing WebSocket message data with structure:
                - message: str - The chat message content
                - session_id: str - Session identifier
                - agent_profile: str - Agent profile type
                - enable_memory: bool - Memory injection setting
                - tts_enabled: bool - TTS processing setting
                - files: List - Attached files (if any)

        Returns:
            dict: Complete message processing result with structure:
                - session_id: str - Session identifier
                - agent_profile: str - Agent profile type
                - message_id: str - Message unique identifier
                - enable_memory: bool - Memory injection setting
                - was_rejection_feedback: bool - Whether message was processed as rejection feedback

        Note:
            This method encapsulates the complete user message processing pipeline,
            including pending rejection feedback handling for elegant user interaction.
        """
        # 1. Parse request data using unified parsing logic
        try:
            parsed_data = parse_message_data(request_data)

        except Exception as e:
            raise ValueError(f"WebSocket message parsing failed: {str(e)}")

        # 2. Check for pending rejection state and handle feedback
        session_id = parsed_data['session_id']
        was_rejection_feedback = await self._check_and_process_pending_rejection(session_id, parsed_data)

        # 3. Save user message to session (only if not rejection feedback)
        if not was_rejection_feedback:
            self.save_user_message_to_session(parsed_data)

        return {
            'session_id': session_id,
            'agent_profile': parsed_data['agent_profile'],
            'message_id': parsed_data.get('id'),
            'enable_memory': parsed_data['enable_memory'],
            'was_rejection_feedback': was_rejection_feedback
        }

    async def _check_and_process_pending_rejection(self, session_id: str, result: MessageParseResult) -> bool:
        """
        Check for pending rejection state and process user feedback if needed.

        Args:
            session_id: Session identifier
            result: Parsed message result containing user feedback

        Returns:
            bool: True if message was processed as rejection feedback, False otherwise
        """
        try:
            # Get LLM client and context manager for this session
            from backend.shared.utils.app_context import get_llm_client
            llm_client = get_llm_client()
            context_manager = llm_client.get_context_manager(session_id)

            if context_manager and context_manager.has_pending_rejection():
                # Extract user feedback message
                user_feedback = result.get('message', '')

                # Resolve the pending rejection with user feedback
                context_manager.resolve_pending_rejection(user_feedback)

                return True

        except Exception as e:
            print(f"[ChatService] Error checking pending rejection: {e}")

        return False