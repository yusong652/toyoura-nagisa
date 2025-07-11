"""
配置文件示例，用于管理应用的各种配置项。
请复制此文件为 config.py 并填入您的实际配置。
"""
from __future__ import annotations
import os
from functools import lru_cache
from typing import Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 基础配置
BASE_DIR = Path(__file__).parent
CHAT_DIR = BASE_DIR / "chat"

# 数据库路径配置
TOOL_DB_PATH = BASE_DIR / "tool_db"
LOCATION_DB_PATH = BASE_DIR / "location_data"
MEMORY_DB_PATH = BASE_DIR / "memory_db"

# -----------------------------------------------------------------------------
# Prompt Loading Functions
# -----------------------------------------------------------------------------

@lru_cache(maxsize=None)
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
    # 在示例中，我们只演示从文件加载
    return _load_prompt_file("base_prompt.md")

def get_expression_prompt() -> str:
    """加载表情/关键词指令提示"""
    return _load_prompt_file("expression_prompt.md")

def get_tool_prompt() -> str:
    """加载工具使用指南提示"""
    return _load_prompt_file("tool_prompt.md")

# -----------------------------------------------------------------------------
# LLM Configuration
# -----------------------------------------------------------------------------

# LLM 配置
LLM_CONFIG = {
    # 当前使用的 LLM 类型
    "type": "gemini",  # 可选: "chatgpt", "gemini", "anthropic"
    
    "debug": False,  # 是否打印调试信息（API请求payload等）
    
    # ChatGPT 特定配置
    "chatgpt": {
        "api_key": os.getenv("OPENAI_API_KEY", "your_openai_api_key_here"),
        "model": "gpt-4o",  
        "temperature": 1.0,
    },
    
    # Gemini 特定配置
    "gemini": {
        "api_key": os.getenv("GOOGLE_API_KEY", "your_google_api_key_here"),
        "model": "gemini-1.5-pro-latest",  
        "temperature": 1.0,
        "maxOutputTokens": 8192
    },
    
    # Anthropic 特定配置
    "anthropic": {
        "api_key": os.getenv("ANTHROPIC_API_KEY", "your_anthropic_api_key_here"),
        "model": "claude-3-5-sonnet-20240620",
        "temperature": 1.0,
        "max_tokens": 4096,
    }
}

# TTS 配置
TTS_CONFIG = {
    "type": "gpt_sovits",  # 可选: "fish_audio" 或 "gpt_sovits"
    "fish_audio": {
        "api_key": os.getenv("FISH_AUDIO_API_KEY", "your_fish_speech_api_key_here"),
        "reference_id": os.getenv("FISH_AUDIO_REFERENCE_ID", "your_reference_id_here")
    },
    "gpt_sovits": {
        "server_url": os.getenv("GPT_SOVITS_SERVER_URL", "http://localhost:9880"),
        "text_lang": "zh",
        "speed": 1.0,
        "ref_audio_path": os.getenv("GPT_SOVITS_REFERENCE_AUDIO_PATH", "path/to/your/reference.wav"),
        "prompt_lang": "zh",
        "prompt_text": "嗯～～ ",
        "cut_punc": "",
        "top_k": 20,
        "top_p": 1.0,
        "temperature": 1.2,
        "inp_refs": ""
    }
}

# Google Custom Search API 配置
GOOGLE_CUSTOM_SEARCH_API_KEY = os.getenv("GOOGLE_CUSTOM_SEARCH_API_KEY", "your_google_custom_search_api_key_here")
GOOGLE_CUSTOM_SEARCH_ENGINE_ID = os.getenv("GOOGLE_CUSTOM_SEARCH_ENGINE_ID", "your_google_custom_search_engine_id_here")

# 邮件配置
EMAIL_CONFIG = {
    "smtp_server": os.getenv("EMAIL_SMTP_SERVER", "smtp.example.com"),
    "smtp_port": int(os.getenv("EMAIL_SMTP_PORT", "587")),
    "username": os.getenv("EMAIL_USERNAME", "your_email@example.com"),
    "password": os.getenv("EMAIL_PASSWORD", "your_email_password"),
    "use_tls": True,
    "sender_name": "Nagisa Assistant",
    "imap_server": os.getenv("EMAIL_IMAP_SERVER", "imap.example.com"),
    "imap_port": int(os.getenv("EMAIL_IMAP_PORT", "993")),
}

