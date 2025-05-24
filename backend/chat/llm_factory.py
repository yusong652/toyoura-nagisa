from typing import Dict, Optional, Type
from backend.chat.base import LLMClientBase
from backend.chat.gpt import GPTClient
from backend.chat.gemini import GeminiClient
from backend.chat.mistral import MistralClient
from backend.chat.anthropic import AnthropicClient
from backend.chat.grok import GrokClient
from backend.config import get_llm_config, get_current_llm_type, get_llm_specific_config, get_system_prompt

# 注册的 LLM 客户端类型
_clients: Dict[str, Type[LLMClientBase]] = {
    "chatgpt": GPTClient,
    "gemini": GeminiClient,
    "mistral": MistralClient,
    "anthropic": AnthropicClient,
    "grok": GrokClient,
}

# 缓存的客户端实例
_instances: Dict[str, LLMClientBase] = {}

def register_client(name: str, client_class: Type[LLMClientBase]) -> None:
    """
    Register a new LLM client class.
    
    Args:
        name: Unique identifier for the LLM client
        client_class: The LLM client class to register
    """
    _clients[name] = client_class

def get_client(name: Optional[str] = None, mcp_client=None, **kwargs) -> LLMClientBase:
    """
    Get or create an LLM client instance.
    
    Args:
        name: Name of the LLM client to get. If None, uses the configured type.
        mcp_client: MCP client instance to inject (for in-process tool calls)
        **kwargs: Arguments to pass to the client constructor
        
    Returns:
        An instance of the requested LLM client
        
    Raises:
        ValueError: If the requested LLM client is not registered
    """
    # 如果没有指定名称，使用配置中的类型
    name = name or get_current_llm_type()
    
    if name not in _clients:
        raise ValueError(f"Unknown LLM client: {name}")
    
    # 获取配置
    config = get_llm_config()
    specific_config = get_llm_specific_config(name)
    
    # 合并配置和参数
    client_kwargs = {
        "system_prompt": get_system_prompt(),
        **specific_config,
        **kwargs
    }
    
    if mcp_client is not None:
        client_kwargs["mcp_client"] = mcp_client
    
    # To avoid creating multiple instances with the same configuration
    config_key = f"{name}:{str(sorted(client_kwargs.items()))}"
    
    # 返回现有实例或创建新实例
    if config_key in _instances:
        return _instances[config_key]
    # instantiation
    client = _clients[name](**client_kwargs)
    _instances[config_key] = client
    return client

def list_available_clients() -> list[str]:
    """
    Get a list of all registered LLM client names.
    
    Returns:
        List of registered LLM client names
    """
    return list(_clients.keys())

def clear_instances() -> None:
    """
    Clear all cached LLM client instances.
    """
    _instances.clear() 