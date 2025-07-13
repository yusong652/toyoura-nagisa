"""
文本转图像配置模块
包含文本转图像生成相关的配置
"""
from __future__ import annotations
from typing import Literal, Optional, Dict, Any
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelsLabConfig(BaseSettings):
    """Models Lab配置"""
    
    # 必需的敏感信息 - 字段名直接匹配环境变量MODELS_LAB_API_KEY
    models_lab_api_key: str = Field(description="Models Lab API密钥")
    
    # 生成参数配置
    model_id: str = Field(default="midjourney", description="模型ID")
    width: int = Field(default=1024, ge=64, le=2048, description="图像宽度")
    height: int = Field(default=1024, ge=64, le=2048, description="图像高度")
    samples: int = Field(default=1, ge=1, le=4, description="生成图像数量")
    num_inference_steps: int = Field(default=30, ge=1, le=150, description="推理步数")
    safety_checker: bool = Field(default=False, description="是否启用安全检查")
    enhance_prompt: str = Field(default="yes", description="是否增强提示词")
    guidance_scale: float = Field(default=7.5, ge=1.0, le=20.0, description="引导比例")
    scheduler: str = Field(default="UniPCMultistepScheduler", description="调度器")
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )
    
class ModelPreset(BaseSettings):
    """模型预设配置"""
    
    sd_model_checkpoint: str = Field(description="Stable Diffusion模型检查点")
    sd_vae: str = Field(description="VAE模型")
    width: int = Field(ge=64, le=2048, description="图像宽度")
    height: int = Field(ge=64, le=2048, description="图像高度")
    cfg_scale: float = Field(ge=1.0, le=20.0, description="CFG比例")
    clip_skip: int = Field(ge=1, le=12, description="CLIP跳过层数")
    sampler_name: str = Field(description="采样器名称")
    
    model_config = SettingsConfigDict(extra='allow')


class StableDiffusionWebUIConfig(BaseSettings):
    """Stable Diffusion WebUI配置"""
    
    # 服务器配置
    server_url: str = Field(
        default="http://127.0.0.1:7860/sdapi/v1/txt2img",
        description="Stable Diffusion WebUI服务器URL",
        validation_alias="STABLE_DIFFUSION_WEBUI_URL"
    )
    
    # 生成参数配置
    steps: int = Field(default=25, ge=1, le=150, description="采样步数")
    sampler_name: str = Field(default="DPM++ 2M Karras", description="采样器名称")
    cfg_scale: float = Field(default=6.0, ge=1.0, le=20.0, description="CFG比例")
    seed: int = Field(default=-1, description="随机种子")
    
    # 高分辨率修复配置
    enable_hr: bool = Field(default=False, description="是否启用高分辨率修复")
    hr_scale: float = Field(default=2.0, ge=1.0, le=4.0, description="高分辨率缩放比例")
    hr_upscaler: str = Field(default="4x-UltraSharp", description="高分辨率放大器")
    denoising_strength: float = Field(default=0.5, ge=0.0, le=1.0, description="去噪强度")
    
    # 模型配置
    model_type: Literal["illustrious", "sdxl", "sd15"] = Field(
        default="illustrious",
        description="模型类型预设"
    )
    debug: bool = Field(default=False, description="是否启用调试模式")
    
    # 模型预设配置
    model_presets: Dict[str, Dict[str, Any]] = Field(
        default={
            "illustrious": {
                "sd_model_checkpoint": "illustriousXLPersonalMerge_v10.safetensors",
                "sd_vae": "sdxl_vae.safetensors",
                "width": 1024,
                "height": 1536,
                "cfg_scale": 7.0,
                "clip_skip": 2,
                "sampler_name": "Euler a"
            },
            "sdxl": {
                "sd_model_checkpoint": "sd_xl_base_1.0.safetensors",
                "sd_vae": "sdxl_vae.safetensors",
                "width": 1024,
                "height": 1024,
                "cfg_scale": 6.0,
                "clip_skip": 2,
                "sampler_name": "DPM++ 2M Karras"
            },
            "sd15": {
                "sd_model_checkpoint": "v1-5-pruned-emaonly.safetensors",
                "sd_vae": "vae-ft-mse-840000-ema-pruned.safetensors",
                "width": 512,
                "height": 768,
                "cfg_scale": 7.0,
                "clip_skip": 1,
                "sampler_name": "DPM++ SDE Karras"
            }
        },
        description="模型预设配置"
    )
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        populate_by_name=True,  # 允许使用字段或别名填充
        extra='ignore'
    )
    
    def get_current_preset(self) -> Dict[str, Any]:
        """获取当前模型预设"""
        return self.model_presets.get(self.model_type, {})


class TextToImageSettings(BaseSettings):
    """文本转图像总配置"""
    
    # 重命名避免冲突
    provider: Literal["models_lab", "stable_diffusion_webui"] = Field(
        default="stable_diffusion_webui",
        description="当前使用的文本转图像服务提供商"
    )
    
    # 系统配置
    text_to_image_system_prompt: str = Field(description="文生图系统提示词，用于生成图像的提示词")
    context_message_count: int = Field(default=10, ge=1, le=50, description="上下文消息数量")
    
    # 默认提示词配置
    default_positive_prompt: str = Field(
        default="high quality, detailed, masterpiece, best quality",
        description="默认正面提示词"
    )
    default_negative_prompt: str = Field(
        default="blurry, low quality, distorted, bad anatomy, text, watermark, ugly, deformed",
        description="默认负面提示词"
    )
    
    # 重命名避免冲突
    enable_debug: bool = Field(default=True, description="是否启用调试模式")
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',  # 删除前缀！
        extra='ignore'
    )
    
    def get_models_lab_config(self) -> ModelsLabConfig:
        """获取Models Lab配置"""
        return ModelsLabConfig()
    
    def get_stable_diffusion_webui_config(self) -> StableDiffusionWebUIConfig:
        """获取Stable Diffusion WebUI配置"""
        return StableDiffusionWebUIConfig()
    
    def get_current_config(self):
        """获取当前文本转图像配置"""
        if self.provider == "models_lab":
            return self.get_models_lab_config()
        elif self.provider == "stable_diffusion_webui":
            return self.get_stable_diffusion_webui_config()
        else:
            raise ValueError(f"不支持的文本转图像类型: {self.provider}")
    
    def validate_current_config(self):
        """验证当前文本转图像配置 - 实现fail fast"""
        try:
            config = self.get_current_config()
            # 这里会触发配置验证
            return config
        except Exception as e:
            raise ValueError(f"当前文本转图像配置验证失败: {e}")


# 全局文本转图像配置实例
def get_text_to_image_settings() -> TextToImageSettings:
    """获取文本转图像配置实例"""
    return TextToImageSettings() 