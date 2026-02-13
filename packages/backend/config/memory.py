"""
Memory system configuration for toyoura-nagisa.

This module defines the MemoryConfig class with all configurable settings
for the Mem0-based memory system.
"""
from __future__ import annotations
import os
from typing import Optional, Literal, Dict, Any
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MemoryConfig(BaseSettings):
    """
    Memory system configuration using Pydantic BaseSettings.

    Supports configuration via:
    - Direct instantiation with parameters
    - Environment variables with MEMORY_ prefix
    - .env file
    """

    # Debug settings
    debug_mode: bool = Field(default=False, description="Enable detailed debug logging")
    save_conversations: bool = Field(default=True, description="Save conversations to memory")

    # Time constraints
    min_memory_age_minutes: int = Field(default=0, description="Minimum age of memories to include")
    max_memory_age_days: Optional[int] = Field(default=None, description="Maximum age of memories (None = no limit)")

    # Search parameters
    max_memories_to_inject: int = Field(default=16, description="Maximum memories to inject into context")
    memory_relevance_threshold: float = Field(default=0.3, ge=0.0, le=1.0, description="Minimum relevance score")
    memory_search_timeout_ms: int = Field(default=200, description="Search timeout in milliseconds")
    enable_performance_logging: bool = Field(default=True, description="Log performance metrics")

    # Mem0 settings
    mem0_user_id: str = Field(default="default", description="Default user ID for memories")
    mem0_collection_name: str = Field(default="nagisa_memories", description="ChromaDB collection name")
    vector_db_path: str = Field(default="memory_db", description="Path to vector database")

    # Embedding configuration
    embedder_provider: Literal["openrouter", "gemini"] = Field(
        default="openrouter",
        description="Embedding provider: 'openrouter' or 'gemini'"
    )
    embedding_model: str = Field(
        default="google/gemini-embedding-001",
        description="Embedding model name"
    )
    embedding_dims: int = Field(default=768, description="Embedding dimensions")

    # LLM for memory extraction
    mem0_llm_provider: Literal["gemini", "openai", "anthropic"] = Field(
        default="gemini",
        description="LLM provider for memory extraction"
    )
    mem0_llm_model: str = Field(default="gemini-2.0-flash", description="LLM model for extraction")
    mem0_llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="LLM temperature")
    mem0_llm_max_tokens: int = Field(default=500, description="Max tokens for extraction")

    # Multimodal support
    mem0_enable_vision: bool = Field(default=True, description="Enable vision/image support")
    mem0_vision_details: Literal["auto", "low", "high"] = Field(
        default="high",
        description="Vision detail level"
    )

    # Custom prompts and provider settings
    use_custom_prompts: bool = Field(default=False, description="Use custom extraction prompts")
    mem0_gemini_safety_block_none: bool = Field(default=True, description="Disable Gemini safety blocks")
    mem0_openai_seed: Optional[int] = Field(default=42, description="OpenAI seed for reproducibility")
    show_memory_in_response: bool = Field(default=False, description="Show injected memories in response")

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        env_prefix='MEMORY_',
        extra='ignore'
    )

    def should_save_memory(self) -> bool:
        """Check if memory saving is enabled."""
        return self.save_conversations

    def build_mem0_config(self) -> Dict[str, Any]:
        """
        Build Mem0 configuration dictionary from settings.

        Returns:
            Dict containing complete Mem0 configuration
        """
        # Build embedder config based on provider
        if self.embedder_provider == "openrouter":
            embedder_config = {
                "provider": "openai",
                "config": {
                    "model": self.embedding_model,
                    "openai_base_url": "https://openrouter.ai/api/v1",
                    "api_key": os.getenv("OPENROUTER_API_KEY", ""),
                }
            }
        else:  # gemini
            embedder_config = {
                "provider": "gemini",
                "config": {
                    "model": self.embedding_model,
                    "api_key": os.getenv("GOOGLE_API_KEY", ""),
                }
            }

        # Build LLM config based on provider
        if self.mem0_llm_provider == "gemini":
            llm_config = {
                "provider": "gemini",
                "config": {
                    "model": self.mem0_llm_model,
                    "temperature": self.mem0_llm_temperature,
                    "max_tokens": self.mem0_llm_max_tokens,
                    "api_key": os.getenv("GOOGLE_API_KEY", ""),
                }
            }
            if self.mem0_gemini_safety_block_none:
                llm_config["config"]["safety_block_none"] = True
        elif self.mem0_llm_provider == "openai":
            llm_config = {
                "provider": "openai",
                "config": {
                    "model": self.mem0_llm_model,
                    "temperature": self.mem0_llm_temperature,
                    "max_tokens": self.mem0_llm_max_tokens,
                    "api_key": os.getenv("OPENAI_API_KEY", ""),
                }
            }
            if self.mem0_openai_seed is not None:
                llm_config["config"]["seed"] = self.mem0_openai_seed
        else:  # anthropic
            llm_config = {
                "provider": "anthropic",
                "config": {
                    "model": self.mem0_llm_model,
                    "temperature": self.mem0_llm_temperature,
                    "max_tokens": self.mem0_llm_max_tokens,
                    "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
                }
            }

        # Build complete config
        return {
            "embedder": embedder_config,
            "llm": llm_config,
            "vector_store": {
                "provider": "chroma",
                "config": {
                    "collection_name": self.mem0_collection_name,
                    "path": self.vector_db_path,
                    "embedding_model_dims": self.embedding_dims,
                }
            },
            "version": "v1.1"
        }


def get_memory_config() -> MemoryConfig:
    """Get memory configuration instance."""
    return MemoryConfig()
