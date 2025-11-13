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
    openai_api_key: str = Field(default="", description="OpenAI API Key")
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
    google_api_key: str = Field(default="", description="Google API Key")
    model: str = Field(default="gemini-2.5-flash", description="Model name")
    temperature: float = Field(default=1.0, ge=0.0, le=2.0, description="Sampling temperature")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Nucleus sampling probability")
    top_k: Optional[int] = Field(default=None, ge=1, description="Top-K sampling")
    max_output_tokens: int = Field(default=8192, alias="maxOutputTokens", ge=1, description="Max output tokens")
    web_search_max_uses: int = Field(default=5, ge=1, le=20, description="Web search max uses")

    # Advanced Thinking Features (optional, uncomment to enable)
    # preserve_thinking_in_history: bool = Field(default=False, description="Preserve thinking content across sessions")
    # Benefits: (1) Cross-turn reasoning (2) Resume after restart (3) Tool call reasoning chains
    # Recommended for: PFC agent, domain-specific sessions with reasoning continuity needs

    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )


class AnthropicConfig(BaseSettings):
    """Anthropic Configuration"""
    anthropic_api_key: str = Field(default="", description="Anthropic API Key")
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


class KimiConfig(BaseSettings):
    """Kimi (Moonshot) Configuration"""

    # API Keys - 支持直连或 OpenRouter (至少需要配置一个)
    moonshot_api_key: Optional[str] = Field(default="", description="Moonshot 官方 API 密钥")
    openrouter_api_key: Optional[str] = Field(default="", description="OpenRouter API 密钥")

    # 使用哪个服务
    use_openrouter: bool = Field(default=False, description="是否使用 OpenRouter 中转")

    # OpenRouter 配置
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenRouter API base URL"
    )
    openrouter_http_referer: str = Field(
        default="https://github.com/yusong652/aiNagisa",
        description="OpenRouter HTTP Referer header"
    )
    openrouter_title: str = Field(
        default="aiNagisa Voice Assistant",
        description="OpenRouter X-Title header"
    )
    openrouter_model: str = Field(
        default="moonshotai/kimi-k2-thinking",
        description="OpenRouter 模型名称 (kimi-k2-thinking 支持 reasoning_content)"
    )

    # 有合理默认值的配置
    model: str = Field(default="kimi-k2-thinking", description="模型名称 (直连 Moonshot API)")
    # Direct API models:
    #   - kimi-k2-thinking: K2 Thinking model with reasoning_content field (推荐 temperature=0.6)
    #   - kimi-k2-0905-preview: Standard K2 model
    #   - kimi-k2-turbo-preview: Faster K2 variant
    #   - moonshot-v1-8k, moonshot-v1-32k, moonshot-v1-128k: Legacy Moonshot models
    # OpenRouter models:
    #   - moonshotai/kimi-k2-thinking: K2 Thinking via OpenRouter
    #   - moonshotai/kimi-k2-0905: Standard K2 via OpenRouter
    # Note: K2 Thinking models expose reasoning_content field with intermediate thinking steps
    # Kimi excels at long-context understanding (up to 200K tokens)
    temperature: float = Field(default=0.6, ge=0.0, le=1.0, description="采样温度 (推荐 0.6)")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="核采样概率")
    max_tokens: Optional[int] = Field(default=None, ge=1, description="最大输出token数")

    model_config = SettingsConfigDict(
        env_file='backend/.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )


class ZhipuConfig(BaseSettings):
    """Zhipu (智谱) Configuration"""
    zhipu_api_key: str = Field(default="", description="Zhipu API Key")
    model: str = Field(default="glm-4.6", description="模型名称")
    # Available models:
    #   - glm-4.6: GLM-4 Plus model (推荐，支持 thinking mode)
    #   - glm-4.5-air: GLM-4 Air model (fast and efficient)
    #   - glm-4-flash: GLM-4 Flash model (fastest)
    #   - glm-4-long: GLM-4 Long model (supports up to 1M tokens)
    # Note: GLM models support thinking mode (reasoning_content field)
    temperature: float = Field(default=0.6, ge=0.0, le=1.0, description="采样温度 (推荐，与 top_p 二选一)")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="核采样概率 (与 temperature 二选一)")
    max_tokens: Optional[int] = Field(default=None, ge=1, description="最大输出token数")
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )


class OpenRouterConfig(BaseSettings):
    """OpenRouter Configuration"""
    openrouter_api_key: str = Field(default="", description="OpenRouter API Key")
    model: str = Field(default="anthropic/claude-3.5-sonnet", description="模型名称")
    # Popular models on OpenRouter:
    #   - anthropic/claude-3.5-sonnet: Claude 3.5 Sonnet
    #   - openai/gpt-4-turbo: GPT-4 Turbo
    #   - google/gemini-pro: Gemini Pro
    #   - moonshotai/kimi-k2-thinking: Kimi K2 Thinking
    temperature: float = Field(default=1.0, ge=0.0, le=2.0, description="采样温度")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="核采样概率")
    max_tokens: Optional[int] = Field(default=None, ge=1, description="最大输出token数")
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )


class LLMSettings(BaseSettings):
    """LLM Configuration"""
    type: Literal["gpt", "gemini", "anthropic", "kimi", "zhipu", "openrouter"] = Field(
        default="gemini",
        description="LLM type (gpt, gemini, anthropic, kimi, zhipu, openrouter)"
    )
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

    def get_kimi_config(self) -> KimiConfig:
        """Retrieve Kimi configuration"""
        return KimiConfig()

    def get_zhipu_config(self) -> ZhipuConfig:
        """Retrieve Zhipu configuration"""
        return ZhipuConfig()

    def get_openrouter_config(self) -> OpenRouterConfig:
        """Retrieve OpenRouter configuration"""
        return OpenRouterConfig()

    def get_current_llm_config(self):
        """Retrieve current LLM configuration based on type"""
        if self.type == "gpt":
            return self.get_openai_config()
        elif self.type == "gemini":
            return self.get_gemini_config()
        elif self.type == "anthropic":
            return self.get_anthropic_config()
        elif self.type == "kimi":
            return self.get_kimi_config()
        elif self.type == "zhipu":
            return self.get_zhipu_config()
        elif self.type == "openrouter":
            return self.get_openrouter_config()
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

