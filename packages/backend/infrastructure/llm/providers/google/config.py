"""
Google Client Configuration Module

This module contains all Google-specific configuration settings,
including safety settings, model parameters, and other Google-specific options.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from google.genai import types


class GoogleConfig(BaseSettings):
    """Google (Gemini) configuration loaded from environment variables."""

    google_api_key: str = Field(description="Google API key")
    model: str = Field(default="gemini-3-flash-preview", description="Default model")
    secondary_model: str = Field(
        default="gemini-3-flash-preview",
        description="Secondary model for SubAgent"
    )

    model_config = SettingsConfigDict(
        env_file='packages/backend/.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )


class GoogleSafetySettings(BaseModel):
    """Google safety settings"""
    
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
    
    def to_gemini_format(self) -> List[types.SafetySetting]:
        """Convert to Google API format safety settings"""
        return [
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=self.sexually_explicit_threshold
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=self.harassment_threshold
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=self.dangerous_content_threshold
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=self.hate_speech_threshold
            ),
        ]


class GoogleModelConfig(BaseModel):
    """Google model parameters configuration"""
    
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
    max_tokens: int = Field(
        default=1024*16,
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
    
    # Thinking configuration
    enable_thinking: bool = Field(
        default=True,
        description="Whether to enable thinking mode for supported models (Google 2.5+, Google 3+)"
    )
    include_thoughts_in_response: bool = Field(
        default=True,
        description="Whether to include thinking process in the response"
    )
    # Note: thinking content and thought_signature are ALWAYS preserved in history
    # This is required for: cross-turn reasoning, tool calling chain validation, context caching

    # Backward compatibility alias
    @property
    def enable_thinking_for_gemini_2_5(self) -> bool:
        """Backward compatibility alias for enable_thinking"""
        return self.enable_thinking


class GoogleClientConfig(BaseModel):
    """Google Client full configuration"""
    
    # 安全设置
    safety_settings: GoogleSafetySettings = Field(
        default_factory=GoogleSafetySettings,
        description="Google safety settings"
    )
    
    # 模型配置
    model_settings: GoogleModelConfig = Field(
        default_factory=GoogleModelConfig,
        description="Google model configuration"
    )
    
    # 调试配置
    debug: bool = Field(
        default=False,
        description="Whether to enable debug mode"
    )

    timeout: float = Field(
        default=60.0,
        description="Request timeout in seconds"
    )

    max_retries: int = Field(
        default=3,
        description="Maximum number of retries for failed requests"
    )
    
    # 工具相关配置
    tools_enabled: bool = Field(
        default=True,
        description="Whether to enable tool calling function"
    )
    
    def get_generation_config_kwargs(self, system_prompt: str, tool_schemas: Optional[List[types.Tool]]) -> Dict[str, Any]:
        """
        Get GenerateContentConfig parameters for Google API
        
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
            "max_output_tokens": self.model_settings.max_tokens,
        }
        
        # Add optional parameters
        if self.model_settings.top_p is not None:
            config_kwargs["top_p"] = self.model_settings.top_p
        if self.model_settings.top_k is not None:
            config_kwargs["top_k"] = self.model_settings.top_k
        
        # Add tool schemas
        if tool_schemas:
            config_kwargs["tools"] = tool_schemas
        
        # Add thinking configuration based on model version
        model = self.model_settings.model
        if self.model_settings.enable_thinking:
            # Google 3 models use thinking_level parameter (enum)
            if model.startswith("gemini-3"):
                config_kwargs["thinking_config"] = types.ThinkingConfig(
                    thinking_level=types.ThinkingLevel.HIGH,  # LOW or HIGH, cannot be disabled for Google 3
                    include_thoughts=self.model_settings.include_thoughts_in_response
                )
            # Google 2.5 models use thinking_budget parameter
            elif model.startswith("gemini-2.5"):
                config_kwargs["thinking_config"] = types.ThinkingConfig(
                    thinking_budget=-1,  # -1 = dynamic (auto), model adjusts based on complexity
                    include_thoughts=self.model_settings.include_thoughts_in_response
                )

        return config_kwargs


# Default configuration instance
DEFAULT_GEMINI_CONFIG = GoogleClientConfig()


def get_google_client_config(**overrides) -> GoogleClientConfig:
    """
    Get Google Client configuration, support runtime overrides
    
    Args:
        **overrides: Configuration items to override
        
    Returns:
        GoogleClientConfig: Configuration instance
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
    
    return GoogleClientConfig(**config_dict) 
