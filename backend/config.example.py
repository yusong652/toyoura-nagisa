"""
配置文件示例，用于管理应用的各种配置项。
请复制此文件为 config.py 并填入您的实际配置。
"""

from typing import Dict, Any, Optional
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 基础配置
BASE_DIR = Path(__file__).parent

# 提示词相关配置
PROMPT_CONFIG = {
    # 允许的关键词列表
    "allowed_keywords": [
        'neutral', 'happy', 'sad', 'angry', 'confused', 'blush',
        'thinking', 'nod', 'shake', 'cry', 'shocked', 'surprised', 'upset'
    ],
    
    # 基础 Persona 定义
    "nagisa_persona": """
    豊浦 凪沙（Toyoura Nagisa）Persona
    You are a good assistant.
    
    """.strip(),
    
    # 输出关键词的指令模板
    "keyword_instruction_template": """
在你的回复文本结束后，请在最后一行单独输出一个最能代表该回复核心情绪或内容的关键词，格式为 [[关键词]]。
请严格从以下列表中选择一个词，并用双方括号包裹：
[[{keywords}]]
例如：

能帮上忙真是太好了！
[[happy]]

如果没有任何特别的情绪或动作含义则使用 [[neutral]]。
""".strip()
}

# LLM 配置
LLM_CONFIG = {
    # 当前使用的 LLM 类型
    "type": "gemini",  # 可选: "chatgpt", "gemini"
    
    "system_prompt": None,  # 如果为 None，将使用默认的 system prompt
    "debug": False,  # 是否打印调试信息（API请求payload等）
    "enable_tool_use": True,  # 是否允许调用工具（tool use），如需禁用工具调用可设为 False
    
    # ChatGPT 特定配置
    "chatgpt": {
        "api_key": "your_openai_api_key_here",  # 替换为您的 OpenAI API 密钥
        "model": "gpt-4.1-mini",  # 默认模型
        "temperature": 1.5,
        "top_p": 0.95,
        "top_k": 40,
    },
    
    # Gemini 特定配置
    "gemini": {
        "api_key": "your_google_api_key_here",  # 替换为您的 Google API 密钥
        "model": "gemini-2.0-flash-lite",  # 默认模型
        "temperature": 1.2,
        "top_p": 0.95,
        "top_k": 40,
        "maxOutputTokens": 512
    }
}

# TTS 配置
TTS_CONFIG = {
    "type": "gpt_sovits",  # 可选: "fish_audio" 或 "gpt_sovits"
    "fish_audio": {
        "api_key": "your_fish_speech_api_key_here",  # 替换为您的 Fish Speech API 密钥
        "reference_id": "your_reference_id_here"  # 替换为您的参考 ID
    },
    "gpt_sovits": {
        "server_url": "http://localhost:9880",  # GPT-SoVITS 服务器 URL
        "text_lang": "zh",  # 文本语言
        "speed": 1.1,  # 语速
        "ref_audio_path": "GPT_SoVITS/pretrained_models/reference.wav",  # 参考音频路径
        "prompt_lang": "zh",  # 提示语言
        "prompt_text": " ",  # 提示文本
        "cut_punc": "",  # 切分标点
        "top_k": 20,  # Top-K 采样
        "top_p": 1.0,  # Top-P 采样
        "temperature": 1.2,  # 温度
        "inp_refs": ""  # 输入引用
    }
}

# Google Custom Search API 配置
GOOGLE_CUSTOM_SEARCH_API_KEY = "your_google_custom_search_api_key_here"
GOOGLE_CUSTOM_SEARCH_ENGINE_ID = "your_google_custom_search_engine_id_here"

def get_llm_config() -> Dict[str, Any]:
    """
    获取 LLM 配置。
    Returns:
        LLM 配置字典
    """
    return LLM_CONFIG

def get_current_llm_type() -> str:
    """
    获取当前使用的 LLM 类型。
    Returns:
        LLM 类型字符串
    """
    return LLM_CONFIG["type"]

def get_llm_specific_config(llm_type: Optional[str] = None) -> Dict[str, Any]:
    """
    获取特定 LLM 的配置。
    Args:
        llm_type: LLM 类型，如果为 None 则使用当前配置的类型
    Returns:
        特定 LLM 的配置字典
    """
    llm_type = llm_type or LLM_CONFIG["type"]
    return LLM_CONFIG.get(llm_type, {})

def get_prompt_config() -> Dict[str, Any]:
    """
    获取提示词配置。
    Returns:
        提示词配置字典
    """
    return PROMPT_CONFIG

def get_system_prompt() -> str:
    """
    获取完整的系统提示词。
    Returns:
        合并后的系统提示词
    """
    config = get_prompt_config()
    keywords = "]], [[".join(config["allowed_keywords"])
    instruction = config["keyword_instruction_template"].format(keywords=keywords)
    system_prompt = f"{config['nagisa_persona']}\n\n{instruction}" 
    return system_prompt

def get_tts_config() -> dict:
    """
    获取 TTS 配置
    
    Returns:
        dict: TTS 配置字典，包含以下字段：
            - type: TTS 引擎类型 ('fish_audio' 或 'gpt_sovits')
            - 其他 TTS 引擎特定的配置项
    """
    return TTS_CONFIG 