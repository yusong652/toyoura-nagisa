from typing import Dict, Optional, Type, Any, List
from backend.chat.base import LLMClientBase
from backend.chat.gemini import GeminiClient
from backend.config import get_llm_config, get_current_llm_type, get_llm_specific_config, get_system_prompt

# ========== SOTA架构 - Gemini专用工厂 ==========
# 移除过时的LLM客户端，专注于SOTA Gemini实现

# 导入本地客户端
from backend.chat.local import VLLMClient, OllamaClient
from backend.chat.local.distributed_client import create_distributed_vllm, create_distributed_ollama

# 注册的 LLM 客户端类型 - 支持 Gemini 和本地模型
_clients: Dict[str, Type[LLMClientBase]] = {
    "gemini": GeminiClient,
    "vllm": VLLMClient,
    "ollama": OllamaClient,
}

# 缓存的客户端实例
_instances: Dict[str, LLMClientBase] = {}

# 支持的客户端列表 - 用于错误提示
SUPPORTED_CLIENTS = ["gemini", "vllm", "ollama", "distributed-vllm", "distributed-ollama"]

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
    Get or create an LLM client instance.
    
    This factory supports both cloud and local model clients:
    - gemini: Google Gemini client with enhanced tool calling
    - vllm: High-performance local inference with vLLM
    - ollama: Lightweight local models with Ollama
    
    Args:
        name: Name of the LLM client to get. If None, uses the configured type.
              Supported: "gemini", "vllm", "ollama"
        app: Optional FastAPI app instance for context injection.
        **kwargs: Arguments to pass to the client constructor
        
    Returns:
        An LLM client instance configured for the current architecture
        
    Raises:
        ValueError: If the requested LLM client is not supported
        
    Note:
        Local clients (vllm, ollama) provide offline inference capabilities
        with automatic service management and health monitoring.
    """
    # 如果没有指定名称，使用配置中的类型
    name = name or get_current_llm_type()
    
    # 处理分布式客户端
    if name.startswith("distributed-"):
        return _create_distributed_client(name, **kwargs)
    
    # 验证客户端是否支持
    if name not in _clients:
        supported_list = ", ".join(SUPPORTED_CLIENTS)
        raise ValueError(
            f"❌ Unsupported LLM client: '{name}'\n"
            f"📋 Supported clients: {supported_list}\n"
            f"🚀 Available options:\n"
            f"   - gemini: Cloud-based Gemini API with tool calling\n"
            f"   - vllm: High-performance local inference server\n"
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
    elif name == "vllm":
        # vLLM specific parameters
        if "model_path" in extra_config:
            client_kwargs["model_path"] = extra_config.pop("model_path")
        if "base_url" in extra_config:
            client_kwargs["base_url"] = extra_config.pop("base_url")
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

def _create_distributed_client(name: str, **kwargs) -> LLMClientBase:
    """
    Create distributed client instance.
    
    Args:
        name: Distributed client name (e.g., "distributed-vllm")
        **kwargs: Configuration parameters
        
    Returns:
        Distributed client instance
    """
    # Import here to avoid circular dependency
    from backend.chat.local.config import get_hpc_config
    
    # Get HPC configuration from config file
    hpc_config = get_hpc_config()
    
    # Override with any provided kwargs
    hpc_config.update(kwargs.get("hpc_config", {}))
    hpc_config.update({k: v for k, v in kwargs.items() if k.startswith("hpc_") or k in ["host", "username", "ssh_key_path"]})
    
    # Map parameter names for compatibility
    hpc_host = hpc_config.get("host") or kwargs.get("hpc_host")
    ssh_user = hpc_config.get("username") or kwargs.get("ssh_user") or kwargs.get("username")
    ssh_key_path = hpc_config.get("ssh_key_path") or kwargs.get("ssh_key_path")
    
    # Check if HPC is enabled and configured
    if not hpc_config.get("enabled", False):
        logger.warning("HPC is not enabled in configuration. Set enabled=True in HPC config.")
    
    # Validate required parameters
    if not hpc_host or not ssh_user:
        raise ValueError(
            f"Missing required HPC configuration:\n"
            f"  - HPC host: {hpc_host or 'NOT SET'}\n"
            f"  - SSH user: {ssh_user or 'NOT SET'}\n"
            f"Please configure these in backend/chat/local/config.py or pass as parameters."
        )
    
    if name == "distributed-vllm":
        model_path = hpc_config.get("models", {}).get("vllm") or kwargs.get("model_path", "/shared/models/llama-7b")
        return create_distributed_vllm(
            hpc_host=hpc_host,
            ssh_user=ssh_user,
            model_path=model_path,
            ssh_key_path=ssh_key_path,
            session_hours=hpc_config.get("session_duration_hours", 8),
            base_port=hpc_config.get("tunnel_ports", {}).get("vllm", 8000),
            local_base_port=hpc_config.get("tunnel_ports", {}).get("local_base", 8000),
            **{k: v for k, v in kwargs.items() if k not in ["hpc_host", "ssh_user", "ssh_key_path", "model_path"]}
        )
    elif name == "distributed-ollama":
        model_name = hpc_config.get("models", {}).get("ollama") or kwargs.get("model_name", "llama3.2:3b")
        return create_distributed_ollama(
            hpc_host=hpc_host,
            ssh_user=ssh_user,
            model_name=model_name,
            ssh_key_path=ssh_key_path,
            session_hours=hpc_config.get("session_duration_hours", 8),
            base_port=hpc_config.get("tunnel_ports", {}).get("ollama", 11434),
            local_base_port=hpc_config.get("tunnel_ports", {}).get("local_base", 8000),
            **{k: v for k, v in kwargs.items() if k not in ["hpc_host", "ssh_user", "ssh_key_path", "model_name"]}
        )
    else:
        raise ValueError(f"Unknown distributed client: {name}") 