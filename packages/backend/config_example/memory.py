"""
Memory system configuration examples for toyoura-nagisa.

This file demonstrates how to configure the memory system, including:
- Feature toggles
- Performance settings  
- Mem0 integration
- LLM provider selection for memory extraction
"""

# Import the actual configuration class
from backend.config.memory import MemoryConfig


# ===== Example Configurations for Different Use Cases =====

# Example 1: Default Configuration (Balanced)
default_config = MemoryConfig(
    # Debug settings
    debug_mode=False,  # Quiet operation (only errors)
    save_conversations=True,
    
    # Time constraints
    min_memory_age_minutes=0,  # All memories are active
    max_memory_age_days=None,  # No upper limit
    
    # Search parameters  
    max_memories_to_inject=16,
    memory_relevance_threshold=0.3,
    memory_search_timeout_ms=200,
    enable_performance_logging=True,
    
    # Mem0 settings
    mem0_user_id="default",
    mem0_collection_name="nagisa_memories",
    vector_db_path="memory_db",
    embedding_model="models/gemini-embedding-001",
    
    # LLM for memory extraction
    mem0_llm_provider="gemini",
    mem0_llm_model="gemini-2.0-flash",
    mem0_llm_temperature=0.1,
    mem0_llm_max_tokens=500,
    
    # Multimodal support
    mem0_enable_vision=True,
    mem0_vision_details="high",
    
    # Custom prompts and provider settings
    use_custom_prompts=False,
    mem0_gemini_safety_block_none=True,
    mem0_openai_seed=42,
    show_memory_in_response=False,
)

# Example 2: High Performance Mode (minimal latency)
high_performance_config = MemoryConfig(
    debug_mode=False,  # No debug logging for speed
    save_conversations=False,  # Don't save new memories for speed
    
    # Fast search settings
    max_memories_to_inject=5,  # Fewer memories = faster
    memory_relevance_threshold=0.5,  # Stricter filtering
    memory_search_timeout_ms=100,  # Tight timeout
    enable_performance_logging=False,  # No logging for speed
    
    # Use fastest model
    mem0_llm_provider="gemini",
    mem0_llm_model="gemini-2.0-flash",
    mem0_llm_temperature=0.0,
    mem0_llm_max_tokens=200,  # Shorter summaries
    
    # Disable features for speed
    mem0_enable_vision=False,
    use_custom_prompts=False,
)

# Example 3: High Quality Mode (best memory extraction)
high_quality_config = MemoryConfig(
    debug_mode=False,  # Production settings
    save_conversations=True,
    
    # Quality search settings
    max_memories_to_inject=20,  # More context
    memory_relevance_threshold=0.2,  # Include more memories
    memory_search_timeout_ms=1000,  # Allow more time
    enable_performance_logging=True,
    
    # Use best quality model
    mem0_llm_provider="openai",
    mem0_llm_model="gpt-4o",
    mem0_llm_temperature=0.1,  # Slight creativity
    mem0_llm_max_tokens=800,  # More detailed summaries
    mem0_openai_seed=42,  # Reproducible results
    
    # Enable advanced features
    mem0_enable_vision=True,
    mem0_vision_details="high",
    use_custom_prompts=True,  # Use custom prompts for better extraction
)

# Example 4: OpenAI Configuration
openai_config = MemoryConfig(
    debug_mode=False,
    save_conversations=True,
    
    # OpenAI LLM settings
    mem0_llm_provider="openai",
    mem0_llm_model="gpt-4o-mini",  # Cost-effective option
    mem0_llm_temperature=0.0,
    mem0_llm_max_tokens=500,
    mem0_openai_seed=42,
    
    # Standard multimodal support
    mem0_enable_vision=True,
    mem0_vision_details="auto",
)

# Example 5: Anthropic Configuration
anthropic_config = MemoryConfig(
    debug_mode=False,
    save_conversations=True,
    
    # Anthropic LLM settings
    mem0_llm_provider="anthropic",
    mem0_llm_model="claude-3-haiku-20240307",  # Fast and efficient
    mem0_llm_temperature=0.0,
    mem0_llm_max_tokens=500,
    
    # Standard multimodal support
    mem0_enable_vision=True,
    mem0_vision_details="auto",
)

# Example 6: Development/Debug Mode
debug_config = MemoryConfig(
    debug_mode=True,  # Enable detailed debug logging
    save_conversations=True,
    
    # Debug-friendly settings
    show_memory_in_response=True,  # See what memories were used
    enable_performance_logging=True,
    memory_search_timeout_ms=2000,  # Generous timeout for debugging
    
    # Age filtering for testing
    min_memory_age_minutes=0,  # Include all memories
    max_memory_age_days=7,  # Only last week for testing
    
    # Use reliable model for debugging
    mem0_llm_provider="gemini",
    mem0_llm_model="gemini-2.0-flash",
    mem0_llm_temperature=0.0,
    
    # Test custom prompts
    use_custom_prompts=True,
)

