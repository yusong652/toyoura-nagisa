from typing import Dict, Optional, Type, Any, List
from backend.chat.base import LLMClientBase
from backend.chat.gemini import GeminiClient
from backend.config import get_llm_config, get_current_llm_type, get_llm_specific_config, get_system_prompt

# ========== SOTA架构 - Gemini专用工厂 ==========
# 移除过时的LLM客户端，专注于SOTA Gemini实现

# 注册的 LLM 客户端类型 - 仅支持 Gemini
_clients: Dict[str, Type[LLMClientBase]] = {
    "gemini": GeminiClient,
}

# 缓存的客户端实例
_instances: Dict[str, LLMClientBase] = {}

# 支持的客户端列表 - 用于错误提示
SUPPORTED_CLIENTS = ["gemini"]

def register_client(name: str, client_class: Type[LLMClientBase]) -> None:
    """
    Register a new LLM client class.
    
    Args:
        name: Unique identifier for the LLM client
        client_class: The LLM client class to register
        
    Note:
        Currently only GeminiClient is supported due to architectural requirements.
        Other clients are deprecated and removed due to incompatibility with the
        new state-machine tool calling architecture.
    """
    _clients[name] = client_class

def get_client(name: Optional[str] = None, app: Optional[Any] = None, **kwargs) -> LLMClientBase:
    """
    Get or create a Gemini LLM client instance.
    
    This factory has been optimized for the new SOTA architecture and only supports
    GeminiClient with enhanced tool calling capabilities.
    
    Args:
        name: Name of the LLM client to get. If None, uses the configured type.
              Currently only "gemini" is supported.
        app: Optional FastAPI app instance for context injection.
        **kwargs: Arguments to pass to the client constructor
        
    Returns:
        A GeminiClient instance configured for the current architecture
        
    Raises:
        ValueError: If the requested LLM client is not supported
        
    Note:
        Other LLM clients (GPT, Anthropic, Mistral, Grok) have been removed
        due to incompatibility with the new state-machine tool calling architecture.
        They relied on deprecated ResponseType enums and recursive processing logic
        that has been replaced with internal state machines.
    """
    # 如果没有指定名称，使用配置中的类型
    name = name or get_current_llm_type()
    
    # 严格验证 - 只支持 Gemini
    if name not in _clients:
        supported_list = ", ".join(SUPPORTED_CLIENTS)
        raise ValueError(
            f"❌ Unsupported LLM client: '{name}'\n"
            f"📋 Supported clients: {supported_list}\n"
            f"🚀 Reason: Other clients are incompatible with the new SOTA architecture.\n"
            f"   They used deprecated ResponseType enums and recursive logic that\n"
            f"   has been replaced with internal state-machine tool calling.\n"
            f"💡 Solution: Configure your LLM to use 'gemini' in your config file."
        )
    
    # 获取全局配置和特定 LLM 的配置
    global_config = get_llm_config()
    specific_config = get_llm_specific_config(name)
    
    # 合并配置和参数
    client_kwargs = {
        # 首先应用全局配置中的通用参数
        "system_prompt": global_config.get("system_prompt") or get_system_prompt(),
        "recent_messages_length": global_config.get("recent_messages_length", 20),
        "debug": global_config.get("debug", False),
        # 然后应用特定 LLM 的配置
        **specific_config,
        # 最后应用传入的参数，这些参数会覆盖之前的配置
        **kwargs,
        # 显式传递 app 实例
        "app": app
    }
    
    # 优化的实例管理 - 为高性能架构设计
    config_key = f"{name}:{str(sorted(client_kwargs.items()))}"
    
    # 返回现有实例或创建新实例
    if config_key in _instances:
        print(f"[FACTORY] Reusing cached {name} client instance")
        return _instances[config_key]
        
    # 创建新的Gemini客户端实例
    print(f"[FACTORY] Creating new {name} client instance with SOTA architecture")
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
    return name in _clients 