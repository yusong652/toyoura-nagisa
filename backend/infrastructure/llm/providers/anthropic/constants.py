"""
Anthropic Client Constants

This module contains all constants used by the Anthropic client.
"""

# API相关常量
ANTHROPIC_API_BASE_URL = "https://api.anthropic.com/v1"
ANTHROPIC_API_VERSION = "2023-06-01"

# 模型常量 (最新至2025年1月)
SUPPORTED_MODELS = [
    # Claude 4 系列 (最新)
    "claude-opus-4-20250514",
    "claude-sonnet-4-20250514",
    # Claude 3.7 系列
    "claude-3-7-sonnet-20250219",
    # Claude 3.5 系列
    "claude-3-5-haiku-20241022",
    # Claude 3 系列 (传统)
    "claude-3-haiku-20240307",
]

DEFAULT_MODEL = "claude-3-5-sonnet-20241022"  # 平衡性能和成本的优秀选择

# Token限制 (输入上下文窗口)
MODEL_TOKEN_LIMITS = {
    # Claude 4 系列
    "claude-opus-4-20250514": 200000,
    "claude-sonnet-4-20250514": 200000,
    # Claude 3.7 系列  
    "claude-3-7-sonnet-20250219": 200000,
    # Claude 3.5 系列
    "claude-3-5-sonnet-20241022": 200000,
    "claude-3-5-haiku-20241022": 200000,
    # Claude 3 系列
    "claude-3-haiku-20240307": 200000,
}

# 输出Token限制
MODEL_OUTPUT_LIMITS = {
    # Claude 4 系列
    "claude-opus-4-20250514": 32000,
    "claude-sonnet-4-20250514": 64000,
    # Claude 3.7 系列
    "claude-3-7-sonnet-20250219": 64000,
    # Claude 3.5 系列
    "claude-3-5-sonnet-20241022": 8192,
    "claude-3-5-haiku-20241022": 8192,
    # Claude 3 系列
    "claude-3-haiku-20240307": 4096,
}

# 模型定价 (美元/百万Token)
MODEL_PRICING = {
    # Claude 4 系列
    "claude-opus-4-20250514": {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    # Claude 3.7 系列
    "claude-3-7-sonnet-20250219": {"input": 3.00, "output": 15.00},
    # Claude 3.5 系列
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    # Claude 3 系列
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
}

# 模型特性
MODEL_FEATURES = {
    # Claude 4 系列 - 最先进的推理能力
    "claude-opus-4-20250514": {
        "description": "最强大的模型，具备高级编码能力和持续性能",
        "strengths": ["复杂推理", "高级编程", "长期任务", "工具使用"],
        "use_cases": ["复杂工程任务", "深度分析", "高级编程"]
    },
    "claude-sonnet-4-20250514": {
        "description": "混合推理模型，平衡能力和效率",
        "strengths": ["快速响应", "深度思考", "工具使用", "代理任务"],
        "use_cases": ["日常对话", "代码生成", "数据分析"]
    },
    # Claude 3.7 系列 - 混合推理先驱
    "claude-3-7-sonnet-20250219": {
        "description": "混合AI推理模型，支持快速和深度思考模式",
        "strengths": ["双模式推理", "详细分析", "逐步思考"],
        "use_cases": ["复杂分析", "教育内容", "详细解释"]
    },
    # Claude 3.5 系列 - 成熟稳定
    "claude-3-5-sonnet-20241022": {
        "description": "平衡性能和成本的优秀选择，支持计算机使用",
        "strengths": ["工具使用", "编程", "桌面环境交互"],
        "use_cases": ["代码生成", "自动化任务", "通用对话"]
    },
    "claude-3-5-haiku-20241022": {
        "description": "最快速且经济的模型，适合高频使用",
        "strengths": ["快速响应", "成本效益", "代码补全"],
        "use_cases": ["聊天机器人", "快速查询", "代码补全"]
    },
    # Claude 3 系列 - 经典版本
    "claude-3-haiku-20240307": {
        "description": "最快速的经典模型，适合简单任务",
        "strengths": ["极速响应", "低成本", "简单查询"],
        "use_cases": ["基础对话", "简单问答", "文本处理"]
    },
}

# HTTP状态码
HTTP_STATUS_OK = 200
HTTP_STATUS_BAD_REQUEST = 400
HTTP_STATUS_UNAUTHORIZED = 401
HTTP_STATUS_FORBIDDEN = 403
HTTP_STATUS_NOT_FOUND = 404
HTTP_STATUS_RATE_LIMITED = 429
HTTP_STATUS_SERVER_ERROR = 500

# 错误信息
ERROR_MESSAGES = {
    "INVALID_API_KEY": "Invalid API key provided",
    "RATE_LIMITED": "Rate limit exceeded",
    "INVALID_MODEL": "Invalid model specified",
    "TOKEN_LIMIT_EXCEEDED": "Token limit exceeded",
    "TOOL_EXECUTION_FAILED": "Tool execution failed",
    "NETWORK_ERROR": "Network connection failed",
}

# 工具调用相关
MAX_TOOL_ITERATIONS = 10
TOOL_TIMEOUT_SECONDS = 30
MAX_FUNCTION_CALLS_PER_REQUEST = 20

# 缓存设置
TOOL_CACHE_TTL_SECONDS = 3600  # 1 hour
SESSION_CACHE_TTL_SECONDS = 7200  # 2 hours