# Example 7: Memory Minimal (for testing)
minimal_config = MemoryConfig(
    debug_mode=False,  # No debug output
    save_conversations=False,  # Don't save new memories
    
    # Minimal settings
    max_memories_to_inject=1,
    memory_relevance_threshold=0.8,  # Very strict
    memory_search_timeout_ms=50,  # Very fast
    enable_performance_logging=False,
    
    # Basic model
    mem0_llm_model="gemini-2.0-flash",
    mem0_enable_vision=False,
    use_custom_prompts=False,
)


# ===== Environment Variables Configuration =====
"""
You can also configure via environment variables in .env file:

# Basic settings
MEMORY_DEBUG_MODE=false
MEMORY_SAVE_CONVERSATIONS=true

# Time constraints
MEMORY_MIN_MEMORY_AGE_MINUTES=0
MEMORY_MAX_MEMORY_AGE_DAYS=

# Mem0 settings
MEMORY_MEM0_USER_ID=default
MEMORY_MEM0_COLLECTION_NAME=nagisa_memories
MEMORY_VECTOR_DB_PATH=memory_db
MEMORY_EMBEDDING_MODEL=models/gemini-embedding-001

# LLM configuration
MEMORY_MEM0_LLM_PROVIDER=gemini
MEMORY_MEM0_LLM_MODEL=gemini-2.0-flash
MEMORY_MEM0_LLM_TEMPERATURE=0.1
MEMORY_MEM0_LLM_MAX_TOKENS=500

# Multimodal support
MEMORY_MEM0_ENABLE_VISION=true
MEMORY_MEM0_VISION_DETAILS=high

# Search parameters
MEMORY_MAX_MEMORIES_TO_INJECT=16
MEMORY_MEMORY_RELEVANCE_THRESHOLD=0.3

# Performance
MEMORY_MEMORY_SEARCH_TIMEOUT_MS=200
MEMORY_ENABLE_PERFORMANCE_LOGGING=true

# Debug and display
MEMORY_SHOW_MEMORY_IN_RESPONSE=false

# Custom prompts
MEMORY_USE_CUSTOM_PROMPTS=false

# Provider-specific settings
MEMORY_MEM0_GEMINI_SAFETY_BLOCK_NONE=true
MEMORY_MEM0_OPENAI_SEED=42

# Custom prompts (these override markdown files if set)
MEMORY_CUSTOM_FACT_EXTRACTION_PROMPT="Extract customer support information, order details..."
MEMORY_CUSTOM_UPDATE_MEMORY_PROMPT="You are a smart memory manager which controls..."

# API Keys (required based on provider)
GOOGLE_API_KEY=your_google_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
"""


# ===== Model Comparison Guide =====
"""
LLM Provider Recommendations for Memory Extraction:

1. **Gemini 2.0 Flash** (gemini-2.0-flash)
   - ✅ Fast and cheap (~$0.075 per 1M tokens)
   - ✅ Good for general conversations
   - ✅ Excellent multimodal support
   - ✅ Latest Gemini model
   - ❌ May miss very nuanced details

2. **GPT-4o mini** (gpt-4o-mini)  
   - ✅ Good balance of quality and cost
   - ✅ Reliable memory extraction
   - ✅ Better at nuanced understanding
   - ❌ More expensive than Gemini

3. **GPT-4o** (gpt-4o)
   - ✅ Best quality memory extraction
   - ✅ Excellent at identifying important details
   - ✅ Great for complex conversations
   - ❌ Most expensive option

4. **Claude Haiku** (claude-3-haiku-20240307)
   - ✅ Good for structured information
   - ✅ Fast processing
   - ✅ Good privacy practices
   - ❌ May be overly conservative

Configuration Tips:
- Use temperature=0.0 for consistent memory extraction
- Set max_tokens=500 for balanced summaries
- Enable safety blocking only if needed
- Use seed values for reproducible results (OpenAI)
- Set debug_mode=True to see injected and embedded memory details
"""


# ===== What Gets Remembered =====
"""
Mem0 with LLM assistance typically remembers:

✅ WILL BE REMEMBERED:
- User preferences ("I like coffee")
- Personal information ("I'm a software engineer")
- Important events ("I'm moving next month") 
- Relationships ("My sister lives in Tokyo")
- Skills and expertise ("I know Python")
- Goals and plans ("I want to learn guitar")

❌ USUALLY FILTERED OUT:
- Greetings and pleasantries
- Technical troubleshooting discussions  
- Meta-conversations about the system
- Temporary requests
- Generic responses
- Weather or news discussions

The LLM analyzes each conversation and decides what information
would be valuable for future interactions with the user.
"""