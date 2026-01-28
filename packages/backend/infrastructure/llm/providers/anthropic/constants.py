"""
Anthropic Client Constants

This module contains all constants used by the Anthropic client.
"""

# API Related Constants
ANTHROPIC_API_BASE_URL = "https://api.anthropic.com/v1"
ANTHROPIC_API_VERSION = "2023-06-01"

# Model Constants (Latest as of Jan 2025)
SUPPORTED_MODELS = [
    # Claude 4 Series (Latest)
    "claude-opus-4-20250514",
    "claude-sonnet-4-20250514",
    # Claude 3.7 Series
    "claude-3-7-sonnet-20250219",
    # Claude 3.5 Series
    "claude-3-5-haiku-20241022",
    # Claude 3 Series (Legacy)
    "claude-3-haiku-20240307",
]

DEFAULT_MODEL = "claude-3-5-sonnet-20241022"  # Excellent choice balancing performance and cost

# Token Limits (Input context window)
MODEL_TOKEN_LIMITS = {
    # Claude 4 Series
    "claude-opus-4-20250514": 200000,
    "claude-sonnet-4-20250514": 200000,
    # Claude 3.7 Series  
    "claude-3-7-sonnet-20250219": 200000,
    # Claude 3.5 Series
    "claude-3-5-sonnet-20241022": 200000,
    "claude-3-5-haiku-20241022": 200000,
    # Claude 3 Series
    "claude-3-haiku-20240307": 200000,
}

# Output Token Limits
MODEL_OUTPUT_LIMITS = {
    # Claude 4 Series
    "claude-opus-4-20250514": 32000,
    "claude-sonnet-4-20250514": 64000,
    # Claude 3.7 Series
    "claude-3-7-sonnet-20250219": 64000,
    # Claude 3.5 Series
    "claude-3-5-sonnet-20241022": 8192,
    "claude-3-5-haiku-20241022": 8192,
    # Claude 3 Series
    "claude-3-haiku-20240307": 4096,
}

# Model Pricing (USD per million tokens)
MODEL_PRICING = {
    # Claude 4 Series
    "claude-opus-4-20250514": {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    # Claude 3.7 Series
    "claude-3-7-sonnet-20250219": {"input": 3.00, "output": 15.00},
    # Claude 3.5 Series
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    # Claude 3 Series
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
}

# Model Features
MODEL_FEATURES = {
    # Claude 4 Series - Advanced reasoning capabilities
    "claude-opus-4-20250514": {
        "description": "Most powerful model with advanced coding capabilities and sustained performance",
        "strengths": ["Complex reasoning", "Advanced programming", "Long-term tasks", "Tool use"],
        "use_cases": ["Complex engineering tasks", "In-depth analysis", "Advanced programming"]
    },
    "claude-sonnet-4-20250514": {
        "description": "Hybrid reasoning model balancing capability and efficiency",
        "strengths": ["Fast response", "Deep thinking", "Tool use", "Agentic tasks"],
        "use_cases": ["Daily conversation", "Code generation", "Data analysis"]
    },
    # Claude 3.7 Series - Hybrid reasoning pioneer
    "claude-3-7-sonnet-20250219": {
        "description": "Hybrid AI reasoning model supporting both fast and deep thinking modes",
        "strengths": ["Dual-mode reasoning", "Detailed analysis", "Step-by-step thinking"],
        "use_cases": ["Complex analysis", "Educational content", "Detailed explanations"]
    },
    # Claude 3.5 Series - Mature and stable
    "claude-3-5-sonnet-20241022": {
        "description": "Excellent choice balancing performance and cost, supports computer use",
        "strengths": ["Tool use", "Programming", "Desktop environment interaction"],
        "use_cases": ["Code generation", "Automation tasks", "General conversation"]
    },
    "claude-3-5-haiku-20241022": {
        "description": "Fastest and most economical model, suitable for high-frequency use",
        "strengths": ["Fast response", "Cost-effectiveness", "Code completion"],
        "use_cases": ["Chatbots", "Quick queries", "Code completion"]
    },
    # Claude 3 Series - Classic versions
    "claude-3-haiku-20240307": {
        "description": "Fastest classic model, suitable for simple tasks",
        "strengths": ["Ultrafast response", "Low cost", "Simple queries"],
        "use_cases": ["Basic conversation", "Simple Q&A", "Text processing"]
    },
}

# HTTP Status Codes
HTTP_STATUS_OK = 200
HTTP_STATUS_BAD_REQUEST = 400
HTTP_STATUS_UNAUTHORIZED = 401
HTTP_STATUS_FORBIDDEN = 403
HTTP_STATUS_NOT_FOUND = 404
HTTP_STATUS_RATE_LIMITED = 429
HTTP_STATUS_SERVER_ERROR = 500

# Error Messages
ERROR_MESSAGES = {
    "INVALID_API_KEY": "Invalid API key provided",
    "RATE_LIMITED": "Rate limit exceeded",
    "INVALID_MODEL": "Invalid model specified",
    "TOKEN_LIMIT_EXCEEDED": "Token limit exceeded",
    "TOOL_EXECUTION_FAILED": "Tool execution failed",
    "NETWORK_ERROR": "Network connection failed",
}

# Tool Execution Constants
MAX_TOOL_ITERATIONS = 10
TOOL_TIMEOUT_SECONDS = 30
MAX_FUNCTION_CALLS_PER_REQUEST = 20

# Cache Settings
TOOL_CACHE_TTL_SECONDS = 3600  # 1 hour
SESSION_CACHE_TTL_SECONDS = 7200  # 2 hours
