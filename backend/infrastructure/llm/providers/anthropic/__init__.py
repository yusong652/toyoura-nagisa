"""
Anthropic Claude客户端模块

该模块提供了与Anthropic Claude API的集成，采用与Gemini客户端相似的架构。
主要特性：
- 内部循环处理工具调用，避免API层递归
- MCP工具集成
- 会话隔离的工具缓存
- 统一的消息处理流程
- 模块化架构：消息格式化、响应处理、内容生成、调试工具

组件：
- AnthropicClient: 主客户端类
- MessageFormatter: 消息格式转换
- ResponseProcessor: 响应处理和解析
- ContentGenerators: 标题生成、图像提示等
- AnthropicDebugger: 调试和日志工具
- Config & Constants: 配置管理和常量定义
"""

from .client import AnthropicClient
from .message_formatter import MessageFormatter
from .response_processor import AnthropicResponseProcessor
from .content_generators import TitleGenerator, ImagePromptGenerator, AnalysisGenerator
from .debug import AnthropicDebugger
from .config import get_anthropic_config, AnthropicClientConfig
from .constants import SUPPORTED_MODELS, DEFAULT_MODEL

__all__ = [
    "AnthropicClient",
    "MessageFormatter", 
    "AnthropicResponseProcessor",
    "TitleGenerator",
    "ImagePromptGenerator",
    "AnalysisGenerator",
    "AnthropicDebugger",
    "get_anthropic_config",
    "AnthropicClientConfig",
    "SUPPORTED_MODELS",
    "DEFAULT_MODEL"
]