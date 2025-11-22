"""
TTS Configuration Module
Contains configurations for text-to-speech services
"""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FishAudioConfig(BaseSettings):
    """Fish Audio Configuration"""
    
    # Required sensitive information - field names directly match environment variables
    fish_audio_api_key: str = Field(description="Fish Audio API key")
    fish_audio_reference_id: str = Field(description="Reference audio ID")
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )
    
class GPTSoVITSConfig(BaseSettings):
    """GPT-SoVITS Configuration"""
    
    # Server configuration
    server_url: str = Field(default="http://localhost:9880", description="GPT-SoVITS server URL", validation_alias="GPT_SOVITS_SERVER_URL")
    
    # Voice generation configuration
    text_lang: str = Field(default="zh", description="Text language")
    speed: float = Field(default=1.0, ge=0.1, le=3.0, description="Speech speed")
    prompt_lang: str = Field(default="zh", description="Prompt language")
    prompt_text: str = Field(default=" ", description="Prompt text")
    cut_punc: str = Field(default="", description="Cut punctuation")
    
    # Sampling configuration
    top_k: int = Field(default=20, ge=1, description="Top-K sampling")
    top_p: float = Field(default=1.0, ge=0.0, le=1.0, description="Top-P sampling")
    temperature: float = Field(default=1.2, ge=0.0, le=2.0, description="Sampling temperature")
    
    # Audio configuration
    ref_audio_path: str = Field(
        default="GPT_SoVITS/pretrained_models/reference.wav",
        description="Reference audio path",
        validation_alias="GPT_SOVITS_REFERENCE_AUDIO_PATH"
    )
    inp_refs: str = Field(default="", description="Input references")
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        populate_by_name=True,  # Allow population by field name or alias
        extra='ignore'
    )
    
class TTSSettings(BaseSettings):
    """TTS Master Configuration"""
    
    # Currently used TTS type
    type: Literal["fish_audio", "gpt_sovits"] = Field(default="gpt_sovits", description="Currently used TTS type")
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='TTS__',
        extra='ignore'
    )
    
    def get_fish_audio_config(self) -> FishAudioConfig:
        """Get Fish Audio configuration"""
        return FishAudioConfig()
    
    def get_gpt_sovits_config(self) -> GPTSoVITSConfig:
        """Get GPT-SoVITS configuration"""
        return GPTSoVITSConfig()
    
    def get_current_tts_config(self):
        """Get current TTS configuration"""
        if self.type == "fish_audio":
            return self.get_fish_audio_config()
        elif self.type == "gpt_sovits":
            return self.get_gpt_sovits_config()
        else:
            raise ValueError(f"Unsupported TTS type: {self.type}")
    
    def validate_current_tts(self):
        """Validate current TTS configuration - implements fail fast"""
        try:
            config = self.get_current_tts_config()
            # This will trigger configuration validation
            return config
        except Exception as e:
            raise ValueError(f"Current TTS configuration validation failed: {e}")


# Global TTS configuration instance
def get_tts_settings() -> TTSSettings:
    """Get TTS configuration instance"""
    return TTSSettings() 