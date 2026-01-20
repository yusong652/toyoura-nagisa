"""
Session Service - Business logic for session management.

This service encapsulates all session-related business logic,
separating it from the presentation layer (API routes) and
infrastructure layer (storage, LLM clients).
"""
from typing import List, Dict, Any, Optional
from backend.infrastructure.storage.session_manager import (
    get_all_sessions,
    delete_session_data,
    load_all_message_history,
    load_history,
    create_new_history,
    load_token_usage,
    update_session_mode as update_session_mode_metadata,
    get_session_metadata,
)
from backend.domain.models.message_factory import message_factory
from backend.domain.utils import filter_message_content


class SessionService:
    """
    Service layer for session management operations.
    
    This class provides high-level business operations for managing
    chat sessions, abstracting away infrastructure details.
    """
    
    async def create_session(self, session_name: str) -> Dict[str, Any]:
        """
        Create a new chat session.
        
        This operation:
        1. Generates a new unique session ID
        2. Creates session metadata and storage structure
        3. Initializes empty chat history
        
        Args:
            session_name: Display name for the new session
            
        Returns:
            Dict[str, Any]: Creation result:
                - session_id: str - UUID of the newly created session
                - success: bool - Always True if successful
        """
        session_id = create_new_history(session_name)
        
        return {
            "session_id": session_id,
            "success": True
        }
    
    async def get_all_sessions(self) -> List[Dict[str, Any]]:
        """
        Retrieve all available chat sessions.
        
        Returns:
            List[Dict[str, Any]]: List of session metadata dictionaries:
                - id: str - Session UUID
                - name: str - Session display name
                - created_at: str - Creation timestamp
                - updated_at: str - Last update timestamp
                - message_count: int - Number of messages in session
        """
        return get_all_sessions()
    
    async def get_session_details(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive details about a specific session.
        
        Args:
            session_id: UUID of the session
            
        Returns:
            Optional[Dict[str, Any]]: Session details or None if not found:
                - session: dict - Session metadata
                - history: List[dict] - Complete message history
                - message_count: int - Total number of messages
        """
        # Validate session exists
        sessions = get_all_sessions()
        session = next((s for s in sessions if s['id'] == session_id), None)
        
        if not session:
            return None
        
        # Load complete message history
        history = load_all_message_history(session_id)
        history_msgs = [
            message_factory(msg) if isinstance(msg, dict) else msg
            for msg in history
        ]

        # Filter system tags from message content for clean display
        filtered_history = []
        for msg in history_msgs:
            msg_dict = msg.model_dump() | {"role": msg.role}  # type: ignore
            msg_dict["content"] = filter_message_content(msg_dict.get("content", ""))
            filtered_history.append(msg_dict)

        return {
            "session": session,
            "history": filtered_history,
            "message_count": len(history_msgs)
        }
    
    async def switch_session(
        self, 
        session_id: str,
        llm_client: Optional[Any] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Switch to a different chat session.
        
        This operation:
        1. Validates the target session exists
        2. Clears any cached tools for the session
        3. Loads the session's message history
        4. Returns recent messages for UI context
        
        Args:
            session_id: Target session UUID
            llm_client: Optional LLM client for cache management
            
        Returns:
            Optional[Dict[str, Any]]: Switch result or None if session not found:
                - session_id: str - Target session ID
                - success: bool - Always True if successful
                - message_count: int - Total messages in session
                - recent_messages: List[dict] - Recent message context
        """
        # Validate session exists
        sessions = get_all_sessions()
        session_exists = any(session['id'] == session_id for session in sessions)
        
        if not session_exists:
            return None
        
        # Clear tool cache if LLM client provided
        if llm_client and hasattr(llm_client, '_clear_session_context'):
            await llm_client._clear_session_context(session_id)
        
        # Load session history
        history = load_all_message_history(session_id)
        history_msgs = [
            message_factory(msg) if isinstance(msg, dict) else msg 
            for msg in history
        ]
        
        # Filter system tags from message content for clean display
        filtered_recent = []
        for msg in history_msgs:
            msg_dict = msg.model_dump() | {"role": msg.role}  # type: ignore
            msg_dict["content"] = filter_message_content(msg_dict.get("content", ""))
            filtered_recent.append(msg_dict)

        return {
            "session_id": session_id,
            "success": True,
            "message_count": len(history_msgs),
            "recent_messages": filtered_recent
        }
    
    async def delete_session(
        self,
        session_id: str,
        llm_client: Optional[Any] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Delete a chat session and all associated data.
        
        This operation:
        1. Validates the session exists
        2. Deletes session history and metadata files
        3. Clears any cached tools
        4. TODO: Remove related memories from vector database
        
        Args:
            session_id: Session UUID to delete
            llm_client: Optional LLM client for cache management
            
        Returns:
            Optional[Dict[str, Any]]: Deletion result or None if session not found:
                - session_id: str - Deleted session ID
                - success: bool - Always True if successful
                - message: str - User-friendly status message
        """
        # Validate session exists
        sessions = get_all_sessions()
        session = next((s for s in sessions if s['id'] == session_id), None)
        
        if not session:
            return None
        
        # Delete session data
        success = delete_session_data(session_id)
        
        if not success:
            raise Exception(f"Failed to delete session data for {session_id}")
        
        # Clear tool cache if LLM client provided
        if llm_client and hasattr(llm_client, '_clear_session_context'):
            await llm_client._clear_session_context(session_id)
        
        # TODO: Delete related memories from vector database
        # This will be implemented when memory service is refactored
        
        return {
            "session_id": session_id,
            "success": True,
            "message": f"Session '{session.get('name', session_id)}' successfully deleted"
        }

    async def get_token_usage(self, session_id: str) -> Optional[Dict[str, int]]:
        """
        Get token usage information for a session.

        Token usage includes:
        - prompt_tokens: Input tokens (context window usage)
        - completion_tokens: Output tokens (AI response)
        - total_tokens: Total tokens used in last turn
        - tokens_left: Remaining tokens in context window

        Args:
            session_id: Session UUID

        Returns:
            Optional[Dict[str, int]]: Token usage statistics or None if not available
        """
        return load_token_usage(session_id)

    async def update_session_mode(self, session_id: str, mode: str) -> Optional[Dict[str, Any]]:
        """
        Update session mode (plan/build).

        Args:
            session_id: Session UUID
            mode: New session mode

        Returns:
            Optional[Dict[str, Any]]: Update result or None if session not found
        """
        session_metadata = get_session_metadata(session_id)
        if not session_metadata:
            return None

        update_session_mode_metadata(session_id, mode)
        updated_metadata = get_session_metadata(session_id)

        return {
            "session_id": session_id,
            "mode": updated_metadata.get("mode", mode) if updated_metadata else mode,
            "success": True,
        }
