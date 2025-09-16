"""
TTS Factory module for aiNagisa
用于根据配置动态选择和实例化 TTS 引擎
"""

from typing import Optional
from backend.infrastructure.tts.base import BaseTTS
from backend.infrastructure.tts.remote.fish_audio import FishAudioTTS, FishSpeechConfig
from backend.infrastructure.tts.local.gpt_sovits import GPTSoVITSTTS, GPTSoVITSConfig
from backend.config import get_tts_settings

# Global TTS engine instance
_tts_engine: Optional[BaseTTS] = None

def get_tts_engine() -> BaseTTS:
    """
    根据配置获取对应的 TTS 引擎实例
    
    Returns:
        BaseTTS: TTS 引擎实例
        
    Raises:
        ValueError: 如果配置的 TTS 类型不支持
    """
    settings = get_tts_settings()
    tts_type = settings.type.lower()
    
    if tts_type == 'fish_audio':
        fish_config = settings.get_fish_audio_config()
        return FishAudioTTS(FishSpeechConfig({
            'api_key': fish_config.fish_audio_api_key,
            'reference_id': fish_config.fish_audio_reference_id,
        }))
    elif tts_type == 'gpt_sovits':
        gpt_config = settings.get_gpt_sovits_config()
        return GPTSoVITSTTS(GPTSoVITSConfig({
            'server_url': gpt_config.gpt_sovits_server_url,
            'text_lang': gpt_config.text_lang,
            'speed': gpt_config.speed,
            'ref_audio_path': gpt_config.ref_audio_path,
            'prompt_lang': gpt_config.prompt_lang,
            'prompt_text': gpt_config.prompt_text,
            'cut_punc': gpt_config.cut_punc,
            'top_k': gpt_config.top_k,
            'top_p': gpt_config.top_p,
            'temperature': gpt_config.temperature,
            'inp_refs': gpt_config.inp_refs,
        }))
    else:
        raise ValueError(f"Unsupported TTS type: {tts_type}") 