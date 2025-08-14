"""
Memory injection middleware for automatic context enhancement.

This module provides the middleware layer that automatically injects
relevant memories into LLM conversations without explicit tool calls.
"""

import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from backend.infrastructure.memory.mem0_manager import Mem0MemoryManager
from backend.domain.models.memory_context import (
    MemoryContext, MemoryInjectionResult
)
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
        self.memory_manager = memory_manager or Mem0MemoryManager(config=self.config)
        
        # Use config values
        self.max_injection_time_ms = self.config.memory_search_timeout_ms
        self.max_context_tokens = self.config.max_memories_to_inject * 200  # Estimate tokens per memory
        self.enable_injection = self.config.enabled
    
    
    async def get_enhanced_system_prompt(
        self,
        base_system_prompt: str,
        user_query: str,
        session_id: str,
        user_id: str = "default"
    ) -> tuple[str, MemoryInjectionResult]:
        """
        Get enhanced system prompt with memory context using SessionMemoryContextManager.
        
        This is the preferred method for integrating memory into system prompts
        rather than injecting system messages into conversations.
        
        Args:
            base_system_prompt: Base system prompt
            user_query: User's query text
            session_id: Session ID
            user_id: User ID
            
        Returns:
            Tuple of (enhanced_system_prompt, injection_result)
        """
        start_time = time.time()
        
        if not self.config.should_inject_memory():
            return base_system_prompt, MemoryInjectionResult(
                success=False,
                injected_count=0,
                injection_time_ms=0,
                error="Memory injection disabled or auto-inject off"
            )
        
        try:
            # Extract query from user query text
            query_extraction_start = time.time()
            query_text = user_query
            query_extraction_time_ms = (time.time() - query_extraction_start) * 1000
            
            if not query_text:
                return base_system_prompt, MemoryInjectionResult(
                    success=False,
                    injected_count=0,
                    injection_time_ms=query_extraction_time_ms,
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
            
            # Retrieve relevant memories without session filtering
            memory_retrieval_start = time.time()
            memories = await self.memory_manager.get_relevant_memories_for_context(
                query_text=query_text,
                session_id=None,  # Don't filter by session - search all user memories
                top_k=memory_context.top_k,
                exclude_recent_minutes=memory_context.exclude_recent_minutes,
                memory_types=memory_context.memory_types,
                user_id=user_id
            )
            
            memory_retrieval_time_ms = (time.time() - memory_retrieval_start) * 1000
            if self.config.debug_mode:
                logger.info(f"[Memory Timing] Memory retrieval: {memory_retrieval_time_ms:.2f}ms, Found {len(memories)} memories")
            
            memory_context.memories = memories
            
            # Format memories for injection
            formatted_context = memory_context.format_for_injection()
            
            if not formatted_context:
                # No relevant memories found
                elapsed_ms = (time.time() - start_time) * 1000
                return base_system_prompt, MemoryInjectionResult(
                    success=True,
                    injected_count=0,
                    injection_time_ms=elapsed_ms,
                    formatted_context=""
                )
            
            # Compose enhanced system prompt
            enhanced_prompt = self._compose_enhanced_system_prompt(base_system_prompt, formatted_context)
            
            elapsed_ms = (time.time() - start_time) * 1000
            context_tokens = self._estimate_tokens(formatted_context)
            
            return enhanced_prompt, MemoryInjectionResult(
                success=True,
                injected_count=len(memory_context.filter_by_relevance()),
                injection_time_ms=elapsed_ms,
                context_tokens=context_tokens,
                formatted_context=formatted_context
            )
            
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"Enhanced system prompt failed: {e}")
            return base_system_prompt, MemoryInjectionResult(
                success=False,
                injected_count=0,
                injection_time_ms=elapsed_ms,
                error=f"Enhancement error: {str(e)}"
            )
    
    def _compose_enhanced_system_prompt(self, base_prompt: str, memory_context: str) -> str:
        """
        Compose enhanced system prompt with memory context.
        
        Args:
            base_prompt: Base system prompt
            memory_context: Formatted memory context
            
        Returns:
            str: Enhanced system prompt
        """
        if not memory_context or not memory_context.strip():
            return base_prompt
        
        # Compose enhanced prompt with clear separation
        enhanced_prompt = f"""{base_prompt}

## Relevant Context from Previous Conversations

{memory_context}

## Instructions

Use the above context to provide more personalized and contextually aware responses. Reference specific information from previous conversations when relevant, but don't explicitly mention that you're using memory unless asked."""
        
        return enhanced_prompt
    
    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        
        This is a simple estimation. For production, use proper
        tokenizer for the target LLM.
        
        Args:
            text: Text to estimate
        
        Returns:
            Estimated token count
        """
        # Simple estimation: ~4 characters per token
        return len(text) // 4
    
    async def save_conversation_turn(
        self,
        user_message: str,
        assistant_response: str,
        session_id: str,
        user_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Save a conversation turn to memory using SessionMemoryContextManager.
        
        Delegates to the SessionMemoryContextManager for consistent memory handling
        and cache invalidation.
        
        Args:
            user_message: User's message
            assistant_response: Assistant's response
            session_id: Session ID
            user_id: User ID
            metadata: Additional metadata
        """
        # Check if saving is enabled
        if not self.config.should_save_memory():
            return
            
        # Save conversation using direct memory manager
        await self._save_conversation_direct(
            user_message, assistant_response, session_id, user_id, metadata
        )
    
    async def _save_conversation_direct(
        self,
        user_message: str,
        assistant_response: str,
        session_id: str,
        user_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Direct method for saving conversation to memory manager.
        """
        # Prepare metadata
        turn_metadata = {
            "type": "conversation_turn",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        if metadata:
            turn_metadata.update(metadata)
        
        # Save complete conversation turn as a single memory
        # This helps Mem0 understand the context better
        conversation_content = f"""User: {user_message}
Assistant: {assistant_response[:500]}"""
        
        # Add conversation memory (detailed output handled by Mem0 manager)
        conversation_memory_id = await self.memory_manager.add_memory(
            content=conversation_content,
            user_id=user_id,
            session_id=session_id,
            metadata={**turn_metadata, "role": "conversation"}
        )


