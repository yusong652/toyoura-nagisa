"""
LLM Configuration Module
Contains all large language model related configurations
"""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OpenAIConfig(BaseSettings):
    """OpenAI Configuration"""
    openai_api_key: str = Field(description="OpenAI API Key")
    model: str = Field(default="gpt-4o-2024-08-06", description="Model name")
    temperature: float = Field(default=1.0, ge=0.0, le=2.0, description="Sampling temperature")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Nucleus sampling probability")
    top_k: Optional[int] = Field(default=None, ge=1, description="Top-K sampling")
    max_tokens: Optional[int] = Field(default=None, ge=1, description="Max output tokens")
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )


class GeminiConfig(BaseSettings):
    """Gemini Configuration"""
    google_api_key: str = Field(description="Google API Key")
    model: str = Field(default="gemini-2.5-flash", description="Model name")
    temperature: float = Field(default=1.0, ge=0.0, le=2.0, description="Sampling temperature")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Nucleus sampling probability")
    top_k: Optional[int] = Field(default=None, ge=1, description="Top-K sampling")
    max_output_tokens: int = Field(default=8192, alias="maxOutputTokens", ge=1, description="Max output tokens")
    web_search_max_uses: int = Field(default=5, ge=1, le=20, description="Web search max uses")
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )


class AnthropicConfig(BaseSettings):
    """Anthropic Configuration"""
    anthropic_api_key: str = Field(description="Anthropic API Key")
    model: str = Field(default="claude-3-5-sonnet-20241022", description="模型名称")
    temperature: float = Field(default=1.0, ge=0.0, le=2.0, description="采样温度")
    max_tokens: int = Field(default=4096, ge=1, description="最大输出token数")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="核采样概率")
    top_k: Optional[int] = Field(default=None, ge=1, description="Top-K采样")
    web_search_max_uses: int = Field(default=5, ge=1, le=20, description="Web搜索工具最大使用次数")
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )
    

class LLMSettings(BaseSettings):
    """LLM Configuration"""
    type: Literal["gpt", "gemini", "anthropic"] = Field(default="gemini", description="LLM type (gpt, gemini, anthropic)")
    debug: bool = Field(default=False, description="Enable debug mode")
    recent_messages_length: int = Field(default=20, ge=1, le=100, description="Number of recent messages to use for context")
    max_tool_iterations: int = Field(default=10, ge=1, le=50, description="Maximum number of tool calling iterations per request")
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='LLM__',
        extra='ignore'
    )
    
    def get_openai_config(self) -> OpenAIConfig:
        """Retrieve OpenAI configuration"""
        return OpenAIConfig()
    
    def get_gemini_config(self) -> GeminiConfig:
        """Retrieve Gemini configuration"""
        return GeminiConfig()
    
    def get_anthropic_config(self) -> AnthropicConfig:
        """Retrieve Anthropic configuration"""
        return AnthropicConfig()
    
    def get_current_llm_config(self):
        """Retrieve current LLM configuration based on type"""
        if self.type == "gpt":
            return self.get_openai_config()
        elif self.type == "gemini":
            return self.get_gemini_config()
        elif self.type == "anthropic":
            return self.get_anthropic_config()
        else:
            raise ValueError(f"Unsupported llm provider: {self.type}")
    
    def validate_current_llm(self):
        """Validate - fail fast"""
        try:
            config = self.get_current_llm_config()
            # Trigger fail-fast validation
            return config
        except Exception as e:
            raise ValueError(f"当前LLM配置验证失败: {e}")


def get_llm_settings() -> LLMSettings:
    """Retrieve LLM settings"""
    return LLMSettings() 

