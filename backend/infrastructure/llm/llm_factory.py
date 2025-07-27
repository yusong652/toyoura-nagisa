import logging
from typing import Dict, Optional, Type, Any, List
from backend.infrastructure.llm.base import LLMClientBase
from backend.infrastructure.llm.gemini import GeminiClient
from backend.infrastructure.llm.local.local_llm_client import LocalLLMClient
from backend.infrastructure.llm.anthropic import AnthropicClient
from backend.infrastructure.llm.gpt import GPTClient
from backend.config import get_llm_config, get_current_llm_type, get_llm_specific_config

logger = logging.getLogger(__name__)

# ========== 多LLM客户端支持架构 ==========
# 支持多种LLM客户端：Gemini、Anthropic、GPT和本地模型


# 注册的 LLM 客户端类型
_clients: Dict[str, Type[LLMClientBase]] = {
    "gemini": GeminiClient,
    "anthropic": AnthropicClient,
    "gpt": GPTClient,
    "openai": GPTClient,  # Alias for GPT
    "local_llm": LocalLLMClient,
}

# 缓存的客户端实例
_instances: Dict[str, LLMClientBase] = {}

# 支持的客户端列表 - 用于错误提示
SUPPORTED_CLIENTS = ["gemini", "anthropic", "gpt", "local_llm"]

def register_client(name: str, client_class: Type[LLMClientBase]) -> None:
    """
    Register a new LLM client class.
    
    Args:
        name: Unique identifier for the LLM client
        client_class: The LLM client class to register
        
    Note:
        All major LLM clients are now supported with consistent MCP tool calling architecture.
        Each client implements the same LLMClientBase interface for compatibility.
    """
    _clients[name] = client_class

def get_client(name: Optional[str] = None, app: Optional[Any] = None, **kwargs) -> LLMClientBase:
    """
    Get or create an LLM client instance.
    
    This factory supports multiple cloud and local model clients:
    - gemini: Google Gemini client with enhanced tool calling
    - anthropic: Anthropic Claude client with function calling
    - gpt/openai: OpenAI GPT client with function calling
    - local_llm: Local LLM inference server
    - ollama: Lightweight local models with Ollama
    
    Args:
        name: Name of the LLM client to get. If None, uses the configured type.
              Supported: "gemini", "anthropic", "gpt", "openai", "local_llm", "ollama"
        app: Optional FastAPI app instance for context injection.
        **kwargs: Arguments to pass to the client constructor
        
    Returns:
        An LLM client instance configured for the current architecture
        
    Raises:
        ValueError: If the requested LLM client is not supported
        
    Note:
        Local clients (local_llm, ollama) provide offline inference capabilities
        with automatic service management and health monitoring.
    """
    # 如果没有指定名称，使用配置中的类型
    name = name or get_current_llm_type()
    
    # 验证客户端是否支持
    if name not in _clients:
        supported_list = ", ".join(SUPPORTED_CLIENTS)
        raise ValueError(
            f"❌ Unsupported LLM client: '{name}'\n"
            f"📋 Supported clients: {supported_list}\n"
            f"🚀 Available options:\n"
            f"   - gemini: Cloud-based Gemini API with tool calling\n"
            f"   - anthropic: Anthropic Claude with function calling\n"
            f"   - gpt/openai: OpenAI GPT with function calling\n"
            f"   - local_llm: Local LLM inference server\n"
            f"   - ollama: Lightweight local model serving\n"
            f"   - distributed-vllm: Distributed vLLM on HPC cluster\n"
            f"   - distributed-ollama: Distributed Ollama on HPC cluster\n"
            f"💡 Solution: Configure your LLM to use one of the supported clients."
        )
    
    # 获取全局配置和特定 LLM 的配置
    global_config = get_llm_config()
    specific_config = get_llm_specific_config(name)
    
    # 合并配置和参数 - 正确处理必需参数和可选参数
    extra_config = {
        "recent_messages_length": global_config.get("recent_messages_length", 20),
        "debug": global_config.get("debug", False),
        # 合并特定LLM配置
        **specific_config,
        # 合并传入的kwargs
        **kwargs
    }
    
    # 提取必需的构造函数参数（如API key）
    client_kwargs = {
        "tools_enabled": global_config.get("tools_enabled", True),
        "extra_config": {}
    }
    
    # 将特定LLM的必需参数从extra_config中提取出来
    if name == "gemini" and "api_key" in extra_config:
        client_kwargs["api_key"] = extra_config.pop("api_key")
    elif name in ["anthropic"] and "api_key" in extra_config:
        client_kwargs["api_key"] = extra_config.pop("api_key")
    elif name in ["gpt", "openai"] and "api_key" in extra_config:
        client_kwargs["api_key"] = extra_config.pop("api_key")
    elif name == "local_llm":
        # Local LLM specific parameters
        if "server_url" in extra_config:
            client_kwargs["server_url"] = extra_config.pop("server_url")
        if "api_key" in extra_config:
            client_kwargs["api_key"] = extra_config.pop("api_key")
        if "model" in extra_config:
            client_kwargs["model"] = extra_config.pop("model")
        if "timeout" in extra_config:
            client_kwargs["timeout"] = extra_config.pop("timeout")
    elif name == "ollama":
        # Ollama specific parameters
        if "model_name" in extra_config:
            client_kwargs["model_name"] = extra_config.pop("model_name")
        if "base_url" in extra_config:
            client_kwargs["base_url"] = extra_config.pop("base_url")
    
    # 将剩余配置放入extra_config
    client_kwargs["extra_config"] = extra_config
    
    # 如果app实例被传递，将其添加到extra_config中
    if app:
        client_kwargs["extra_config"]["app"] = app
    
    # 优化的实例管理 - 为高性能架构设计
    config_key = f"{name}:{str(sorted(client_kwargs.items()))}"
    
    # 返回现有实例或创建新实例
    if config_key in _instances:
        print(f"[FACTORY] Reusing cached {name} client instance")
        return _instances[config_key]
        
    # 创建新的客户端实例
    print(f"[FACTORY] Creating new {name} client instance")
    client = _clients[name](**client_kwargs)
    _instances[config_key] = client
    
    return client

def get_supported_clients() -> List[str]:
    """
    获取当前支持的LLM客户端列表
    
    Returns:
        支持的客户端名称列表
    """
    return SUPPORTED_CLIENTS.copy()

def is_client_supported(name: str) -> bool:
    """
    检查指定的LLM客户端是否受支持
    
    Args:
        name: LLM客户端名称
        
    Returns:
        True if supported, False otherwise
    """
    return name in _clients or name.startswith("distributed-")
