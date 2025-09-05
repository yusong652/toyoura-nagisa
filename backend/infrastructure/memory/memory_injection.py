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
        
        # Use config values
        self.max_injection_time_ms = self.config.memory_search_timeout_ms
        self.max_context_tokens = self.config.max_memories_to_inject * 200  # Estimate tokens per memory
        self.enable_injection = self.config.enabled
    
    async def save_conversation_turn(
        self,
        user_message: BaseMessage,
        assistant_message: BaseMessage,
        user_id: Optional[str] = None
    ) -> None:
        """
        Save a conversation turn to memory with support for multimodal content.
        All memories are saved at user level and searchable across all sessions.
        
        Args:
            user_message: User's BaseMessage object
            assistant_message: Assistant's BaseMessage object
            user_id: User ID (uses config default if None)
        """
        # Use config defaults
        user_id = user_id or self.config.mem0_user_id
        
        # Check if saving is enabled
        if not self.config.should_save_memory():
            return
        
        # Extract text from standard BaseMessage objects
        from backend.domain.models.message_factory import extract_text_from_message
        user_text = extract_text_from_message(user_message)
        assistant_text = extract_text_from_message(assistant_message)
        
        # Create conversation content for memory
        conversation_content = f"""User: {user_text}
Assistant: {assistant_text[:500]}"""
        
        try:
            # Add conversation memory (detailed output handled by Mem0 manager)
            # All memories are saved at user level and searchable across all sessions
            await self.memory_manager.add_memory(
                content=conversation_content,
                user_id=user_id
            )
        except Exception as e:
            logger.error(f"Failed to save conversation to memory: {e}")
            raise


