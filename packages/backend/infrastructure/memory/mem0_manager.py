"""
Mem0-based memory manager for toyoura-nagisa.

This module provides a modern memory management system using Mem0,
replacing the legacy ChromaDB-based implementation.
"""

import logging
from typing import List, Dict, Any, Optional
from mem0 import Memory
from backend.domain.models.memory_context import EnhancedMemory
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

    def __init__(self):
        """
        Initialize Mem0 memory manager.

        Loads configuration directly from backend.config.memory.
        """
        # Ensure environment variables are loaded
        from dotenv import load_dotenv
        import os
        from pathlib import Path

        # Try to load .env from multiple locations
        env_paths = [
            Path(".env"),
            Path("backend/.env"),
            Path(__file__).parent.parent.parent / ".env",
            Path(__file__).parent.parent.parent.parent / ".env",
        ]

        for env_path in env_paths:
            if env_path.exists():
                load_dotenv(env_path)
                print(f"[Mem0 Init] Loaded environment from {env_path}")
                break

        # Load configuration directly from backend.config
        self.config = MemoryConfig()

        # Build complete Mem0 configuration from MemoryConfig
        mem0_config = self.config.build_mem0_config()

        # Log API key status
        google_key = os.getenv("GOOGLE_API_KEY")
        if not google_key:
            logger.warning("[Mem0 Init] GOOGLE_API_KEY not found, using HuggingFace fallback")
        else:
            print(f"[Mem0 Init] Using Google API key (length: {len(google_key)})")

        # Initialize Mem0
        print(f"[Mem0 Init] Configuration details:")
        print(f"  Embedder provider: {mem0_config.get('embedder', {}).get('provider', 'unknown')}")
        print(f"  Embedder model: {mem0_config.get('embedder', {}).get('config', {}).get('model', 'unknown')}")
        print(f"  Vector store provider: {mem0_config.get('vector_store', {}).get('provider', 'unknown')}")
        print(f"  Vector store path: {mem0_config.get('vector_store', {}).get('config', {}).get('path', 'unknown')}")
        print(
            f"  Collection name: {mem0_config.get('vector_store', {}).get('config', {}).get('collection_name', 'unknown')}"
        )
        print(
            f"  Embedding dimensions: {mem0_config.get('vector_store', {}).get('config', {}).get('embedding_model_dims', 'unknown')}"
        )

        if self.config.debug_mode:
            logger.info(f"[Mem0 Init] Attempting to initialize with config: {mem0_config}")

        try:
            self.memory = Memory.from_config(mem0_config)
            print("[Mem0 Init] ✅ Memory system initialized successfully with above configuration")

            if self.config.debug_mode:
                logger.info(f"[Mem0 Init] Successfully initialized Mem0")
                logger.info(
                    f"[Mem0 LLM Config] Using {self.config.mem0_llm_provider} with model {self.config.mem0_llm_model}"
                )
        except Exception as e:
            logger.error(f"[Mem0 Init] Failed to initialize Mem0: {e}")
            print(f"[Mem0 Init] ❌ Failed to initialize with config: {mem0_config}")
            raise RuntimeError(f"Memory system initialization failed: {e}") from e

    async def add_memory(
        self, messages: List[Dict[str, str]], user_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add a memory to the Mem0 store.

        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
            user_id: User identifier (uses config default if None)
            metadata: Additional metadata

        Returns:
            Memory ID
        """
        # Use config defaults
        user_id = user_id or self.config.mem0_user_id

        # Use provided metadata as-is (Mem0 handles user_id separately)
        if metadata is None:
            metadata = {}

        # Add memory using Mem0
        if self.config.debug_mode:
            logger.info(
                f"[Mem0 Debug] Adding memory: user_id={user_id}, messages={len(messages)} messages, metadata={metadata}"
            )

        try:
            # Support Mem0 API variants: prefer user_id, fallback to agent_id
            try:
                result = self.memory.add(messages=messages, user_id=user_id, metadata=metadata)
            except TypeError:
                # Older/newer API may use agent_id instead of user_id
                result = self.memory.add(messages=messages, agent_id=user_id, metadata=metadata)
            if self.config.debug_mode:
                logger.info(f"[Mem0 Debug] Add result type: {type(result)}, value: {result}")
        except Exception as e:
            logger.error(f"[Mem0] Add failed: {e}")
            return "error_memory_id"

        # Return the memory ID
        # Handle Mem0's response format: {'results': [{'id': '...', 'memory': '...', 'event': 'ADD'}]}
        # mem0.add() always returns {'results': [...]} where results is always a list
        results_list = result["results"]

        if len(results_list) > 0:
            # Process each result item (might include ADD, UPDATE, DELETE events)
            for item in results_list:
                event_type = item.get("event", "ADD")
                memory_id = item.get("id", "")

                # Handle potential errors in result items first
                if "error" in item:
                    logger.warning(f"[MEMORY] Error in {event_type} event for memory {memory_id}: {item['error']}")
                    continue

            # Return the ID from the first result with an ID
            first_result = results_list[0]
            return first_result.get("id", "")
        else:
            # Empty results - Mem0 decided not to save this memory
            print(f"[MEMORY] Content filtered by Mem0 (not memorable)")
            return "filtered_by_mem0"

    async def search_memories(self, query: str, user_id: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search memories using Mem0's built-in search.
        All searches are cross-session for comprehensive retrieval.

        Args:
            query: Search query
            user_id: User identifier (uses config default if None)
            limit: Maximum results

        Returns:
            List of memory dictionaries
        """
        # Use config defaults
        user_id = user_id or self.config.mem0_user_id

        if self.config.debug_mode:
            logger.info(f"[Mem0 Debug] Starting search for query: '{query[:50]}...' (user: {user_id}, limit: {limit})")

        # Search using Mem0 - this includes vectorization + semantic search
        try:
            # Support Mem0 API variants for search
            try:
                search_result = self.memory.search(query=query, user_id=user_id, limit=limit)
            except TypeError:
                search_result = self.memory.search(query=query, agent_id=user_id, limit=limit)
            # mem0.search() always returns {'results': [...]} where results is always a list
            results = search_result.get("results", [])

            if self.config.debug_mode:
                logger.info(f"[Mem0 Debug] Search completed, found {len(results)} results")

        except Exception as e:
            logger.error(f"[Mem0] Search failed: {e}")
            # Return empty list on search failure
            results = []

        return results

    async def get_relevant_memories_for_context(
        self, query_text: str, top_k: Optional[int] = None, user_id: Optional[str] = None
    ) -> List[EnhancedMemory]:
        """
        Get relevant memories for LLM context injection.

        This method retrieves and ranks memories based on relevance,
        specifically designed for automatic memory injection into LLM conversations.
        All searches are cross-session for comprehensive context retrieval.

        Args:
            query_text: Current user message for semantic search
            top_k: Maximum memories to retrieve (uses config default if None)
            user_id: User identifier (uses config default if None)

        Returns:
            List of EnhancedMemory objects with relevance scores
        """
        # Use config defaults if not provided
        top_k = top_k if top_k is not None else self.config.max_memories_to_inject
        user_id = user_id or self.config.mem0_user_id

        # Memory search is now controlled by frontend enable_memory parameter
        # This method is always active when called

        # Search memories with Mem0
        raw_memories = await self.search_memories(
            query=query_text,
            user_id=user_id,
            limit=top_k * 2,  # Get extra for filtering
        )

        # Convert to EnhancedMemory objects
        enhanced_memories = []

        for i, mem in enumerate(raw_memories):
            metadata = mem.get("metadata", {})

            # Use relevance score from Mem0
            relevance_score = mem.get("score", 0.5)

            # Create simplified EnhancedMemory
            enhanced_memory = EnhancedMemory(
                content=mem.get("memory", ""), relevance_score=relevance_score, metadata=metadata
            )

            enhanced_memories.append(enhanced_memory)

        # Sort by relevance and return top_k
        enhanced_memories.sort(key=lambda m: m.relevance_score, reverse=True)
        final_memories = enhanced_memories[:top_k]

        return final_memories

    async def get_all_memories(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all memories for a user.

        Args:
            user_id: User identifier (uses config default if None)

        Returns:
            List of all memories
        """
        # Use config defaults
        user_id = user_id or self.config.mem0_user_id

        # Get all memories from Mem0
        # Support Mem0 API variants for get_all
        try:
            all_memories_resp = self.memory.get_all(user_id=user_id)
        except TypeError:
            all_memories_resp = self.memory.get_all(agent_id=user_id)
        all_memories: List[Dict[str, Any]]
        if isinstance(all_memories_resp, dict) and "results" in all_memories_resp:
            all_memories = all_memories_resp["results"]
        else:
            # Gracefully handle older/alternative return shapes
            all_memories = all_memories_resp if isinstance(all_memories_resp, list) else []

        return all_memories

    async def delete_memory(self, memory_id: Optional[str] = None, user_id: Optional[str] = None) -> bool:
        """
        Delete memories by ID or user.

        Args:
            memory_id: Specific memory ID
            user_id: Delete all memories for user

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

            return True
        except Exception as e:
            logger.error(f"Error deleting memory: {e}")
            return False

    def _calculate_confidence(self, base_relevance: float, metadata: Dict[str, Any]) -> float:
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
