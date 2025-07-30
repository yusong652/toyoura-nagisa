import logging
from typing import Dict, Optional, Type, Any, List
from backend.infrastructure.llm.base import LLMClientBase
from backend.infrastructure.llm.providers.gemini import GeminiClient
from backend.infrastructure.llm.providers.anthropic import AnthropicClient
from backend.infrastructure.llm.providers.openai import OpenAIClient
from backend.infrastructure.llm.providers.local.local_llm_client import LocalLLMClient
from backend.config import get_llm_settings

logger = logging.getLogger(__name__)

# ========== 多LLM客户端支持架构 ==========
# 支持多种LLM客户端：Gemini、Anthropic、GPT和本地模型


# 注册的 LLM 客户端类型
_clients: Dict[str, Type[LLMClientBase]] = {
    "gemini": GeminiClient,
    "anthropic": AnthropicClient,
    "gpt": OpenAIClient,
    "openai": OpenAIClient,  # Alias for GPT
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
    # 获取LLM配置
    llm_settings = get_llm_settings()
    
    # 如果没有指定名称，使用配置中的类型
    name = name or llm_settings.provider
    
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
    
    # 准备客户端配置
    client_kwargs = {
        "tools_enabled": getattr(llm_settings, 'tools_enabled', True),
        "extra_config": kwargs  # 直接传递额外的kwargs
    }
    
    # 根据LLM类型获取特定配置和API key
    if name == "gemini":
        gemini_config = llm_settings.get_gemini_config()
        client_kwargs["api_key"] = gemini_config.google_api_key
        client_kwargs["extra_config"].update({
            "model": gemini_config.model,
            "temperature": gemini_config.temperature,
            "top_p": gemini_config.top_p,
            "top_k": gemini_config.top_k,
            "max_output_tokens": gemini_config.max_output_tokens,
            "web_search_max_uses": gemini_config.web_search_max_uses,
            "debug": llm_settings.debug,
        })
    elif name == "anthropic":
        anthropic_config = llm_settings.get_anthropic_config()
        client_kwargs["api_key"] = anthropic_config.anthropic_api_key
        client_kwargs["extra_config"].update({
            "model": anthropic_config.model,
            "temperature": anthropic_config.temperature,
            "max_tokens": anthropic_config.max_tokens,
            "top_p": anthropic_config.top_p,
            "top_k": anthropic_config.top_k,
            "web_search_max_uses": anthropic_config.web_search_max_uses,
            "debug": llm_settings.debug,
        })
    elif name in ["gpt", "openai"]:
        gpt_config = llm_settings.get_gpt_config()
        client_kwargs["api_key"] = gpt_config.openai_api_key
        client_kwargs["extra_config"].update({
            "model": gpt_config.model,
            "temperature": gpt_config.temperature,
            "top_p": gpt_config.top_p,
            "top_k": gpt_config.top_k,
            "max_tokens": gpt_config.max_tokens,
        })
    elif name == "local_llm":
        local_llm_config = llm_settings.get_local_llm_config()
        client_kwargs.update({
            "server_url": local_llm_config.server_url,
            "api_key": local_llm_config.api_key,
            "model": local_llm_config.model,
            "timeout": local_llm_config.timeout,
        })
        client_kwargs["extra_config"].update({
            "temperature": local_llm_config.temperature,
            "top_p": local_llm_config.top_p,
            "max_tokens": local_llm_config.max_tokens,
        })
    elif name == "ollama":
        # Ollama使用local_llm配置
        local_llm_config = llm_settings.get_local_llm_config()
        client_kwargs.update({
            "model_name": local_llm_config.model,
            "base_url": local_llm_config.server_url,
        })
    
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
