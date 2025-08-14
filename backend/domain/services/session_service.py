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
    load_history
)
from backend.domain.models.message_factory import message_factory
from backend.config import get_llm_settings


class SessionService:
    """
    Service layer for session management operations.
    
    This class provides high-level business operations for managing
    chat sessions, abstracting away infrastructure details.
    """
    
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
        
        return {
            "session": session,
            "history": [
                msg.model_dump() | {"role": msg.role} 
                for msg in history_msgs
            ],
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
        if llm_client and hasattr(llm_client, '_clear_session_tool_cache'):
            await llm_client._clear_session_tool_cache(session_id)
            print(f"[DEBUG] Cleared tool cache for session: {session_id}")
        
        # Load session history
        history = load_all_message_history(session_id)
        history_msgs = [
            message_factory(msg) if isinstance(msg, dict) else msg 
            for msg in history
        ]
        
        # Get recent messages for context
        recent_messages_length = get_llm_settings().recent_messages_length
        recent_messages = (
            history_msgs[-recent_messages_length:] 
            if len(history_msgs) > recent_messages_length 
            else history_msgs
        )
        
        return {
            "session_id": session_id,
            "success": True,
            "message_count": len(history_msgs),
            "recent_messages": [
                msg.model_dump() | {"role": msg.role} 
                for msg in recent_messages
            ]
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
        if llm_client and hasattr(llm_client, '_clear_session_tool_cache'):
            await llm_client._clear_session_tool_cache(session_id)
            print(f"[DEBUG] Cleared tool cache for deleted session: {session_id}")
        
        # TODO: Delete related memories from vector database
        # This will be implemented when memory service is refactored
        
        return {
            "session_id": session_id,
            "success": True,
            "message": f"Session '{session.get('name', session_id)}' successfully deleted"
        }