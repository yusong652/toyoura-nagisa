"""
Memory injection middleware for automatic context enhancement.

This module provides the middleware layer that automatically injects
relevant memories into LLM conversations without explicit tool calls.
"""

import asyncio
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from backend.infrastructure.memory.mem0_manager import Mem0MemoryManager
from backend.domain.models.memory_context import (
    MemoryContext, MemoryInjectionResult, MemoryType
)


class MemoryInjectionMiddleware:
    """
    Middleware for automatic memory injection into LLM context.
    
    This class handles the automatic retrieval and formatting of memories
    to be injected as context before LLM processing.
    """
    
    def __init__(
        self,
        memory_manager: Optional[Mem0MemoryManager] = None,
        max_injection_time_ms: int = 200,
        max_context_tokens: int = 1000,
        enable_injection: bool = True
    ):
        """
        Initialize memory injection middleware.
        
        Args:
            memory_manager: Memory manager instance (creates new if None)
            max_injection_time_ms: Maximum time for injection operation
            max_context_tokens: Maximum tokens for memory context
            enable_injection: Global flag to enable/disable injection
        """
        self.memory_manager = memory_manager or Mem0MemoryManager()
        self.max_injection_time_ms = max_injection_time_ms
        self.max_context_tokens = max_context_tokens
        self.enable_injection = enable_injection
    
    async def inject_memory_context(
        self,
        messages: List[Dict[str, Any]],
        session_id: str,
        user_id: str = "default",
        options: Optional[Dict[str, Any]] = None
    ) -> tuple[List[Dict[str, Any]], MemoryInjectionResult]:
        """
        Inject relevant memory context into messages.
        
        This is the main entry point for memory injection. It analyzes
        the current conversation, retrieves relevant memories, and
        injects them as system context.
        
        Args:
            messages: Original message list
            session_id: Current session ID
            user_id: User identifier
            options: Optional injection options
        
        Returns:
            Tuple of (enhanced_messages, injection_result)
        """
        start_time = time.time()
        
        # Check if injection is enabled
        if not self.enable_injection:
            return messages, MemoryInjectionResult(
                success=False,
                injected_count=0,
                injection_time_ms=0,
                error="Memory injection disabled"
            )
        
        try:
            # Extract query from latest user message
            query_text = self._extract_query_from_messages(messages)
            if not query_text:
                return messages, MemoryInjectionResult(
                    success=False,
                    injected_count=0,
                    injection_time_ms=0,
                    error="No user query found"
                )
            
            # Parse options
            opts = options or {}
            top_k = opts.get("top_k", 5)
            exclude_recent = opts.get("exclude_recent_minutes", 10)
            memory_types = opts.get("memory_types")
            relevance_threshold = opts.get("relevance_threshold", 0.5)
            
            # Create memory context
            memory_context = MemoryContext(
                session_id=session_id,
                query=query_text,
                top_k=top_k,
                exclude_recent_minutes=exclude_recent,
                memory_types=memory_types,
                relevance_threshold=relevance_threshold
            )
            
            # Retrieve relevant memories with timeout
            memories = await self._retrieve_memories_with_timeout(
                memory_context,
                user_id
            )
            
            memory_context.memories = memories
            
            # Format memories for injection
            formatted_context = memory_context.format_for_injection()
            
            if not formatted_context:
                # No relevant memories found
                elapsed_ms = (time.time() - start_time) * 1000
                return messages, MemoryInjectionResult(
                    success=True,
                    injected_count=0,
                    injection_time_ms=elapsed_ms,
                    formatted_context=""
                )
            
            # Create enhanced messages with memory context
            enhanced_messages = self._inject_context_into_messages(
                messages,
                formatted_context
            )
            
            # Calculate metrics
            elapsed_ms = (time.time() - start_time) * 1000
            context_tokens = self._estimate_tokens(formatted_context)
            
            return enhanced_messages, MemoryInjectionResult(
                success=True,
                injected_count=len(memory_context.filter_by_relevance()),
                injection_time_ms=elapsed_ms,
                context_tokens=context_tokens,
                formatted_context=formatted_context
            )
            
        except asyncio.TimeoutError:
            elapsed_ms = (time.time() - start_time) * 1000
            return messages, MemoryInjectionResult(
                success=False,
                injected_count=0,
                injection_time_ms=elapsed_ms,
                error="Memory retrieval timeout"
            )
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            return messages, MemoryInjectionResult(
                success=False,
                injected_count=0,
                injection_time_ms=elapsed_ms,
                error=f"Injection error: {str(e)}"
            )
    
    async def _retrieve_memories_with_timeout(
        self,
        memory_context: MemoryContext,
        user_id: str
    ) -> List[Any]:
        """
        Retrieve memories with timeout protection.
        
        Args:
            memory_context: Memory retrieval context
            user_id: User identifier
        
        Returns:
            List of retrieved memories
        """
        timeout_seconds = self.max_injection_time_ms / 1000
        
        # Create retrieval task
        retrieval_task = self.memory_manager.get_relevant_memories_for_context(
            query_text=memory_context.query,
            session_id=memory_context.session_id,
            top_k=memory_context.top_k,
            exclude_recent_minutes=memory_context.exclude_recent_minutes,
            memory_types=memory_context.memory_types,
            user_id=user_id
        )
        
        # Wait with timeout
        memories = await asyncio.wait_for(
            retrieval_task,
            timeout=timeout_seconds
        )
        
        return memories
    
    def _extract_query_from_messages(
        self,
        messages: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Extract the latest user query from messages.
        
        Args:
            messages: List of message dictionaries
        
        Returns:
            Latest user query text or None
        """
        # Find the latest user message
        for message in reversed(messages):
            if message.get("role") == "user":
                content = message.get("content", "")
                
                # Handle different content formats
                if isinstance(content, str):
                    return content
                elif isinstance(content, list):
                    # Extract text from structured content
                    text_parts = []
                    for item in content:
                        if isinstance(item, dict):
                            if "text" in item:
                                text_parts.append(item["text"])
                            elif item.get("type") == "text":
                                text_parts.append(item.get("text", ""))
                    return " ".join(text_parts)
        
        return None
    
    def _inject_context_into_messages(
        self,
        messages: List[Dict[str, Any]],
        formatted_context: str
    ) -> List[Dict[str, Any]]:
        """
        Inject formatted memory context into messages.
        
        The context is added as a system message at the beginning
        of the conversation to provide background without disrupting
        the message flow.
        
        Args:
            messages: Original messages
            formatted_context: Formatted memory context
        
        Returns:
            Enhanced messages with injected context
        """
        # Create a copy to avoid modifying original
        enhanced_messages = messages.copy()
        
        # Create system message with memory context
        memory_message = {
            "role": "system",
            "content": formatted_context,
            "metadata": {
                "type": "memory_context",
                "timestamp": datetime.now().isoformat()
            }
        }
        
        # Find insertion point (after initial system message if exists)
        insert_index = 0
        if enhanced_messages and enhanced_messages[0].get("role") == "system":
            # Check if it's not already a memory context
            if enhanced_messages[0].get("metadata", {}).get("type") != "memory_context":
                insert_index = 1
            else:
                # Replace existing memory context
                enhanced_messages[0] = memory_message
                return enhanced_messages
        
        # Insert memory context
        enhanced_messages.insert(insert_index, memory_message)
        
        return enhanced_messages
    
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
        Save a conversation turn to memory.
        
        This should be called after each successful conversation turn
        to build up the memory database.
        
        Args:
            user_message: User's message
            assistant_response: Assistant's response
            session_id: Session ID
            user_id: User ID
            metadata: Additional metadata
        """
        # Prepare metadata
        turn_metadata = {
            "type": "conversation_turn",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        if metadata:
            turn_metadata.update(metadata)
        
        # Save user message
        await self.memory_manager.add_memory(
            content=f"User said: {user_message}",
            user_id=user_id,
            session_id=session_id,
            metadata={**turn_metadata, "role": "user"}
        )
        
        # Save assistant response (extract key points)
        await self.memory_manager.add_memory(
            content=f"Assistant responded: {assistant_response[:500]}",  # Truncate long responses
            user_id=user_id,
            session_id=session_id,
            metadata={**turn_metadata, "role": "assistant"}
        )


class MemoryPerformanceGuard:
    """
    Performance protection for memory operations.
    
    Ensures memory operations don't degrade system performance.
    """
    
    MAX_INJECTION_TIME_MS = 200
    MAX_MEMORY_CONTEXT_TOKENS = 1000
    FALLBACK_ON_TIMEOUT = True
    
    @classmethod
    async def safe_inject_memory(
        cls,
        middleware: MemoryInjectionMiddleware,
        messages: List[Dict[str, Any]],
        session_id: str,
        user_id: str = "default"
    ) -> tuple[List[Dict[str, Any]], MemoryInjectionResult]:
        """
        Safely inject memory with performance guards.
        
        Args:
            middleware: Memory injection middleware
            messages: Original messages
            session_id: Session ID
            user_id: User ID
        
        Returns:
            Enhanced messages and injection result
        """
        try:
            # Set timeout for injection
            timeout = cls.MAX_INJECTION_TIME_MS / 1000
            
            # Run injection with timeout
            result = await asyncio.wait_for(
                middleware.inject_memory_context(
                    messages=messages,
                    session_id=session_id,
                    user_id=user_id
                ),
                timeout=timeout
            )
            
            return result
            
        except asyncio.TimeoutError:
            if cls.FALLBACK_ON_TIMEOUT:
                # Return original messages on timeout
                return messages, MemoryInjectionResult(
                    success=False,
                    injected_count=0,
                    injection_time_ms=cls.MAX_INJECTION_TIME_MS,
                    error="Timeout - falling back to no memory"
                )
            raise