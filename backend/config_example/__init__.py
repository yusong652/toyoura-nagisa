"""
配置系统主入口
提供统一的配置接口和向后兼容性
"""
from __future__ import annotations
import os
from typing import Dict, Any
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .base import BaseConfig
from .llm import LLMSettings, get_llm_settings
from .tts import TTSSettings, get_tts_settings
from .email import EmailConfig, AuthConfig, SearchConfig, get_email_config, get_auth_config, get_search_config
from .text_to_image import TextToImageSettings, get_text_to_image_settings


class AppSettings(BaseSettings):
    """应用总配置"""
    
    # 环境配置
    environment: str = Field(default="development", description="运行环境")
    
    # 基础配置
    base: BaseConfig = Field(default_factory=BaseConfig, description="基础配置")
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        env_prefix='APP_',
        extra='ignore'
    )
    
    def get_llm_settings(self) -> LLMSettings:
        """获取LLM配置"""
        return get_llm_settings()
    
    def get_tts_settings(self) -> TTSSettings:
        """获取TTS配置"""
        return get_tts_settings()
    
    def get_email_config(self) -> EmailConfig:
        """获取邮件配置"""
        return get_email_config()
    
    def get_auth_config(self) -> AuthConfig:
        """获取认证配置"""
        return get_auth_config()
    
    def get_search_config(self) -> SearchConfig:
        """获取搜索配置"""
        return get_search_config()
    
    def get_text_to_image_settings(self) -> TextToImageSettings:
        """获取文本转图像配置"""
        return get_text_to_image_settings()


# 全局配置实例 - 每次重新创建以确保最新配置
def get_app_settings() -> AppSettings:
    """获取应用配置实例 - 每次重新创建以确保最新配置"""
    return AppSettings()


# -----------------------------------------------------------------------------
# 向后兼容性接口
# -----------------------------------------------------------------------------

# 路径配置
def get_base_config() -> BaseConfig:
    """获取基础配置"""
    return get_app_settings().base


# 基础路径
BASE_DIR = Path(__file__).parent.parent
CHAT_DIR = BASE_DIR / "chat"
TOOL_DB_PATH = BASE_DIR / "tool_db"
LOCATION_DB_PATH = BASE_DIR / "location_data"
MEMORY_DB_PATH = BASE_DIR / "memory_db"


# 提示词加载函数
def _load_prompt_file(filename: str) -> str:
    """从 chat 目录加载指定的提示文件"""
    prompt_path = CHAT_DIR / filename
    try:
        return prompt_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def get_base_prompt() -> str:
    """
    加载基础系统提示。
    优先从环境变量 `NAGISA_BASE_PROMPT` 加载。
    如果环境变量未设置，则回退到从 `base_prompt.md` 文件加载。
    """
    base_prompt_from_env = os.getenv("NAGISA_BASE_PROMPT")
    if base_prompt_from_env is not None:
        return base_prompt_from_env.strip()
    
    return _load_prompt_file("base_prompt.md")


def get_expression_prompt() -> str:
    """加载表情/关键词指令提示"""
    return _load_prompt_file("expression_prompt.md")


def get_tool_prompt() -> str:
    """加载工具使用指南提示"""
    return _load_prompt_file("tool_prompt.md")


def get_system_prompt(tools_enabled: bool = True) -> str:
    """
    获取完整的系统提示词。

    根据 `tools_enabled` 标志，动态地组合不同的提示词模块。
    """
    base = get_base_prompt()
    expression = get_expression_prompt()
    
    components = [base]
    
    if tools_enabled:
        tool_prompt = get_tool_prompt()
        if tool_prompt:
            components.append(tool_prompt)
            
    components.append(expression)

    # 使用分隔符将所有部分连接起来，同时过滤掉空字符串
    full_prompt = "\n\n---\n\n".join(filter(None, components))
    return full_prompt


# 向后兼容的配置字典 - 真正的Fail Fast实现
def get_llm_config() -> Dict[str, Any]:
    """
    获取 LLM 配置（向后兼容）
    
    注意：这个函数会实现真正的Fail Fast机制
    如果当前LLM的API密钥未正确配置，会立即抛出错误
    """
    settings = get_app_settings().get_llm_settings()
    
    # 构建向后兼容的配置字典
    config = {
        "type": settings.type,
        "debug": settings.debug,
        "chatgpt": {},
        "gemini": {},
        "anthropic": {}
    }
    
    # 只有当前使用的LLM才包含完整配置，并且会触发验证
    if settings.type == "chatgpt":
        chatgpt_config = settings.get_chatgpt_config()  # 这里会触发fail fast验证
        config["chatgpt"] = {
            "api_key": chatgpt_config.openai_api_key,
            "model": chatgpt_config.model,
            "temperature": chatgpt_config.temperature,
            "top_p": chatgpt_config.top_p,
            "top_k": chatgpt_config.top_k,
            "max_tokens": chatgpt_config.max_tokens,
        }
    elif settings.type == "gemini":
        gemini_config = settings.get_gemini_config()  # 这里会触发fail fast验证
        config["gemini"] = {
            "api_key": gemini_config.google_api_key,
            "model": gemini_config.model,
            "temperature": gemini_config.temperature,
            "top_p": gemini_config.top_p,
            "top_k": gemini_config.top_k,
            "maxOutputTokens": gemini_config.max_output_tokens,
        }
    elif settings.type == "anthropic":
        anthropic_config = settings.get_anthropic_config()  # 这里会触发fail fast验证
        config["anthropic"] = {
            "api_key": anthropic_config.anthropic_api_key,
            "model": anthropic_config.model,
            "temperature": anthropic_config.temperature,
            "max_tokens": anthropic_config.max_tokens,
            "top_p": anthropic_config.top_p,
            "top_k": anthropic_config.top_k,
        }
    
    return config


