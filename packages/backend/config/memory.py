"""
Memory system configuration module.

Controls memory feature toggles, time limits, and Mem0 integration settings.
"""
from __future__ import annotations
from typing import Optional, Dict, Any
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MemoryConfig(BaseSettings):
    """Memory system configuration for aiNagisa."""
    
    # Debug settings
    debug_mode: bool = Field(
        default=True,
        description="Enable detailed debug logging for memory system."
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
        default=128,
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
        default="default",
        description="Default user ID for Mem0 memory storage. Can be overridden per session."
    )
    
    def model_post_init(self, __context):
        """Debug config loading."""
        print(f"[CONFIG DEBUG] MemoryConfig created with mem0_user_id: {self.mem0_user_id}")
    
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
        default="models/gemini-embedding-001",
        description="Google Gemini embedding model for memory vectorization."
    )
    
    # Mem0 LLM settings for memory extraction
    mem0_llm_provider: str = Field(
        default="gemini",
        description="LLM provider for memory extraction (gemini, openai, anthropic)."
    )
    
    @staticmethod
    def _get_llm_model() -> str:
        """Get the current LLM model from config/llm."""
        from backend.config.llm import get_llm_settings
        llm_settings = get_llm_settings()
        current_config = llm_settings.get_current_llm_config()
        return current_config.model

    mem0_llm_model: str = Field(
        default_factory=lambda: MemoryConfig._get_llm_model(),
        description="LLM model for analyzing and extracting memories. Automatically uses the same model as config/llm."
    )
    
    mem0_llm_temperature: float = Field(
        default=0.1,
        description="Temperature for memory extraction LLM (0.0 = deterministic)."
    )
    
    mem0_llm_max_tokens: int = Field(
        default=800,
        description="Maximum tokens for memory extraction summaries."
    )
    
    # Multimodal support settings
    mem0_enable_vision: bool = Field(
        default=True,
        description="Enable vision capabilities for multimodal content processing."
    )
    
    mem0_vision_details: str = Field(
        default="high",
        description="Vision detail level: 'auto', 'low', or 'high'."
    )

    # Whether to override Mem0's internal prompts with local custom prompts
    use_custom_prompts: bool = Field(
        default=False,
        description="Use local custom memory extraction/update prompts instead of Mem0 defaults."
    )
    
    # Provider-specific settings (Note: safety_settings not supported by current Mem0 version)
    mem0_gemini_safety_block_none: bool = Field(
        default=True,
        description="Placeholder for Gemini safety filters (not implemented in current Mem0)."
    )
    
    mem0_openai_seed: Optional[int] = Field(
        default=42,
        description="Seed for OpenAI models to ensure consistent memory extraction."
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
    
    def should_save_memory(self) -> bool:
        """Check if conversations should be saved to memory."""
        return self.save_conversations
    
    def get_time_filter_minutes(self) -> int:
        """Get the minimum age filter in minutes for memory activation."""
        return max(0, self.min_memory_age_minutes)
    
    def get_max_age_minutes(self) -> Optional[int]:
        """Get the maximum age filter in minutes for memory consideration."""
        if self.max_memory_age_days is not None:
            return self.max_memory_age_days * 24 * 60
        return None
    
    def build_mem0_llm_config(self) -> Dict[str, Any]:
        """
        Build Mem0 LLM configuration based on current settings.

        Returns:
            Dict containing LLM provider and configuration for Mem0
        """
        import os

        provider = self.mem0_llm_provider
        base_config = {
            "provider": provider,
            "config": {
                "model": self.mem0_llm_model,
                "temperature": self.mem0_llm_temperature,
                "max_tokens": self.mem0_llm_max_tokens,
                "enable_vision": self.mem0_enable_vision,
                "vision_details": self.mem0_vision_details,
            }
        }
        
        # Add provider-specific configurations
        if provider == "gemini":
            base_config["config"]["api_key"] = os.getenv("GOOGLE_API_KEY")
            # Note: safety_settings not supported by current Mem0 version
        elif provider == "openai":
            base_config["config"]["api_key"] = os.getenv("OPENAI_API_KEY")
            if self.mem0_openai_seed is not None:
                base_config["config"]["seed"] = self.mem0_openai_seed
        elif provider == "anthropic":
            base_config["config"]["api_key"] = os.getenv("ANTHROPIC_API_KEY")
        
        return base_config
    
    def _load_memory_extraction_prompt(self) -> str:
        """
        Load memory extraction prompt with priority: environment variable > markdown file > hardcoded.
        
        Returns:
            Memory extraction prompt text
        """
        import os
        from pathlib import Path
        
        # Priority 1: Check environment variable
        env_prompt = os.getenv("MEMORY_CUSTOM_FACT_EXTRACTION_PROMPT")
        if env_prompt:
            return env_prompt
        
        # Priority 2: Load from markdown file
        prompt_path = Path(__file__).parent / "prompts" / "memory_extraction_prompt.md"
        
        if prompt_path.exists():
            try:
                return prompt_path.read_text(encoding='utf-8')
            except Exception as e:
                print(f"[Memory Config] Failed to load prompt from {prompt_path}: {e}")
        
        # Priority 3: Fallback to hardcoded prompt
        return "Extract important information about user preferences, habits, relationships, and significant events. Technical discussions should be saved only if they represent user's knowledge or expertise areas."
    
    def _load_memory_update_prompt(self) -> str:
        """
        Load memory update prompt with priority: environment variable > markdown file > hardcoded.
        
        Returns:
            Memory update prompt text
        """
        import os
        from pathlib import Path
        
        # Priority 1: Check environment variable
        env_prompt = os.getenv("MEMORY_CUSTOM_UPDATE_MEMORY_PROMPT")
        if env_prompt:
            return env_prompt
        
        # Priority 2: Load from markdown file
        prompt_path = Path(__file__).parent / "prompts" / "memory_update_prompt.md"
        
        if prompt_path.exists():
            try:
                return prompt_path.read_text(encoding='utf-8')
            except Exception as e:
                print(f"[Memory Config] Failed to load prompt from {prompt_path}: {e}")
        
        # Priority 3: Fallback to hardcoded prompt
        return "You are a smart memory manager which controls the memory of a system. You can perform four operations: (1) add into the memory, (2) update the memory, (3) delete from the memory, and (4) no change."
    
    def build_mem0_config(self) -> Dict[str, Any]:
        """
        Build complete Mem0 configuration based on current settings.
        
        Returns:
            Complete Mem0 configuration dictionary
        """
        import os
        from pathlib import Path
        
        # Resolve vector store path to an absolute path anchored at repo root
        # This avoids accidental creation of separate DBs when CWD differs across runs
        repo_root = Path(__file__).resolve().parents[2]
        vector_store_path = str((repo_root / self.vector_db_path / "qdrant").resolve())

        # Base configuration
        config = {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": self.mem0_collection_name,
                    "path": vector_store_path,
                    "embedding_model_dims": 768,  # Google gemini-embedding-001 dimensions
                    "on_disk": True,  # Enable persistent storage to disk
                }
            },
            "embedder": {
                "provider": "gemini",
                "config": {
                    "model": self.embedding_model,
                    "api_key": os.getenv("GOOGLE_API_KEY"),
                }
            },
            "llm": self.build_mem0_llm_config(),
            "version": "v1.1",
        }

        # Only attach custom prompts when explicitly enabled to avoid JSON parsing issues
        if self.use_custom_prompts:
            config.update({
                "custom_fact_extraction_prompt": self._load_memory_extraction_prompt(),
                "custom_update_memory_prompt": self._load_memory_update_prompt(),
            })
        
        # Handle fallback for missing Google API key
        if not os.getenv("GOOGLE_API_KEY"):
            config["embedder"] = {
                "provider": "huggingface",
                "config": {
                    "model": "sentence-transformers/all-MiniLM-L6-v2"
                }
            }
        
        return config


# Example environment variables in .env file:
# MEMORY_MIN_MEMORY_AGE_MINUTES=5
# MEMORY_MAX_MEMORIES_TO_INJECT=10
# MEMORY_MEMORY_RELEVANCE_THRESHOLD=0.4
# MEMORY_DEBUG_MODE=false
# MEMORY_CUSTOM_FACT_EXTRACTION_PROMPT="Extract customer support information..."
# MEMORY_CUSTOM_UPDATE_MEMORY_PROMPT="You are a smart memory manager..."
