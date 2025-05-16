"""
TTS Factory module for aiNagisa
用于根据配置动态选择和实例化 TTS 引擎
"""

from typing import Optional
from backend.tts.base import BaseTTS
from backend.tts.remote.fish_audio import FishAudioTTS, FishSpeechConfig
from backend.tts.local.gpt_sovits import GPTSoVITSTTS, GPTSoVITSConfig
from backend.config import get_tts_config

def get_tts_engine() -> BaseTTS:
    """
    根据配置获取对应的 TTS 引擎实例
    
    Returns:
        BaseTTS: TTS 引擎实例
        
    Raises:
        ValueError: 如果配置的 TTS 类型不支持
    """
    config = get_tts_config()
    tts_type = config.get('type', 'fish_audio').lower()
    
    if tts_type == 'fish_audio':
        return FishAudioTTS(FishSpeechConfig(config.get('fish_audio', {})))
    elif tts_type == 'gpt_sovits':
        return GPTSoVITSTTS(GPTSoVITSConfig(config.get('gpt_sovits', {})))
    else:
        raise ValueError(f"Unsupported TTS type: {tts_type}") 