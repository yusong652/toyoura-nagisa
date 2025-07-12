"""
TTS配置模块
包含文本转语音相关的配置
"""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FishAudioConfig(BaseSettings):
    """Fish Audio配置"""
    
    # 必需的敏感信息 - 字段名直接匹配环境变量
    fish_audio_api_key: str = Field(description="Fish Audio API密钥")
    fish_audio_reference_id: str = Field(description="参考音频ID")
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )
    
class GPTSoVITSConfig(BaseSettings):
    """GPT-SoVITS配置"""
    
    # 服务器配置
    server_url: str = Field(default="http://localhost:9880", description="GPT-SoVITS服务器URL", validation_alias="GPT_SOVITS_SERVER_URL")
    
    # 语音生成配置
    text_lang: str = Field(default="zh", description="文本语言")
    speed: float = Field(default=1.0, ge=0.1, le=3.0, description="语速")
    prompt_lang: str = Field(default="zh", description="提示语言")
    prompt_text: str = Field(default=" ", description="提示文本")
    cut_punc: str = Field(default="", description="切分标点")
    
    # 采样配置
    top_k: int = Field(default=20, ge=1, description="Top-K采样")
    top_p: float = Field(default=1.0, ge=0.0, le=1.0, description="Top-P采样")
    temperature: float = Field(default=1.2, ge=0.0, le=2.0, description="采样温度")
    
    # 音频配置
    ref_audio_path: str = Field(
        default="GPT_SoVITS/pretrained_models/reference.wav",
        description="参考音频路径",
        validation_alias="GPT_SOVITS_REFERENCE_AUDIO_PATH"
    )
    inp_refs: str = Field(default="", description="输入引用")
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        populate_by_name=True,  # 允许使用字段或别名填充
        extra='ignore'
    )
    
class TTSSettings(BaseSettings):
    """TTS总配置"""
    
    # 当前使用的TTS类型
    type: Literal["fish_audio", "gpt_sovits"] = Field(default="gpt_sovits", description="当前使用的TTS类型")
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='TTS__',
        extra='ignore'
    )
    
    def get_fish_audio_config(self) -> FishAudioConfig:
        """获取Fish Audio配置"""
        return FishAudioConfig()
    
    def get_gpt_sovits_config(self) -> GPTSoVITSConfig:
        """获取GPT-SoVITS配置"""
        return GPTSoVITSConfig()
    
    def get_current_tts_config(self):
        """获取当前TTS配置"""
        if self.type == "fish_audio":
            return self.get_fish_audio_config()
        elif self.type == "gpt_sovits":
            return self.get_gpt_sovits_config()
        else:
            raise ValueError(f"不支持的TTS类型: {self.type}")
    
    def validate_current_tts(self):
        """验证当前TTS配置 - 实现fail fast"""
        try:
            config = self.get_current_tts_config()
            # 这里会触发配置验证
            return config
        except Exception as e:
            raise ValueError(f"当前TTS配置验证失败: {e}")


# 全局TTS配置实例
def get_tts_settings() -> TTSSettings:
    """获取TTS配置实例"""
    return TTSSettings() 