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
    EnhancedMemory, MemoryType, MemoryTier, MemoryContext
)
from backend.config import MEMORY_DB_PATH

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
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Mem0 memory manager.
        
        Args:
            config: Optional Mem0 configuration override
        """
        # Default configuration for Mem0 with Google Gemini embeddings
        default_config = {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": "ainagisa_memories",
                    "path": os.path.join(MEMORY_DB_PATH, "qdrant"),
                    "embedding_model_dims": 768,  # Google text-embedding-004 dimensions
                }
            },
            "embedder": {
                "provider": "gemini",
                "config": {
                    "model": "models/text-embedding-004",  # Latest Google embedding model
                    "embedding_dims": 768,
                    "api_key": os.getenv("GOOGLE_API_KEY")  # Add API key
                }
            },
            "version": "v1.1"
        }
        
        # Check if API key is available
        if not os.getenv("GOOGLE_API_KEY"):
            logger.warning("[Mem0 Init] GOOGLE_API_KEY not found, Mem0 may fail to initialize")
            # Fallback to a simpler embedding provider that doesn't need API keys
            default_config["embedder"] = {
                "provider": "huggingface",
                "config": {
                    "model": "sentence-transformers/all-MiniLM-L6-v2"
                }
            }
        
        # Merge with provided config
        if config:
            default_config.update(config)
        
        # Initialize Mem0
        try:
            self.memory = Memory.from_config(default_config)
            print(f"[Mem0 Init] Successfully initialized Mem0 with config")
        except Exception as e:
            print(f"[Mem0 Init] Failed to initialize Mem0: {e}")
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
        user_id: str = "default",
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add a memory to the Mem0 store.
        
        Args:
            content: Memory content
            user_id: User identifier
            session_id: Session identifier
            metadata: Additional metadata
        
        Returns:
            Memory ID
        """
        # Prepare metadata
        if metadata is None:
            metadata = {}
        
        metadata.update({
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
        })
        
        # Add memory using Mem0
        if self.memory is None:
            logger.warning(f"[Mem0 Debug] Cannot add memory, Mem0 not initialized")
            return "mock_memory_id"
            
        print(f"[Mem0 Debug] Adding memory: user_id={user_id}, content='{content[:50]}...', metadata={metadata}")
        
        try:
            result = self.memory.add(
                messages=content,
                user_id=user_id,
                metadata=metadata
            )
            print(f"[Mem0 Debug] Add result type: {type(result)}, value: {result}")
        except Exception as e:
            print(f"[Mem0 Debug] Add failed: {e}")
            return "error_memory_id"
        
        # Return the memory ID
        if isinstance(result, dict) and "id" in result:
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
        print(f"[Mem0 Timing] Starting vector search for query: '{query[:50]}...' (user: {user_id}, limit: {limit})")
        
        # Search using Mem0 - this includes vectorization + semantic search
        vectorization_start = time.time()
        try:
            # Handle case where Mem0 initialization failed
            if self.memory is None:
                print(f"[Mem0 Debug] Memory object is None, returning empty results")
                results = []
            else:
                results = self.memory.search(
                    query=query,
                    user_id=user_id,
                    limit=limit
                )
            
            # Handle case where Mem0 returns None or non-list results on empty DB
            if results is None:
                print(f"[Mem0 Debug] Search returned None for empty database")
                results = []
            elif isinstance(results, dict):
                # Mem0 returns dict with 'results' key containing the actual list
                if 'results' in results:
                    actual_results = results['results']
                    print(f"[Mem0 Debug] Extracted results from dict: {len(actual_results)} items")
                    results = actual_results if isinstance(actual_results, list) else []
                else:
                    print(f"[Mem0 Debug] Dict response missing 'results' key: {results}")
                    results = []
            elif isinstance(results, str):
                print(f"[Mem0 Debug] Search returned string instead of list: {results}")
                results = []
            elif not isinstance(results, list):
                print(f"[Mem0 Debug] Search returned unexpected type {type(results)}: {results}")
                results = []
            
            vectorization_time_ms = (time.time() - vectorization_start) * 1000
            print(f"[Mem0 Timing] Mem0 vectorization + search: {vectorization_time_ms:.2f}ms, found {len(results)} results")
            print(f"[Mem0 Debug] Search results type: {type(results)}, sample: {results[:2] if results else 'empty'}")
            
        except Exception as e:
            vectorization_time_ms = (time.time() - vectorization_start) * 1000
            print(f"[Mem0 Debug] Search failed after {vectorization_time_ms:.2f}ms: {e}")
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
            print(f"[Mem0 Timing] Session filtering: {filter_time_ms:.2f}ms, {original_count} -> {len(results)} results")
        
        total_search_time_ms = (time.time() - search_start_time) * 1000
        print(f"[Mem0 Timing] Total search operation: {total_search_time_ms:.2f}ms")
        
        return results
    
    async def get_relevant_memories_for_context(
        self,
        query_text: str,
        session_id: str,
        top_k: int = 5,
        exclude_recent_minutes: int = 10,
        memory_types: Optional[List[MemoryType]] = None,
        user_id: str = "default"
    ) -> List[EnhancedMemory]:
        """
        Get relevant memories for LLM context injection.
        
        This method retrieves and ranks memories based on relevance
        and temporal factors, specifically designed for automatic
        memory injection into LLM conversations.
        
        Args:
            query_text: Current user message for semantic search
            session_id: Current session ID
            top_k: Maximum memories to retrieve
            exclude_recent_minutes: Exclude recent memories
            memory_types: Filter by memory types
            user_id: User identifier
        
        Returns:
            List of EnhancedMemory objects with relevance scores
        """
        # Calculate time threshold
        time_threshold = datetime.now() - timedelta(minutes=exclude_recent_minutes)
        
        # Search memories with Mem0
        context_search_start = time.time()
        logger.info(f"[Mem0 Timing] Starting context memory search (top_k: {top_k}, exclude_recent: {exclude_recent_minutes}min)")
        
        raw_memories = await self.search_memories(
            query=query_text,
            user_id=user_id,
            limit=top_k * 2  # Get extra for filtering
        )
        
        context_search_time_ms = (time.time() - context_search_start) * 1000
        logger.info(f"[Mem0 Timing] Context search completed: {context_search_time_ms:.2f}ms, processing {len(raw_memories)} raw memories")
        
        # Convert to EnhancedMemory objects
        processing_start = time.time()
        enhanced_memories = []
        
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
    
    async def update_memory(
        self,
        memory_id: str,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update an existing memory.
        
        Args:
            memory_id: Memory ID to update
            content: New content (optional)
            metadata: New metadata (optional)
        
        Returns:
            Success status
        """
        try:
            # Mem0 update API
            update_data = {}
            if content:
                update_data["memory"] = content
            if metadata:
                update_data["metadata"] = metadata
            
            self.memory.update(memory_id=memory_id, data=update_data)
            return True
        except Exception as e:
            print(f"Error updating memory: {e}")
            return False
    
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
            print(f"Error deleting memory: {e}")
            return False
    
    async def get_memory_history(
        self,
        user_id: str = "default",
        memory_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get memory history (if supported by Mem0 version).
        
        Args:
            user_id: User identifier
            memory_id: Specific memory ID
        
        Returns:
            Memory history
        """
        try:
            # This depends on Mem0 version
            return self.memory.history(
                user_id=user_id,
                memory_id=memory_id
            )
        except AttributeError:
            # Method not available in this version
            return []
    
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