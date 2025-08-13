"""
Memory injection middleware for automatic context enhancement.

This module provides the middleware layer that automatically injects
relevant memories into LLM conversations without explicit tool calls.
"""

import asyncio
import time
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from backend.infrastructure.memory.mem0_manager import Mem0MemoryManager
from backend.domain.models.memory_context import (
    MemoryContext, MemoryInjectionResult, MemoryType
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
        print(f"[Memory Injection] Starting inject_memory_context for session {session_id} with {len(messages)} messages")
        
        # Check if injection is enabled and auto-inject is on
        if not self.config.should_inject_memory():
            print(f"[Memory Injection] Memory injection disabled or auto-inject off, returning original messages")
            return messages, MemoryInjectionResult(
                success=False,
                injected_count=0,
                injection_time_ms=0,
                error="Memory injection disabled or auto-inject off"
            )
        
        try:
            # Extract query from latest user message
            query_extraction_start = time.time()
            query_text = self._extract_query_from_messages(messages)
            query_extraction_time_ms = (time.time() - query_extraction_start) * 1000
            print(f"[Memory Timing] Query extraction: {query_extraction_time_ms:.2f}ms")
            
            if not query_text:
                print(f"[Memory Timing] No user query found after {query_extraction_time_ms:.2f}ms")
                return messages, MemoryInjectionResult(
                    success=False,
                    injected_count=0,
                    injection_time_ms=query_extraction_time_ms,
                    error="No user query found"
                )
            
            # Parse options with config defaults
            opts = options or {}
            top_k = opts.get("top_k", self.config.max_memories_to_inject)
            exclude_recent = opts.get("exclude_recent_minutes", self.config.get_time_filter_minutes())
            memory_types = opts.get("memory_types")
            relevance_threshold = opts.get("relevance_threshold", self.config.memory_relevance_threshold)
            
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
            memory_retrieval_start = time.time()
            print(f"[Memory Timing] Starting memory retrieval for query: '{query_text[:50]}...'")
            
            memories = await self._retrieve_memories_with_timeout(
                memory_context,
                user_id
            )
            
            memory_retrieval_time_ms = (time.time() - memory_retrieval_start) * 1000
            print(f"[Memory Timing] Memory retrieval: {memory_retrieval_time_ms:.2f}ms, Found {len(memories)} memories")
            
            # Debug: Show found memories
            if memories:
                print(f"[Memory Debug] Found {len(memories)} memories:")
                for i, memory in enumerate(memories[:3]):  # Show first 3 memories
                    print(f"[Memory Debug]   {i+1}. Type: {getattr(memory, 'memory_type', 'unknown')}, Content: {getattr(memory, 'content', str(memory))[:50]}...")
            else:
                print(f"[Memory Debug] No memories found for query")
            
            memory_context.memories = memories
            
            # Format memories for injection
            formatting_start = time.time()
            formatted_context = memory_context.format_for_injection()
            formatting_time_ms = (time.time() - formatting_start) * 1000
            print(f"[Memory Timing] Memory formatting: {formatting_time_ms:.2f}ms")
            
            # Debug: Show formatted context
            if formatted_context:
                print(f"[Memory Debug] Formatted context preview: {formatted_context[:200]}...")
            else:
                print(f"[Memory Debug] No formatted context generated")
            
            if not formatted_context:
                # No relevant memories found
                elapsed_ms = (time.time() - start_time) * 1000
                print(f"[Memory Timing] No memories to inject after {elapsed_ms:.2f}ms")
                return messages, MemoryInjectionResult(
                    success=True,
                    injected_count=0,
                    injection_time_ms=elapsed_ms,
                    formatted_context=""
                )
            
            # Create enhanced messages with memory context
            injection_start = time.time()
            enhanced_messages = self._inject_context_into_messages(
                messages,
                formatted_context
            )
            injection_time_ms = (time.time() - injection_start) * 1000
            print(f"[Memory Timing] Context injection: {injection_time_ms:.2f}ms")
            
            # Calculate metrics
            elapsed_ms = (time.time() - start_time) * 1000
            context_tokens = self._estimate_tokens(formatted_context)
            
            print(
                f"[Memory Timing] Complete injection pipeline: {elapsed_ms:.2f}ms "
                f"(Query: {query_extraction_time_ms:.1f}ms, "
                f"Retrieval: {memory_retrieval_time_ms:.1f}ms, "
                f"Formatting: {formatting_time_ms:.1f}ms, "
                f"Injection: {injection_time_ms:.1f}ms) - "
                f"Context tokens: {context_tokens}"
            )
            
            return enhanced_messages, MemoryInjectionResult(
                success=True,
                injected_count=len(memory_context.filter_by_relevance()),
                injection_time_ms=elapsed_ms,
                context_tokens=context_tokens,
                formatted_context=formatted_context
            )
            
        except asyncio.TimeoutError:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"[Memory Timing] Timeout after {elapsed_ms:.2f}ms")
            return messages, MemoryInjectionResult(
                success=False,
                injected_count=0,
                injection_time_ms=elapsed_ms,
                error="Memory retrieval timeout"
            )
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"[Memory Timing] Error after {elapsed_ms:.2f}ms: {str(e)}")
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
        logger.info(f"[Memory Debug] Extracting query from {len(messages)} messages")
        logger.info(f"[Memory Debug] Messages types: {[type(msg) for msg in messages]}")
        
        # Find the latest user message
        for i, message in enumerate(reversed(messages)):
            logger.info(f"[Memory Debug] Processing message {i}: type={type(message)}")
            
            # Check if message is actually a dictionary
            if not isinstance(message, dict):
                logger.error(f"[Memory Debug] Message {i} is {type(message)}, not dict: {message}")
                continue
                
            try:
                role = message.get("role")
                logger.info(f"[Memory Debug] Message {i} role: {role}")
                
                if role == "user":
                    content = message.get("content", "")
                    logger.info(f"[Memory Debug] User message content type: {type(content)}")
                    
                    # Handle different content formats
                    if isinstance(content, str):
                        if content.strip():
                            logger.info(f"[Memory Debug] Extracted string query: '{content[:50]}...'")
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
                        extracted = " ".join(text_parts)
                        if extracted.strip():
                            logger.info(f"[Memory Debug] Extracted list query: '{extracted[:50]}...'")
                            return extracted
            except Exception as e:
                logger.error(f"[Memory Debug] Exception processing message {i}: {e}")
                continue
        
        logger.warning("[Memory Debug] No user query found")
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
            print(f"[Memory Timing] Memory retrieval: {memory_retrieval_time_ms:.2f}ms, Found {len(memories)} memories")
            
            memory_context.memories = memories
            
            # Format memories for injection
            formatting_start = time.time()
            formatted_context = memory_context.format_for_injection()
            formatting_time_ms = (time.time() - formatting_start) * 1000
            
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
            print(f"[DEBUG] Formatted context preview: {formatted_context[:200]}...")
            enhanced_prompt = self._compose_enhanced_system_prompt(base_system_prompt, formatted_context)
            print(f"[DEBUG] Enhanced prompt length: {len(enhanced_prompt)}, base length: {len(base_system_prompt)}")
            
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
            print(f"[DEBUG] Memory saving disabled, skipping conversation turn")
            return
            
        print(f"[DEBUG] Saving conversation turn: user='{user_message[:50]}...' assistant='{assistant_response[:50]}...'")
        # Save conversation using direct memory manager
        await self._save_conversation_direct(
            user_message, assistant_response, session_id, user_id, metadata
        )
        print(f"[DEBUG] Conversation turn saved successfully")
    
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
        
        print(f"[DEBUG] Adding conversation memory for turn")
        conversation_memory_id = await self.memory_manager.add_memory(
            content=conversation_content,
            user_id=user_id,
            session_id=session_id,
            metadata={**turn_metadata, "role": "conversation"}
        )
        
        if conversation_memory_id in ["filtered_by_mem0", ""]:
            # Mem0 filtered this as non-memorable - this is expected for technical/temporary discussions
            print(f"[DEBUG] Conversation not saved by Mem0 (filtered as non-memorable - likely technical/temporary content)")
        else:
            print(f"[DEBUG] Conversation memory saved with ID: {conversation_memory_id}")
            # Log what was actually saved
            if conversation_memory_id != "filtered_by_mem0":
                print(f"[DEBUG] Mem0 extracted memorable content from conversation")


class MemoryPerformanceGuard:
    """
    Performance protection for memory operations.
    
    Ensures memory operations don't degrade system performance.
    """
    
    def __init__(self, config: Optional[MemoryConfig] = None):
        """Initialize with config."""
        self.config = config or MemoryConfig()
        self.MAX_INJECTION_TIME_MS = self.config.memory_search_timeout_ms
        self.MAX_MEMORY_CONTEXT_TOKENS = self.config.max_memories_to_inject * 200
        self.FALLBACK_ON_TIMEOUT = True
    
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
            print(f"[Memory Guard] Starting safe injection with timeout {timeout}s")
            
            # Run injection with timeout
            result = await asyncio.wait_for(
                middleware.inject_memory_context(
                    messages=messages,
                    session_id=session_id,
                    user_id=user_id
                ),
                timeout=timeout
            )
            
            logger.info(f"[Memory Guard] Safe injection completed successfully")
            
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