def get_current_llm_type() -> str:
    """获取当前使用的 LLM 类型"""
    return get_app_settings().get_llm_settings().type


def get_llm_specific_config(llm_type: str = None) -> Dict[str, Any]:
    """获取特定 LLM 的配置"""
    llm_type = llm_type or get_current_llm_type()
    llm_config = get_llm_config()
    return llm_config.get(llm_type, {})


def get_tts_config() -> Dict[str, Any]:
    """获取 TTS 配置（向后兼容）"""
    settings = get_app_settings().get_tts_settings()
    
    config = {
        "type": settings.type,
        "fish_audio": {},
        "gpt_sovits": {}
    }
    
    if settings.type == "fish_audio":
        fish_config = settings.get_fish_audio_config()  # 可能会触发fail fast验证
        config["fish_audio"] = {
            "api_key": fish_config.fish_audio_api_key,
            "reference_id": fish_config.fish_audio_reference_id,
        }
    elif settings.type == "gpt_sovits":
        gpt_config = settings.get_gpt_sovits_config()
        config["gpt_sovits"] = {
            "server_url": gpt_config.server_url,
            "text_lang": gpt_config.text_lang,
            "speed": gpt_config.speed,
            "ref_audio_path": gpt_config.ref_audio_path,
            "prompt_lang": gpt_config.prompt_lang,
            "prompt_text": gpt_config.prompt_text,
            "cut_punc": gpt_config.cut_punc,
            "top_k": gpt_config.top_k,
            "top_p": gpt_config.top_p,
            "temperature": gpt_config.temperature,
            "inp_refs": gpt_config.inp_refs,
        }
    
    return config


def get_email_config() -> Dict[str, Any]:
    """获取邮件配置（向后兼容）"""
    config = get_app_settings().get_email_config()  # 可能会触发fail fast验证
    return {
        "smtp_server": config.smtp_server,
        "smtp_port": config.smtp_port,
        "username": config.username,
        "password": config.password,
        "use_tls": config.use_tls,
        "sender_name": config.sender_name,
        "imap_server": config.imap_server,
        "imap_port": config.imap_port,
    }


def get_auth_config() -> Dict[str, Any]:
    """获取认证配置（向后兼容）"""
    config = get_app_settings().get_auth_config()  # 可能会触发fail fast验证
    return {
        "client_id": config.client_id,
        "client_secret": config.client_secret,
    }


def get_text_to_image_config() -> Dict[str, Any]:
    """获取文本转图像配置（向后兼容）"""
    settings = get_app_settings().get_text_to_image_settings()
    
    config = {
        "type": settings.provider,
        "system_prompt": settings.text_to_image_system_prompt,
        "context_message_count": settings.context_message_count,
        "default_positive_prompt": settings.default_positive_prompt,
        "default_negative_prompt": settings.default_negative_prompt,
        "debug": settings.enable_debug,
        "models_lab": {},
        "stable_diffusion_webui": {}
    }
    
    if settings.provider == "models_lab":
        models_lab_config = settings.get_models_lab_config()  # 可能会触发fail fast验证
        config["models_lab"] = {
            "key": models_lab_config.models_lab_api_key,
            "model_id": models_lab_config.model_id,
            "width": models_lab_config.width,
            "height": models_lab_config.height,
            "samples": models_lab_config.samples,
            "num_inference_steps": models_lab_config.num_inference_steps,
            "safety_checker": models_lab_config.safety_checker,
            "enhance_prompt": models_lab_config.enhance_prompt,
            "guidance_scale": models_lab_config.guidance_scale,
            "scheduler": models_lab_config.scheduler,
        }
    elif settings.provider == "stable_diffusion_webui":
        sd_config = settings.get_stable_diffusion_webui_config()
        config["stable_diffusion_webui"] = {
            "server_url": sd_config.server_url,
            "steps": sd_config.steps,
            "sampler_name": sd_config.sampler_name,
            "cfg_scale": sd_config.cfg_scale,
            "seed": sd_config.seed,
            "enable_hr": sd_config.enable_hr,
            "hr_scale": sd_config.hr_scale,
            "hr_upscaler": sd_config.hr_upscaler,
            "denoising_strength": sd_config.denoising_strength,
            "model_type": sd_config.model_type,
            "debug": sd_config.debug,
            "model_presets": sd_config.model_presets,
        }
    
    return config


# 向后兼容的全局变量
GOOGLE_CUSTOM_SEARCH_API_KEY = ""
GOOGLE_CUSTOM_SEARCH_ENGINE_ID = ""

try:
    search_config = get_app_settings().get_search_config()
    GOOGLE_CUSTOM_SEARCH_API_KEY = search_config.google_api_key
    GOOGLE_CUSTOM_SEARCH_ENGINE_ID = search_config.google_search_engine_id
except:
    # 搜索配置是可选的，失败时保持空字符串
    pass


# 注意：为了避免模块导入时触发fail fast，移除了全局配置变量
# 请直接使用配置获取函数：get_llm_config(), get_tts_config(), get_email_config() 等


# 导出配置获取函数
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
    
    # 注意：移除了 LLM_CONFIG, TTS_CONFIG 等全局变量
    # 请使用对应的函数：get_llm_config(), get_tts_config() 等
] 