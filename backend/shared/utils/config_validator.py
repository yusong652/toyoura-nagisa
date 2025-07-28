"""
配置验证工具模块

提供各种配置验证功能，包括LLM客户端验证等。
"""

async def validate_llm_configuration():
    """
    验证LLM配置，确保使用的是支持的客户端
    """
    try:
        from backend.infrastructure.llm.llm_factory import get_supported_clients, is_client_supported
        from backend.config.llm import get_llm_settings
        
        current_llm = get_llm_settings().provider
        supported_clients = get_supported_clients()
        
        if not is_client_supported(current_llm):
            print(f"❌ [STARTUP ERROR] Unsupported LLM client configured: '{current_llm}'")
            print(f"📋 Supported clients: {', '.join(supported_clients)}")
            print(f"💡 Please update your configuration to use one of the supported clients.")
            # 注意：这里不抛出异常，让应用启动，但在运行时会被工厂方法捕获
            
        else:
            print(f"✅ [STARTUP] LLM client '{current_llm}' is supported and ready")
            
    except Exception as e:
        print(f"⚠️  [STARTUP WARNING] Could not validate LLM configuration: {e}")