# Google Auth 配置
AUTH_CONFIG = {
    "client_id": os.getenv("AUTH_CLIENT_ID", "your_google_client_id_here"),
    "client_secret": os.getenv("AUTH_CLIENT_SECRET", "your_google_client_secret_here"),
}

# Text-to-Image 配置
TEXT_TO_IMAGE_CONFIG = {
    "type": "stable_diffusion_webui",  # 可选: "models_lab", "stable_diffusion_webui"
    "system_prompt": "You are a professional prompt engineer specializing in AI image generation.",
    "context_message_count": 8,
    "default_positive_prompt": "high quality, detailed, masterpiece, best quality",
    "default_negative_prompt": "blurry, low quality, distorted, bad anatomy, text, watermark, ugly, deformed",
    "debug": True,
    "models_lab": {
        "key": os.getenv("MODELS_LAB_API_KEY", "your_models_lab_api_key_here"),
        "model_id": "midjourney",
        "width": 1024,
        "height": 1024,
        "samples": 1,
        "num_inference_steps": 30,
        "safety_checker": False,
        "enhance_prompt": "yes",
        "guidance_scale": 7.5,
        "scheduler": "UniPCMultistepScheduler",
    },
    "stable_diffusion_webui": {
        "server_url": os.getenv("STABLE_DIFFUSION_WEBUI_URL", "http://127.0.0.1:7860/sdapi/v1/txt2img"),
        "steps": 25,
        "seed": -1,
        "enable_hr": False,
        "hr_scale": 2.0,
        "hr_upscaler": "4x-UltraSharp",
        "denoising_strength": 0.5,
        "model_type": "illustrious",  # 手动选择模型预设，可选: "illustrious", "sdxl", "sd15"
        "debug": False,
        "model_presets": {
            "illustrious": {
                "sd_model_checkpoint": "your_illustrious_model.safetensors",
                "sd_vae": "your_sdxl_vae.safetensors",
                "width": 832,
                "height": 1216,
                "cfg_scale": 5.0,
                "clip_skip": 2,
                "sampler_name": "Euler a"
            },
            "sdxl": {
                "sd_model_checkpoint": "your_sdxl_base_model.safetensors",
                "sd_vae": "your_sdxl_vae.safetensors",
                "width": 1024,
                "height": 1024,
                "cfg_scale": 6.0,
                "clip_skip": 2,
                "sampler_name": "DPM++ 2M Karras"
            },
            "sd15": {
                "sd_model_checkpoint": "your_sd15_model.safetensors",
                "sd_vae": "your_sd15_vae.safetensors",
                "width": 512,
                "height": 768,
                "cfg_scale": 7.0,
                "clip_skip": 1,
                "sampler_name": "DPM++ SDE Karras"
            }
        }
    }
}

# 配置获取函数
def get_llm_config() -> Dict[str, Any]:
    """获取 LLM 配置"""
    return LLM_CONFIG

def get_current_llm_type() -> str:
    """获取当前使用的 LLM 类型"""
    return LLM_CONFIG["type"]

def get_llm_specific_config(llm_type: Optional[str] = None) -> Dict[str, Any]:
    """获取特定 LLM 的配置"""
    llm_type = llm_type or LLM_CONFIG["type"]
    return LLM_CONFIG.get(llm_type, {})

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

def get_tts_config() -> dict:
    """获取 TTS 配置"""
    return TTS_CONFIG 

def get_email_config() -> dict:
    """获取邮件配置"""
    return EMAIL_CONFIG 

def get_auth_config() -> dict:
    """获取 Google Auth 配置"""
    return AUTH_CONFIG 

def get_text_to_image_config() -> dict:
    """获取 Text-to-Image 配置"""
    return TEXT_TO_IMAGE_CONFIG 