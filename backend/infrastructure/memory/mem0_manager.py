"""
Mem0-based memory manager for aiNagisa.

This module provides a modern memory management system using Mem0,
replacing the legacy ChromaDB-based implementation.
"""

import os
import time
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import math
from mem0 import Memory
from backend.domain.models.memory_context import (
    EnhancedMemory, MemoryType, MemoryTier
)
from backend.config.memory import MemoryConfig

logger = logging.getLogger(__name__)


class Mem0MemoryManager:
    """
    Memory manager using Mem0 framework for intelligent memory operations.
    
    Mem0 provides:
    - Automatic memory extraction and management
    - Built-in relevance scoring
    - Multi-user and multi-agent support
    - Time-aware memory retrieval
    """
    
    def __init__(self, config: Optional[MemoryConfig] = None):
        """
        Initialize Mem0 memory manager.
        
        Args:
            config: Optional MemoryConfig instance
        """
        # Use provided config or create default
        self.config = config or MemoryConfig()
        
        # Build complete Mem0 configuration from MemoryConfig
        mem0_config = self.config.build_mem0_config()
        
        # Log API key status
        if not os.getenv("GOOGLE_API_KEY"):
            logger.warning("[Mem0 Init] GOOGLE_API_KEY not found, using HuggingFace fallback")
        
        # Initialize Mem0
        try:
            if self.config.debug_mode:
                logger.info(f"[Mem0 Init] Attempting to initialize with config: {mem0_config}")
            self.memory = Memory.from_config(mem0_config)
            if self.config.debug_mode:
                logger.info(f"[Mem0 Init] Successfully initialized Mem0")
                logger.info(f"[Mem0 LLM Config] Using {self.config.mem0_llm_provider} with model {self.config.mem0_llm_model}")
        except Exception as e:
            logger.error(f"[Mem0 Init] Failed to initialize Mem0: {e}")
            # Create a mock memory object that returns empty results
            self.memory = None
        
        # Memory type decay rates (per day)
        self.decay_rates = {
            MemoryType.PREFERENCE: 0.01,
            MemoryType.FACT: 0.02,
            MemoryType.CONTEXT: 0.05,
            MemoryType.EVENT: 0.03
        }
    
    async def add_memory(
        self,
        content: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add a memory to the Mem0 store.
        
        Args:
            content: Memory content
            user_id: User identifier (uses config default if None)
            session_id: Session identifier
            metadata: Additional metadata
        
        Returns:
            Memory ID
        """
        # Use config defaults
        user_id = user_id or self.config.mem0_user_id
        
        # Check if saving is enabled
        if not self.config.should_save_memory():
            if self.config.debug_mode:
                logger.info("[Mem0] Memory saving disabled, skipping")
            return "disabled_memory_id"
        # Prepare metadata
        if metadata is None:
            metadata = {}
        
        metadata.update({
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
        })
        
        # Add memory using Mem0
        if self.memory is None:
            logger.warning("[Mem0] Cannot add memory, Mem0 not initialized")
            return "mock_memory_id"
            
        if self.config.debug_mode:
            logger.info(f"[Mem0 Debug] Adding memory: user_id={user_id}, content='{content[:50]}...', metadata={metadata}")
        
        try:
            result = self.memory.add(
                messages=content,
                user_id=user_id,
                metadata=metadata
            )
            if self.config.debug_mode:
                logger.info(f"[Mem0 Debug] Add result type: {type(result)}, value: {result}")
        except Exception as e:
            logger.error(f"[Mem0] Add failed: {e}")
            return "error_memory_id"
        
        # Return the memory ID
        # Handle Mem0's response format: {'results': [{'id': '...', 'memory': '...', 'event': 'ADD'}]}
        if isinstance(result, dict):
            if "results" in result and isinstance(result["results"], list):
                if len(result["results"]) > 0:
                    # Process each result item (might include ADD, UPDATE, DELETE events)
                    for item in result["results"]:
                        if isinstance(item, dict):
                            event_type = item.get("event", "ADD")
                            memory_id = item.get("id", "")
                            memory_text = item.get("memory", item.get("text", ""))
                            
                            # Handle potential errors in result items first
                            if "error" in item:
                                logger.warning(f"[MEMORY] Error in {event_type} event for memory {memory_id}: {item['error']}")
                                continue
                            
                            # Log different event types with consistent formatting
                            if self.config.debug_mode:
                                if event_type == "UPDATE":
                                    old_memory = item.get("old_memory", "")
                                    print(f"[MEMORY] {event_type}: Memory {memory_id} updated")
                                    print(f"  OLD: {old_memory}")
                                    print(f"  NEW: {memory_text}")
                                elif event_type == "DELETE":
                                    print(f"[MEMORY] {event_type}: Memory {memory_id} deleted")
                                    print(f"  Content: {memory_text}")
                                elif event_type == "ADD":
                                    print(f"[MEMORY] {event_type}: Memory {memory_id} added")
                                    print(f"  Content: {memory_text}")
                                else:
                                    # Unknown event type
                                    print(f"[MEMORY] {event_type}: Unknown event for memory {memory_id}")
                            else:
                                # Non-debug mode: only show essential info
                                if event_type == "ADD":
                                    print(f"[MEMORY] Stored: {memory_text}")
                    
                    # Return the ID from the first result with an ID
                    first_result = result["results"][0]
                    if isinstance(first_result, dict) and "id" in first_result:
                        return first_result["id"]
                else:
                    # Empty results - Mem0 decided not to save this memory
                    print(f"[MEMORY] Content filtered by Mem0 (not memorable)")
                    return "filtered_by_mem0"
            elif "id" in result:
                return result["id"]
        elif isinstance(result, list) and len(result) > 0:
            return result[0].get("id", "")
        return ""
    
    async def search_memories(
        self,
        query: str,
        user_id: str = "default",
        limit: int = 5,
        session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search memories using Mem0's built-in search.
        
        Args:
            query: Search query
            user_id: User identifier
            limit: Maximum results
            session_id: Optional session filter
        
        Returns:
            List of memory dictionaries
        """
        # Start timing for vectorization and search
        search_start_time = time.time()
        if self.config.debug_mode:
            logger.info(f"[Mem0 Timing] Starting vector search for query: '{query[:50]}...' (user: {user_id}, limit: {limit})")
        
        # Search using Mem0 - this includes vectorization + semantic search
        vectorization_start = time.time()
        try:
            # Handle case where Mem0 initialization failed
            if self.memory is None:
                if self.config.debug_mode:
                    logger.info(f"[Mem0 Debug] Memory object is None, returning empty results")
                results = []
            else:
                results = self.memory.search(
                    query=query,
                    user_id=user_id,
                    limit=limit
                )
            
            # Handle case where Mem0 returns None or non-list results on empty DB
            if results is None:
                if self.config.debug_mode:
                    logger.info(f"[Mem0 Debug] Search returned None for empty database")
                results = []
            elif isinstance(results, dict):
                # Mem0 returns dict with 'results' key containing the actual list
                if 'results' in results:
                    actual_results = results['results']
                    if self.config.debug_mode:
                        logger.info(f"[Mem0 Debug] Extracted results from dict: {len(actual_results)} items")
                    results = actual_results if isinstance(actual_results, list) else []
                else:
                    if self.config.debug_mode:
                        logger.info(f"[Mem0 Debug] Dict response missing 'results' key: {results}")
                    results = []
            elif isinstance(results, str):
                if self.config.debug_mode:
                    logger.info(f"[Mem0 Debug] Search returned string instead of list: {results}")
                results = []
            elif not isinstance(results, list):
                if self.config.debug_mode:
                    logger.info(f"[Mem0 Debug] Search returned unexpected type {type(results)}: {results}")
                results = []
            
            vectorization_time_ms = (time.time() - vectorization_start) * 1000
            if self.config.debug_mode:
                logger.info(f"[Mem0 Timing] Mem0 vectorization + search: {vectorization_time_ms:.2f}ms, found {len(results)} results")
                logger.info(f"[Mem0 Debug] Search results type: {type(results)}, sample: {results[:2] if results else 'empty'}")
            
        except Exception as e:
            vectorization_time_ms = (time.time() - vectorization_start) * 1000
            logger.error(f"[Mem0] Search failed after {vectorization_time_ms:.2f}ms: {e}")
            # Return empty list on search failure
            results = []
        
        # Filter by session if specified
        if session_id:
            filter_start = time.time()
            original_count = len(results)
            results = [
                r for r in results 
                if r.get("metadata", {}).get("session_id") == session_id
            ]
            filter_time_ms = (time.time() - filter_start) * 1000
            if self.config.debug_mode:
                logger.info(f"[Mem0 Timing] Session filtering: {filter_time_ms:.2f}ms, {original_count} -> {len(results)} results")
        
        total_search_time_ms = (time.time() - search_start_time) * 1000
        if self.config.debug_mode:
            logger.info(f"[Mem0 Timing] Total search operation: {total_search_time_ms:.2f}ms")
        
        return results
    
    async def get_relevant_memories_for_context(
        self,
        query_text: str,
        session_id: str,
        top_k: Optional[int] = None,
        exclude_recent_minutes: Optional[int] = None,
        memory_types: Optional[List[MemoryType]] = None,
        user_id: Optional[str] = None
    ) -> List[EnhancedMemory]:
        """
        Get relevant memories for LLM context injection.
        
        This method retrieves and ranks memories based on relevance
        and temporal factors, specifically designed for automatic
        memory injection into LLM conversations.
        
        Args:
            query_text: Current user message for semantic search
            session_id: Current session ID
            top_k: Maximum memories to retrieve (uses config default if None)
            exclude_recent_minutes: Exclude recent memories (uses config default if None)
            memory_types: Filter by memory types
            user_id: User identifier (uses config default if None)
        
        Returns:
            List of EnhancedMemory objects with relevance scores
        """
        # Use config defaults if not provided
        top_k = top_k if top_k is not None else self.config.max_memories_to_inject
        exclude_recent_minutes = exclude_recent_minutes if exclude_recent_minutes is not None else self.config.get_time_filter_minutes()
        user_id = user_id or self.config.mem0_user_id
        
        # Check if memory is enabled
        if not self.config.is_memory_active():
            if self.config.debug_mode:
                logger.info("[Mem0] Memory system disabled, returning empty list")
            return []
        
        # Calculate time threshold
        time_threshold = datetime.now() - timedelta(minutes=exclude_recent_minutes)
        
        # Search memories with Mem0
        context_search_start = time.time()
        if self.config.debug_mode:
            logger.info(f"[Mem0 Timing] Starting context memory search (top_k: {top_k}, exclude_recent: {exclude_recent_minutes}min)")
        
        raw_memories = await self.search_memories(
            query=query_text,
            user_id=user_id,
            limit=top_k * 2  # Get extra for filtering
        )
        
        context_search_time_ms = (time.time() - context_search_start) * 1000
        if self.config.debug_mode:
            logger.info(f"[Mem0 Timing] Context search completed: {context_search_time_ms:.2f}ms, processing {len(raw_memories)} raw memories")
        
        # Convert to EnhancedMemory objects
        processing_start = time.time()
        enhanced_memories = []
        
        if self.config.debug_mode:
            logger.info(f"[Mem0 Debug] Processing {len(raw_memories)} raw memories")
            logger.info(f"[Mem0 Debug] Raw memories sample: {raw_memories[:1] if raw_memories else 'empty'}")
        
        for i, mem in enumerate(raw_memories):
            logger.debug(f"[Mem0 Debug] Processing memory {i}: type={type(mem)}, keys={list(mem.keys()) if isinstance(mem, dict) else 'not_dict'}")
            
            if not isinstance(mem, dict):
                logger.error(f"[Mem0 Debug] Memory {i} is not dict: {type(mem)} - {mem}")
                continue
            metadata = mem.get("metadata", {})
            
            # Parse timestamp
            timestamp_str = metadata.get("timestamp")
            if timestamp_str:
                timestamp = datetime.fromisoformat(timestamp_str)
                # Skip if too recent
                if exclude_recent_minutes > 0 and timestamp > time_threshold:
                    continue
                # Skip if too old (if max age is configured)
                max_age_minutes = self.config.get_max_age_minutes()
                if max_age_minutes is not None:
                    max_age_threshold = datetime.now() - timedelta(minutes=max_age_minutes)
                    if timestamp < max_age_threshold:
                        continue
            else:
                timestamp = datetime.now()
            
            # Classify memory type
            memory_type = self._classify_memory_type(
                mem.get("memory", ""),
                metadata
            )
            
            # Filter by type if specified
            if memory_types and memory_type not in memory_types:
                continue
            
            # Calculate relevance with time decay
            base_relevance = mem.get("score", 0.5)
            age_days = (datetime.now() - timestamp).days
            time_weight = self._calculate_time_weight(memory_type, age_days)
            final_relevance = base_relevance * time_weight
            
            # Determine memory tier
            memory_tier = self._determine_memory_tier(age_days)
            
            # Create EnhancedMemory
            enhanced_memory = EnhancedMemory(
                content=mem.get("memory", ""),
                embedding=[],  # Mem0 handles embeddings internally
                timestamp=timestamp,
                session_id=metadata.get("session_id", session_id),
                memory_type=memory_type,
                memory_tier=memory_tier,
                confidence=self._calculate_confidence(base_relevance, metadata),
                source=metadata.get("source", "conversation"),
                metadata=metadata,
                relevance_score=final_relevance
            )
            
            enhanced_memories.append(enhanced_memory)
        
        # Sort by relevance and return top_k
        sort_start = time.time()
        enhanced_memories.sort(key=lambda m: m.relevance_score, reverse=True)
        sort_time_ms = (time.time() - sort_start) * 1000
        
        processing_time_ms = (time.time() - processing_start) * 1000
        final_memories = enhanced_memories[:top_k]
        
        if self.config.debug_mode:
            logger.info(
                f"[Mem0 Timing] Memory processing: {processing_time_ms:.2f}ms "
                f"(Sort: {sort_time_ms:.2f}ms), "
                f"final count: {len(final_memories)}"
            )
        
        return final_memories
    
    async def get_all_memories(
        self,
        user_id: str = "default",
        session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all memories for a user or session.
        
        Args:
            user_id: User identifier
            session_id: Optional session filter
        
        Returns:
            List of all memories
        """
        # Get all memories from Mem0
        all_memories = self.memory.get_all(user_id=user_id)
        
        # Filter by session if specified
        if session_id:
            all_memories = [
                m for m in all_memories
                if m.get("metadata", {}).get("session_id") == session_id
            ]
        
        return all_memories
    
    async def delete_memory(
        self,
        memory_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> bool:
        """
        Delete memories by ID, user, or session.
        
        Args:
            memory_id: Specific memory ID
            user_id: Delete all memories for user
            session_id: Delete all memories for session
        
        Returns:
            Success status
        """
        try:
            if memory_id:
                # Delete specific memory
                self.memory.delete(memory_id=memory_id)
            elif user_id:
                # Delete all memories for user
                self.memory.delete_all(user_id=user_id)
            elif session_id:
                # Delete memories for session
                memories = await self.get_all_memories(session_id=session_id)
                for mem in memories:
                    if "id" in mem:
                        self.memory.delete(memory_id=mem["id"])
            
            return True
        except Exception as e:
            logger.error(f"Error deleting memory: {e}")
            return False
    
    def _classify_memory_type(
        self,
        content: str,
        metadata: Dict[str, Any]
    ) -> MemoryType:
        """
        Classify memory type based on content analysis.
        
        Args:
            content: Memory content
            metadata: Memory metadata
        
        Returns:
            Classified MemoryType
        """
        # Check metadata first
        if "memory_type" in metadata:
            try:
                return MemoryType(metadata["memory_type"])
            except ValueError:
                pass
        
        content_lower = content.lower()
        
        # Preference indicators
        if any(kw in content_lower for kw in [
            "i like", "i prefer", "i love", "i hate",
            "my favorite", "i don't like", "i enjoy"
        ]):
            return MemoryType.PREFERENCE
        
        # Fact indicators
        if any(kw in content_lower for kw in [
            "i am", "i work", "i live", "my name",
            "my job", "my age", "my birthday"
        ]):
            return MemoryType.FACT
        
        # Event indicators
        if any(kw in content_lower for kw in [
            "yesterday", "today", "tomorrow", "last week",
            "happened", "will", "going to"
        ]):
            return MemoryType.EVENT
        
        # Default to context
        return MemoryType.CONTEXT
    
    def _calculate_time_weight(
        self,
        memory_type: MemoryType,
        age_days: int
    ) -> float:
        """
        Calculate time-based weight with exponential decay.
        
        Args:
            memory_type: Type of memory
            age_days: Age in days
        
        Returns:
            Time weight factor
        """
        decay_rate = self.decay_rates.get(memory_type, 0.03)
        return math.exp(-decay_rate * age_days)
    
    def _determine_memory_tier(self, age_days: int) -> MemoryTier:
        """
        Determine memory tier based on age.
        
        Args:
            age_days: Age in days
        
        Returns:
            Memory tier classification
        """
        if age_days < 1:
            return MemoryTier.WORKING
        elif age_days < 7:
            return MemoryTier.SHORT_TERM
        elif age_days < 30:
            return MemoryTier.MEDIUM_TERM
        else:
            return MemoryTier.LONG_TERM
    
    def _calculate_confidence(
        self,
        base_relevance: float,
        metadata: Dict[str, Any]
    ) -> float:
        """
        Calculate confidence score for a memory.
        
        Args:
            base_relevance: Base relevance score
            metadata: Memory metadata
        
        Returns:
            Confidence score (0-1)
        """
        confidence = base_relevance
        
        # Boost for rich metadata
        if "message_id" in metadata:
            confidence += 0.05
        if metadata.get("user_confirmed"):
            confidence += 0.2
        
        return min(1.0, confidence)