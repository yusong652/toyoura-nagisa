"""
Message Service - Business logic for message management.

This service handles message-related operations within chat sessions,
focusing on CRUD operations and message history management.
"""
from typing import Dict, Any, Optional
from backend.infrastructure.storage.session_manager import (
    get_all_sessions,
    delete_message as delete_message_from_storage
)


class MessageService:
    """
    Service layer for message management operations.
    
    Provides high-level operations for managing individual messages
    within chat sessions.
    """
    
    async def delete_message(
        self,
        session_id: str,
        message_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Delete a specific message from a chat session.
        
        This operation:
        1. Validates the session exists
        2. Deletes the message from storage
        3. Returns operation status
        
        Args:
            session_id: Session UUID containing the message
            message_id: Unique identifier of the message to delete
            
        Returns:
            Optional[Dict[str, Any]]: Deletion result or None if not found:
                - session_id: str - Session containing the message
                - message_id: str - ID of deleted message
                - success: bool - Always True if successful
                - message: str - User-friendly status message
        """
        # Validate session exists
        sessions = get_all_sessions()
        session = next((s for s in sessions if s['id'] == session_id), None)
        
        if not session:
            return None
        
        # Delete the message
        success = delete_message_from_storage(session_id, message_id)
        
        if not success:
            return None
        
        return {
            "session_id": session_id,
            "message_id": message_id,
            "success": True,
            "message": "Message successfully deleted"
        }