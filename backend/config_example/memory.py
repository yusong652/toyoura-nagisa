"""
Memory system configuration module.

Controls memory feature toggles, time limits, and Mem0 integration settings.
"""
from __future__ import annotations
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MemoryConfig(BaseSettings):
    """Memory system configuration for aiNagisa."""
    
    # Feature toggles
    enabled: bool = Field(
        default=True, 
        description="Global toggle for memory system. When False, disables all memory features."
    )
    
    auto_inject: bool = Field(
        default=True,
        description="Automatically inject relevant memories into system prompt. When False, memory must be manually queried."
    )
    
    save_conversations: bool = Field(
        default=True,
        description="Save conversation turns to memory after each response. When False, no new memories are created."
    )
    
    # Time constraints
    min_memory_age_minutes: int = Field(
        default=0,
        description="Minimum age in minutes for memories to be activated. 0 means all memories are active. Use to exclude very recent memories."
    )
    
    max_memory_age_days: Optional[int] = Field(
        default=None,
        description="Maximum age in days for memories to be considered. None means no upper limit. Use to exclude very old memories."
    )
    
    # Search parameters
    max_memories_to_inject: int = Field(
        default=5,
        description="Maximum number of memories to inject into system prompt. Prevents context overflow."
    )
    
    memory_relevance_threshold: float = Field(
        default=0.3,
        description="Minimum relevance score (0-1) for memories to be included. Higher values = stricter filtering."
    )
    
    # Performance settings
    memory_search_timeout_ms: int = Field(
        default=200,
        description="Maximum milliseconds to wait for memory search. Prevents blocking on slow searches."
    )
    
    enable_performance_logging: bool = Field(
        default=True,
        description="Log memory system performance metrics (search time, hit rate, etc)."
    )
    
    # Mem0 specific settings
    mem0_user_id: str = Field(
        default="default_user",
        description="Default user ID for Mem0 memory storage. Can be overridden per session."
    )
    
    mem0_collection_name: str = Field(
        default="nagisa_memories",
        description="Mem0 collection name for memory storage."
    )
    
    # Vector database settings
    vector_db_path: str = Field(
        default="memory_db",
        description="Path to vector database storage directory."
    )
    
    embedding_model: str = Field(
        default="models/text-embedding-004",
        description="Google Gemini embedding model for memory vectorization."
    )
    
    # Debug settings
    debug_mode: bool = Field(
        default=False,
        description="Enable detailed debug logging for memory system."
    )
    
    show_memory_in_response: bool = Field(
        default=False,
        description="Include injected memories in response metadata for debugging."
    )
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        env_prefix='MEMORY_',
        extra='ignore'
    )
    
    def is_memory_active(self) -> bool:
        """Check if memory system should be active based on configuration."""
        return self.enabled
    
    def should_inject_memory(self) -> bool:
        """Check if memories should be automatically injected."""
        return self.enabled and self.auto_inject
    
    def should_save_memory(self) -> bool:
        """Check if conversations should be saved to memory."""
        return self.enabled and self.save_conversations
    
    def get_time_filter_minutes(self) -> int:
        """Get the minimum age filter in minutes for memory activation."""
        return max(0, self.min_memory_age_minutes)
    
    def get_max_age_minutes(self) -> Optional[int]:
        """Get the maximum age filter in minutes for memory consideration."""
        if self.max_memory_age_days is not None:
            return self.max_memory_age_days * 24 * 60
        return None


# Example environment variables in .env file:
# MEMORY_ENABLED=true
# MEMORY_AUTO_INJECT=true
# MEMORY_MIN_MEMORY_AGE_MINUTES=5
# MEMORY_MAX_MEMORIES_TO_INJECT=10
# MEMORY_MEMORY_RELEVANCE_THRESHOLD=0.4
# MEMORY_DEBUG_MODE=false