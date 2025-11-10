"""
Gemini Client Configuration Module

This module contains all Gemini-specific configuration settings,
including safety settings, model parameters, and other Gemini-specific options.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from google.genai import types


class GeminiSafetySettings(BaseModel):
    """Gemini safety settings"""
    
    # 每个安全类别的阈值设置
    sexually_explicit_threshold: types.HarmBlockThreshold = Field(
        default=types.HarmBlockThreshold.BLOCK_NONE,
        description="Sexually explicit content blocking threshold"
    )
    harassment_threshold: types.HarmBlockThreshold = Field(
        default=types.HarmBlockThreshold.BLOCK_NONE,
        description="Harassment content blocking threshold"
    )
    dangerous_content_threshold: types.HarmBlockThreshold = Field(
        default=types.HarmBlockThreshold.BLOCK_NONE,
        description="Dangerous content blocking threshold"
    )
    hate_speech_threshold: types.HarmBlockThreshold = Field(
        default=types.HarmBlockThreshold.BLOCK_NONE,
        description="Hate speech blocking threshold"
    )
    
    def to_gemini_format(self) -> List[Dict[str, Any]]:
        """Convert to Gemini API format safety settings"""
        return [
            {
                "category": types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                "threshold": self.sexually_explicit_threshold
            },
            {
                "category": types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                "threshold": self.harassment_threshold
            },
            {
                "category": types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                "threshold": self.dangerous_content_threshold
            },
            {
                "category": types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                "threshold": self.hate_speech_threshold
            }
        ]


class GeminiModelConfig(BaseModel):
    """Gemini model parameters configuration"""
    
    # 基础模型配置
    model: str = Field(
        default="gemini-2.5-flash",
        description="Default model name"
    )
    temperature: float = Field(
        default=2.0,
        ge=0.0,
        le=2.0,
        description="Sampling temperature, controlling the randomness of the output"
    )
    max_output_tokens: int = Field(
        default=4096,
        ge=1,
        description="Maximum output token number"
    )
    top_p: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Top-P sampling probability"
    )
    top_k: Optional[int] = Field(
        default=None,
        ge=1,
        description="Top-K sampling"
    )
    
    # Gemini 2.5 特有配置
    enable_thinking_for_gemini_2_5: bool = Field(
        default=True,
        description="Whether to enable thinking mode for Gemini 2.5 model"
    )
    include_thoughts_in_response: bool = Field(
        default=True,
        description="Whether to include thinking process in the response"
    )
    preserve_thinking_in_history: bool = Field(
        default=True,  # ✅ Changed from False to True for PFC agent use case
        description=(
            "Whether to preserve thinking content when loading conversation history. "
            "Benefits: "
            "(1) Future-proof for cross-turn reasoning support "
            "(2) Enable 'reasoning resume' after backend restart "
            "(3) Preserve thought signatures for tool calling chains. "
            "Note: Working context always preserves thinking during tool calls. "
            "Recommended: Enable for PFC agent or domain-specific sessions where reasoning continuity is valuable."
        )
    )


class GeminiClientConfig(BaseModel):
    """Gemini Client full configuration"""
    
    # 安全设置
    safety_settings: GeminiSafetySettings = Field(
        default_factory=GeminiSafetySettings,
        description="Gemini safety settings"
    )
    
    # 模型配置
    model_settings: GeminiModelConfig = Field(
        default_factory=GeminiModelConfig,
        description="Gemini model configuration"
    )
    
    # 调试配置
    debug: bool = Field(
        default=False,
        description="Whether to enable debug mode"
    )
    
    # 工具相关配置
    tools_enabled: bool = Field(
        default=True,
        description="Whether to enable tool calling function"
    )
    
    def get_generation_config_kwargs(self, system_prompt: str, tool_schemas: List[types.Tool] = None) -> Dict[str, Any]:
        """
        Get GenerateContentConfig parameters for Gemini API
        
        Args:
            system_prompt: system prompt
            tool_schemas: tool schemas list
            
        Returns:
            Dict[str, Any]: GenerateContentConfig parameters
        """
        
        config_kwargs = {
            "system_instruction": system_prompt,
            "safety_settings": self.safety_settings.to_gemini_format(),
            "temperature": self.model_settings.temperature,
            "max_output_tokens": self.model_settings.max_output_tokens,
        }
        
        # Add optional parameters
        if self.model_settings.top_p is not None:
            config_kwargs["top_p"] = self.model_settings.top_p
        if self.model_settings.top_k is not None:
            config_kwargs["top_k"] = self.model_settings.top_k
        
        # Add tool schemas
        if tool_schemas:
            config_kwargs["tools"] = tool_schemas
        
        # Add thinking configuration for Gemini 2.5 model
        if (self.model_settings.model.startswith("gemini-2.5") and 
            self.model_settings.enable_thinking_for_gemini_2_5):
            config_kwargs["thinking_config"] = types.ThinkingConfig(
                include_thoughts=self.model_settings.include_thoughts_in_response
            )
        
        return config_kwargs


# Default configuration instance
DEFAULT_GEMINI_CONFIG = GeminiClientConfig()


def get_gemini_client_config(**overrides) -> GeminiClientConfig:
    """
    Get Gemini Client configuration, support runtime overrides
    
    Args:
        **overrides: Configuration items to override
        
    Returns:
        GeminiClientConfig: Configuration instance
    """
    if not overrides:
        return DEFAULT_GEMINI_CONFIG
    
    # Create configuration copy and apply overrides
    config_dict = DEFAULT_GEMINI_CONFIG.model_dump()
    
    # Process nested configuration overrides
    for key, value in overrides.items():
        if key == "safety_settings" and isinstance(value, dict):
            config_dict["safety_settings"].update(value)
        elif key == "model_config" and isinstance(value, dict):
            # Support both "model_config" and "model_settings" for backward compatibility
            config_dict["model_settings"].update(value)
        elif key == "model_settings" and isinstance(value, dict):
            config_dict["model_settings"].update(value)
        else:
            config_dict[key] = value
    
    return GeminiClientConfig(**config_dict) 