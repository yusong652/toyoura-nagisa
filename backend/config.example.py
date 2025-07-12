from __future__ import annotations

# 从config包中导入所有配置功能
from .config import *

# 确保所有原有的导出保持不变
__all__ = [
    # 新的配置系统
    "AppSettings",
    "get_app_settings",
    
    # 向后兼容的函数
    "get_base_prompt",
    "get_expression_prompt",
    "get_tool_prompt",
    "get_system_prompt",
    "get_llm_config",
    "get_current_llm_type",
    "get_llm_specific_config",
    "get_tts_config",
    "get_email_config",
    "get_auth_config",
    "get_text_to_image_config",
    
    # 向后兼容的变量
    "BASE_DIR",
    "CHAT_DIR",
    "TOOL_DB_PATH",
    "LOCATION_DB_PATH",
    "MEMORY_DB_PATH",
    "GOOGLE_CUSTOM_SEARCH_API_KEY",
    "GOOGLE_CUSTOM_SEARCH_ENGINE_ID",
    "LLM_CONFIG",
    "TTS_CONFIG",
    "EMAIL_CONFIG",
    "AUTH_CONFIG",
    "TEXT_TO_IMAGE_CONFIG",
] 