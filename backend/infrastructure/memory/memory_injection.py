"""
Memory injection middleware for automatic context enhancement.

This module provides the middleware layer that automatically injects
relevant memories into LLM conversations without explicit tool calls.
"""

import logging
from typing import Optional
from backend.domain.models.messages import BaseMessage
from backend.infrastructure.memory.mem0_manager import Mem0MemoryManager
from backend.config.memory import MemoryConfig

logger = logging.getLogger(__name__)


class MemoryInjectionMiddleware:
    """
    Middleware for automatic memory injection into LLM context.
    
    This class handles the automatic retrieval and formatting of memories
    to be injected as context before LLM processing.
    """
    
    def __init__(
        self,
        memory_manager: Optional[Mem0MemoryManager] = None,
        config: Optional[MemoryConfig] = None
    ):
        """
        Initialize memory injection middleware.
        
        Args:
            memory_manager: Memory manager instance (creates new if None)
            config: Memory configuration (creates default if None)
        """
        self.config = config or MemoryConfig()
        self.memory_manager = memory_manager or Mem0MemoryManager()
    
    async def save_conversation_turn(
        self,
        user_message: BaseMessage,
        assistant_message: BaseMessage
    ) -> None:
        """
        Save a conversation turn to memory with support for multimodal content.
        All memories are saved at user level and searchable across all sessions.

        Args:
            user_message: User's BaseMessage object
            assistant_message: Assistant's BaseMessage object
        """
        # Use config default for user_id
        user_id = self.config.mem0_user_id
        
        # Check if saving is enabled
        if not self.config.should_save_memory():
            return
        
        # Extract text from standard BaseMessage objects
        from backend.domain.models.message_factory import extract_text_from_message
        user_text = extract_text_from_message(user_message)
        assistant_text = extract_text_from_message(assistant_message)
        
        # Create conversation messages in Mem0 format (limit to one turn for testing)
        messages = [
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": assistant_text[:500]}
        ]
        
        try:
            # Add conversation memory (detailed output handled by Mem0 manager)
            # All memories are saved at user level and searchable across all sessions
            await self.memory_manager.add_memory(
                messages=messages,
                user_id=user_id
            )
        except Exception as e:
            logger.error(f"Failed to save conversation to memory: {e}")
            raise


