"""
Chat Service - Business logic for chat stream operations.

This service handles chat streaming operations including message processing,
conversation history management, and response generation.
"""
from typing import List, Any
from fastapi import Request
from backend.infrastructure.storage.session_manager import load_all_message_history
from backend.domain.models.message_factory import message_factory
from backend.shared.utils.helpers import parse_message_data, MessageParseResult


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

        Delegates to MessageService for consistent message handling across the application.

        Args:
            result: Unified MessageParseResult with complete message data including session_id

        Raises:
            ValueError: If message content is None or empty

        Note:
            This function provides a convenient wrapper around MessageService.save_user_message
            for use with parsed WebSocket data.
        """
        # Validate content
        if not result['content']:
            raise ValueError("Invalid message content")

        # Delegate to MessageService for consistent message handling
        from backend.application.services.message_service import MessageService
        MessageService.save_user_message(
            content=result['content'],
            session_id=result['session_id'],
            timestamp=result.get('timestamp'),
            message_id=result.get('id')
        )


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
                - message_id: str - Message unique identifier

        Note:
            This method processes all user messages uniformly.
            User rejection feedback is handled as a normal user message in the new architecture.
        """
        # 1. Parse request data using unified parsing logic
        try:
            parsed_data = parse_message_data(request_data)

        except Exception as e:
            raise ValueError(f"WebSocket message parsing failed: {str(e)}")

        # 2. Extract session ID
        session_id = parsed_data['session_id']
        if not session_id:
            raise ValueError("Session ID is required in the message data")

        # 3. Extract file mentions from frontend or fallback to backend parsing
        # Priority: Use frontend-provided mentioned_files if available (supports spaces, unicode, etc.)
        # Fallback: Parse from message text using regex (legacy support, limited to ASCII)
        mentioned_files = parsed_data.get('mentioned_files', [])

        if not mentioned_files:
            # Fallback: Backend regex parsing (limited support for special characters)
            message_text = parsed_data.get('message', '')
            if message_text:
                mentioned_files = self._extract_file_mentions(message_text)

        if mentioned_files:
            parsed_data['mentioned_files'] = mentioned_files
            print(f"[DEBUG] Processing {len(mentioned_files)} file mentions: {mentioned_files}", flush=True)

        # 4. Inject system status reminders BEFORE saving to database
        # This ensures the database stores the complete message with context
        await self._inject_status_reminders(session_id, parsed_data)

        # 4. Save user message (with injected reminders) to persistent storage
        print(f"[DEBUG] Processing user message for session {session_id}", flush=True)
        self.save_user_message_to_session(parsed_data)
        print(f"[DEBUG] Saved user message {parsed_data.get('id')} to session {session_id}", flush=True)

        # 4. Force reload context manager from storage to get fresh state
        from backend.shared.utils.app_context import get_llm_client
        llm_client = get_llm_client()

        # Clear cached context manager to force reload from database
        # This ensures we always have the latest state including the newly saved message
        llm_client.clear_context_manager(session_id)

        # Get fresh context manager (will auto-load from database in __init__)
        context_manager = llm_client.get_or_create_context_manager(session_id)

        # Update configuration from parsed_data
        context_manager.agent_profile = parsed_data.get('agent_profile', 'general')
        context_manager.enable_memory = parsed_data.get('enable_memory', True)

        # Reset interrupt flag for new conversation turn via StatusMonitor
        from backend.infrastructure.monitoring import get_status_monitor
        status_monitor = get_status_monitor(session_id)
        status_monitor.reset_user_interrupted()

        return {
            'session_id': session_id,
            'message_id': parsed_data.get('id')
        }

    def _extract_file_mentions(self, text: str) -> list[str]:
        """
        Extract file paths from @ mentions in message text.

        Parses message content to find all @ file mention patterns and extracts
        the file paths. Supports paths with directories, extensions, and special characters.

        Pattern: @<filepath> where filepath contains:
        - Alphanumeric characters (a-z, A-Z, 0-9)
        - Dots (.)
        - Hyphens (-)
        - Underscores (_)
        - Forward slashes (/)

        Stops at:
        - Whitespace (space, tab, newline)
        - End of string

        Args:
            text: Message text content to parse

        Returns:
            List of unique file paths (relative to workspace)

        Examples:
            >>> _extract_file_mentions("Check @backend/app.py")
            ['backend/app.py']

            >>> _extract_file_mentions("Compare @src/a.py and @src/b.py")
            ['src/a.py', 'src/b.py']

            >>> _extract_file_mentions("Same @file.txt twice @file.txt")
            ['file.txt']
        """
        import re

        file_paths = []
        seen = set()

        # Regex to match @ followed by a file path
        # Pattern: @<path> where path contains alphanumeric, dots, slashes, dashes, underscores
        # Stops at whitespace, newline, or end of string
        pattern = r'@([a-zA-Z0-9._\-/]+)'

        for match in re.finditer(pattern, text):
            file_path = match.group(1)

            # Deduplicate
            if file_path not in seen:
                seen.add(file_path)
                file_paths.append(file_path)

        return file_paths

    async def _inject_status_reminders(self, session_id: str, parsed_data: MessageParseResult) -> None:
        """
        Inject system status reminders and file mentions into user message content.

        Delegates to ReminderInjector for unified reminder collection and injection.

        Args:
            session_id: Session ID for retrieving status monitor
            parsed_data: Parsed message data (modified in-place)
        """
        try:
            from backend.application.services.reminder import ReminderInjector

            agent_profile = parsed_data.get('agent_profile', 'general')
            mentioned_files = parsed_data.get('mentioned_files', [])
            content = parsed_data.get('content', [])

            injector = ReminderInjector(session_id, agent_profile)
            await injector.inject_to_user_message(content, mentioned_files or None)

        except Exception as e:
            # Non-critical: Log and continue without reminders
            print(f"[WARNING] Failed to inject status reminders: {e}")
            import traceback
            traceback.print_exc()

