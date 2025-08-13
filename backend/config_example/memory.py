"""
Memory system configuration examples for aiNagisa.

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
    # Feature toggles
    enabled=True,
    debug_mode=False,  # Quiet operation (only errors)
    auto_inject=True,
    save_conversations=True,
    
    # Search parameters  
    max_memories_to_inject=16,
    memory_relevance_threshold=0.3,
    
    # Embedding model (latest Gemini)
    embedding_model="models/gemini-embedding-001",
    
    # LLM for memory extraction
    mem0_llm_provider="gemini",
    mem0_llm_model="gemini-1.5-flash",
    mem0_llm_temperature=0.0,
    mem0_llm_max_tokens=500,
    mem0_gemini_safety_block_none=True,
)

# Example 2: High Performance Mode (minimal latency)
high_performance_config = MemoryConfig(
    enabled=True,
    debug_mode=False,  # No debug logging for speed
    auto_inject=True,
    save_conversations=False,  # Don't save new memories for speed
    max_memories_to_inject=5,  # Fewer memories = faster
    memory_relevance_threshold=0.5,  # Stricter filtering
    memory_search_timeout_ms=100,  # Tight timeout
    
    # Use fastest model
    mem0_llm_provider="gemini",
    mem0_llm_model="gemini-1.5-flash",
    mem0_llm_temperature=0.0,
    mem0_llm_max_tokens=200,  # Shorter summaries
)

# Example 3: High Quality Mode (best memory extraction)
high_quality_config = MemoryConfig(
    enabled=True,
    debug_mode=False,  # Production settings
    auto_inject=True,
    save_conversations=True,
    max_memories_to_inject=20,  # More context
    memory_relevance_threshold=0.2,  # Include more memories
    memory_search_timeout_ms=1000,  # Allow more time
    
    # Use best quality model
    mem0_llm_provider="openai",
    mem0_llm_model="gpt-4o",
    mem0_llm_temperature=0.1,  # Slight creativity
    mem0_llm_max_tokens=800,  # More detailed summaries
    mem0_openai_seed=42,  # Reproducible results
)

# Example 4: OpenAI Configuration
openai_config = MemoryConfig(
    enabled=True,
    debug_mode=False,
    auto_inject=True,
    save_conversations=True,
    
    # OpenAI LLM settings
    mem0_llm_provider="openai",
    mem0_llm_model="gpt-4o-mini",  # Cost-effective option
    mem0_llm_temperature=0.0,
    mem0_llm_max_tokens=500,
    mem0_openai_seed=42,
)

# Example 5: Anthropic Configuration
anthropic_config = MemoryConfig(
    enabled=True,
    debug_mode=False,
    auto_inject=True,
    save_conversations=True,
    
    # Anthropic LLM settings
    mem0_llm_provider="anthropic",
    mem0_llm_model="claude-3-haiku-20240307",  # Fast and efficient
    mem0_llm_temperature=0.0,
    mem0_llm_max_tokens=500,
)

# Example 6: Development/Debug Mode
debug_config = MemoryConfig(
    enabled=True,
    debug_mode=True,  # Enable detailed debug logging (injected/embedded memory info)
    auto_inject=True,
    save_conversations=True,
    show_memory_in_response=True,  # See what memories were used
    enable_performance_logging=True,
    memory_search_timeout_ms=2000,  # Generous timeout for debugging
    
    # Use reliable model for debugging
    mem0_llm_provider="gemini",
    mem0_llm_model="gemini-1.5-flash",
    mem0_llm_temperature=0.0,
)

# Example 7: Memory Disabled (for testing)
disabled_config = MemoryConfig(
    enabled=False,  # Turn off all memory functionality
    debug_mode=False,  # No debug output when disabled
)


# ===== Environment Variables Configuration =====
"""
You can also configure via environment variables in .env file:

# Basic settings
MEMORY_ENABLED=true
MEMORY_DEBUG_MODE=false
MEMORY_AUTO_INJECT=true
MEMORY_SAVE_CONVERSATIONS=true

# LLM configuration
MEMORY_MEM0_LLM_PROVIDER=gemini
MEMORY_MEM0_LLM_MODEL=gemini-1.5-flash
MEMORY_MEM0_LLM_TEMPERATURE=0.0
MEMORY_MEM0_LLM_MAX_TOKENS=500

# Search parameters
MEMORY_MAX_MEMORIES_TO_INJECT=16
MEMORY_MEMORY_RELEVANCE_THRESHOLD=0.3

# Performance
MEMORY_MEMORY_SEARCH_TIMEOUT_MS=500

# Debug (debug_mode moved to basic settings above)
MEMORY_SHOW_MEMORY_IN_RESPONSE=false

# API Keys (required based on provider)
GOOGLE_API_KEY=your_google_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
"""


# ===== Model Comparison Guide =====
"""
LLM Provider Recommendations for Memory Extraction:

1. **Gemini Flash** (gemini-1.5-flash)
   - ✅ Fast and cheap (~$0.075 per 1M tokens)
   - ✅ Good for general conversations
   - ✅ Excellent for most use cases
   - ❌ May miss nuanced details

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