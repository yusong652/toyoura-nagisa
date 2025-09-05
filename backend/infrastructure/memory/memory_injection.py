"""
Memory injection middleware for automatic context enhancement.

This module provides the middleware layer that automatically injects
relevant memories into LLM conversations without explicit tool calls.
"""

import logging
from typing import Dict, Any, Optional
from backend.domain.models.messages import BaseMessage
from datetime import datetime
from backend.infrastructure.memory.mem0_manager import Mem0MemoryManager
from backend.domain.models.memory_context import (
    MemoryContext, MemoryInjectionResult
)
from backend.config.memory import MemoryConfig
from backend.shared.utils.token_utils import estimate_tokens
from backend.shared.utils.prompt_templates import format_memory_context_prompt

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
        self.memory_manager = memory_manager or Mem0MemoryManager(config=self.config)
        
        # Use config values
        self.max_injection_time_ms = self.config.memory_search_timeout_ms
        self.max_context_tokens = self.config.max_memories_to_inject * 200  # Estimate tokens per memory
        self.enable_injection = self.config.enabled
    
    async def get_enhanced_system_prompt(
        self,
        base_system_prompt: str,
        user_message: BaseMessage,
        session_id: str,
        user_id: Optional[str] = None
    ) -> tuple[str, MemoryInjectionResult]:
        """
        Get enhanced system prompt with memory context using SessionMemoryContextManager.
        
        This is the preferred method for integrating memory into system prompts
        rather than injecting system messages into conversations.
        
        Args:
            base_system_prompt: Base system prompt
            user_message: User's message (BaseMessage object)
            session_id: Session ID
            user_id: User ID (uses config default if None)
            
        Returns:
            Tuple of (enhanced_system_prompt, injection_result)
        """
        # Use config defaults
        user_id = user_id or self.config.mem0_user_id
        
        if not self.config.should_inject_memory():
            return base_system_prompt, MemoryInjectionResult(
                success=False,
                injected_count=0,
                error="Memory injection disabled or auto-inject off"
            )
        
        try:
            # Extract text from user message
            from backend.domain.models.message_factory import extract_text_from_message
            query_text = extract_text_from_message(user_message)
            
            if not query_text:
                return base_system_prompt, MemoryInjectionResult(
                    success=False,
                    injected_count=0,
                    error="No user query found"
                )
            
            # Create memory context with config values
            memory_context = MemoryContext(
                session_id=session_id,
                query=query_text,
                top_k=self.config.max_memories_to_inject,
                exclude_recent_minutes=self.config.get_time_filter_minutes(),
                memory_types=None,
                relevance_threshold=self.config.memory_relevance_threshold
            )
            
            # Retrieve relevant memories without session filtering (cross-session memory retrieval)
            memories = await self.memory_manager.get_relevant_memories_for_context(
                query_text=query_text,
                session_id=None,  # Cross-session search - retrieve memories from all user sessions
                top_k=memory_context.top_k,
                exclude_recent_minutes=memory_context.exclude_recent_minutes,
                memory_types=memory_context.memory_types,
                user_id=user_id
            )
            
            memory_context.memories = memories
            
            # Format memories for injection
            formatted_context = memory_context.format_for_injection()
            
            if not formatted_context:
                # No relevant memories found
                return base_system_prompt, MemoryInjectionResult(
                    success=True,
                    injected_count=0,
                    formatted_context=""
                )
            
            # Compose enhanced system prompt using template
            enhanced_prompt = format_memory_context_prompt(base_system_prompt, formatted_context)
            
            context_tokens = estimate_tokens(formatted_context)
            
            return enhanced_prompt, MemoryInjectionResult(
                success=True,
                injected_count=len(memory_context.filter_by_relevance()),
                context_tokens=context_tokens,
                formatted_context=formatted_context
            )
            
        except Exception as e:
            logger.error(f"Enhanced system prompt failed: {e}")
            return base_system_prompt, MemoryInjectionResult(
                success=False,
                injected_count=0,
                error=f"Enhancement error: {str(e)}"
            )
    
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
        
        # Prepare metadata
        metadata = {
            "type": "conversation_turn",
            "timestamp": datetime.now().isoformat(),
            "role": "conversation"
        }
        
        try:
            # Add conversation memory (detailed output handled by Mem0 manager)
            # All memories are saved at user level and searchable across all sessions
            await self.memory_manager.add_memory(
                content=conversation_content,
                user_id=user_id,
                metadata=metadata
            )
        except Exception as e:
            logger.error(f"Failed to save conversation to memory: {e}")
            raise


