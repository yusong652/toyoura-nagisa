"""
LLM配置模块
包含所有大语言模型相关的配置
"""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict



class LLMSettings(BaseSettings):
    """LLM总配置 - 简化版本"""
    
    # 当前使用的LLM类型
    provider: Literal["openai", "gemini", "anthropic", "local_llm", "kimi", "openrouter", "zhipu"] = Field(
        default="gemini",
        description="current LLM provider"
    )
    debug: bool = Field(default=True, description="debug mode")
    recent_messages_length: int = Field(default=23, ge=1, le=100, description="Number of recent messages to use for context")
    max_tool_iterations: int = Field(default=23, ge=1, le=50, description="Maximum number of tool calling iterations per request")
    
    model_config = SettingsConfigDict(
        env_file='backend/.env',
        env_nested_delimiter='_',
        case_sensitive=False,
        env_prefix='LLM_',
        extra='ignore'
    )
    
    def get_openai_config(self) -> OpenAIConfig:
        """获取OpenAI配置"""
        return OpenAIConfig() # type: ignore
    
    def get_gemini_config(self) -> GeminiConfig:
        """获取Gemini配置"""
        return GeminiConfig() # type: ignore
    
    def get_anthropic_config(self) -> AnthropicConfig:
        """获取Anthropic配置"""
        return AnthropicConfig() # type: ignore

    def get_kimi_config(self) -> KimiConfig:
        """获取Kimi配置"""
        return KimiConfig() # type: ignore

    def get_openrouter_config(self) -> OpenRouterConfig:
        """获取OpenRouter配置"""
        return OpenRouterConfig() # type: ignore

    def get_zhipu_config(self) -> ZhipuConfig:
        """获取Zhipu配置"""
        return ZhipuConfig() # type: ignore

    def get_local_llm_config(self) -> LocalLLMConfig:
        """获取本地LLM配置"""
        return LocalLLMConfig()
    
    def get_current_llm_config(self):
        """
        获取当前LLM配置。
        
        Returns:
            当前provider对应的配置对象
        """
        config_map = {
            "openai": self.get_openai_config,
            "gemini": self.get_gemini_config,
            "anthropic": self.get_anthropic_config,
            "kimi": self.get_kimi_config,
            "openrouter": self.get_openrouter_config,
            "zhipu": self.get_zhipu_config,
            "local_llm": self.get_local_llm_config
        }
        
        config_getter = config_map.get(self.provider)
        if not config_getter:
            raise ValueError(f"不支持的LLM类型: {self.provider}")
        
        return config_getter()
    
    def validate_current_llm(self):
        """
        验证当前LLM配置 - 实现fail fast。
        
        Returns:
            验证通过的配置对象
            
        Raises:
            ValueError: 配置验证失败时
        """
        try:
            config = self.get_current_llm_config()
            # 这里会触发API密钥验证
            return config
        except Exception as e:
            raise ValueError(f"当前LLM配置验证失败: {e}")
    
    def get_current_model(self) -> str:
        """
        获取当前LLM provider使用的模型名称。
        
        Returns:
            当前使用的模型名称
        """
        config = self.get_current_llm_config()
        return config.model


class OpenAIConfig(BaseSettings):
    """OpenAI配置"""

    # 必需的敏感信息 - 字段名直接匹配环境变量OPENAI_API_KEY
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API密钥")

    # 有合理默认值的配置
    model: str = Field(default="gpt-5", description="模型名称")
    # (gpt-4o-2024-11-20, o3-2025-04-16, gpt-4.1-2025-04-14, gpt-4.1-mini-2025-04-14)
    temperature: float = Field(default=1.0, ge=0.0, le=2.0, description="采样温度")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="核采样概率")
    top_k: Optional[int] = Field(default=None, ge=1, description="Top-K采样")
    max_tokens: Optional[int] = Field(default=None, ge=1, description="最大输出token数")
    reasoning_effort: str = Field(default="minimal", description="推理努力程度: minimal, medium, high")
    
    model_config = SettingsConfigDict(
        env_file='backend/.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )

class GeminiConfig(BaseSettings):
    """Gemini配置"""
    
    # 必需的敏感信息 - 字段名直接匹配环境变量GOOGLE_API_KEY
    google_api_key: str = Field(description="Google API密钥")
    
    # 有合理默认值的配置
    model: str = Field(default="gemini-3-pro-preview", description="模型名称") 
    # (gemini-3-pro-preview, gemini-2.5-pro, gemini-2.5-pro-preview-06-05, gemini-2.5-pro-preview-05-06,
    # gemini-2.5-flash, gemini-2.5-flash-preview-05-20, gemini-2.5-flash-preview-09-2025,
    # gemini-2.5-flash-lite-preview-06-17, gemini-2.5-flash-lite-preview-09-2025
    # gemini-2.0-flash, gemini-2.0-flash-001,
    # gemini-1.5-pro)
    temperature: float = Field(default=1.0, ge=0.0, le=2.0, description="采样温度")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="核采样概率")
    top_k: Optional[int] = Field(default=None, ge=1, description="Top-K采样")
    max_output_tokens: int = Field(default=1024*16, alias="maxOutputTokens", ge=1, description="最大输出token数")
    web_search_max_uses: int = Field(default=10, alias="webSearchMaxUses", ge=1, le=20, description="Web搜索最大使用次数")
    model_config = SettingsConfigDict(
        env_file='backend/.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )

class AnthropicConfig(BaseSettings):
    """Anthropic配置"""
    
    # 必需的敏感信息 - 字段名直接匹配环境变量ANTHROPIC_API_KEY
    anthropic_api_key: str = Field(description="Anthropic API密钥")
    
    # 有合理默认值的配置
    model: str = Field(default="claude-sonnet-4-5-20250929", description="模型名称") # claude-3-5-sonnet-20241022, claude-sonnet-4-20250514, claude-sonnet-4-5-20250929
    temperature: float = Field(default=1.0, ge=0.0, le=2.0, description="采样温度")
    max_tokens: int = Field(default=8192, ge=1, description="最大输出token数")
    web_search_max_uses: int = Field(default=10, alias="webSearchMaxUses", ge=1, le=20, description="Web搜索最大使用次数")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="核采样概率")
    top_k: Optional[int] = Field(default=None, ge=1, description="Top-K采样")
    
    model_config = SettingsConfigDict(
        env_file='backend/.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )

class KimiConfig(BaseSettings):
    """Kimi (Moonshot) 配置"""

    # API Keys - 支持直连或 OpenRouter
    moonshot_api_key: Optional[str] = Field(default=None, description="Moonshot 官方 API 密钥")

    # 有合理默认值的配置
    model: str = Field(default="kimi-k2-thinking", description="模型名称 (直连 Moonshot API)")
    # Direct API models: kimi-k2-0905-preview, kimi-k2-turbo-preview, kimi-k2-thinking
    # OpenRouter models: moonshotai/kimi-k2-0905
    temperature: float = Field(default=0.6, ge=0.0, le=1.0, description="采样温度")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="核采样概率")
    max_tokens: Optional[int] = Field(default=None, ge=1, description="最大输出token数")

    model_config = SettingsConfigDict(
        env_file='backend/.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )

class OpenRouterConfig(BaseSettings):
    """OpenRouter 通用配置 - 支持任意模型"""

    # API Key - 必需
    openrouter_api_key: str = Field(description="OpenRouter API密钥")

    # 模型配置 - 支持任意 OpenRouter 模型
    model: str = Field(
        default="x-ai/grok-4.1-fast",
        description="OpenRouter 模型名称"
    )
    # 常用模型示例:
    # - google/gemini-2.5-pro
    # - moonshotai/kimi-k2-0905
    # - deepseek/deepseek-chat
    # - x-ai/grok-4.1-fast
    # - x-ai/grok-4-fast
    # - x-ai/grok-3-mini
    # - x-ai/grok-code-fast-1
    # - z-ai/glm-4.6
    # - qwen/qwen3-235b-a22b-2507
    # - deepseek/deepseek-v3.2-exp
    # thedrummer/cydonia-24b-v4.1
    # 完整列表: https://openrouter.ai/models

    # OpenRouter 专用 headers
    openrouter_http_referer: str = Field(
        default="https://github.com/yusong652/aiNagisa",
        description="OpenRouter 请求所需的 HTTP-Referer 头"
    )
    openrouter_title: str = Field(
        default="aiNagisa Voice Assistant",
        description="OpenRouter 请求所需的 X-Title 头"
    )

    # 标准生成参数
    temperature: float = Field(default=1.0, ge=0.0, le=2.0, description="采样温度")
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
    """Zhipu (智谱) 配置"""

    # API Key - 必需
    zhipu_api_key: str = Field(description="智谱 API密钥")

    # 模型配置
    model: str = Field(
        default="glm-4.6",
        description="智谱模型名称"
    )
    # 可用模型:
    # - glm-4.6: 最强大的版本，适合复杂任务
    # - glm-4.5: 适合大多数任务的平衡版本
    # - glm-4.5-air: 适合轻量级任务的基础版本
    # - glm-4.5v: 视觉模型，支持图像输入
    # 完整列表: https://bigmodel.cn/console/modelcenter/square

    # 标准生成参数
    temperature: float = Field(default=0.6, ge=0.0, le=1.0, description="采样温度")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="核采样概率")
    max_tokens: Optional[int] = Field(default=None, ge=8192, description="最大输出token数")

    model_config = SettingsConfigDict(
        env_file='backend/.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )

class LocalLLMConfig(BaseSettings):
    """本地LLM配置"""

    # 本地LLM服务器配置
    enabled: bool = Field(default=False, description="是否启用本地LLM客户端")
    server_url: str = Field(default="https://your-workstation.com:8000", description="本地LLM服务器URL")
    api_key: Optional[str] = Field(default=None, description="API密钥(如果需要认证)")
    model: str = Field(default="default", description="默认模型名称")
    timeout: float = Field(default=120.0, ge=1.0, description="请求超时时间(秒)")

    # 生成参数
    temperature: float = Field(default=0.6, ge=0.0, le=2.0, description="采样温度")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="核采样概率")
    max_tokens: int = Field(default=4000, ge=1, description="最大输出token数")

    model_config = SettingsConfigDict(
        env_file='backend/.env',
        env_nested_delimiter='_',
        case_sensitive=False,
        env_prefix='LOCAL_LLM_',
        extra='ignore'
    )


# 全局LLM配置实例
# 注意：这里不直接实例化，而是在需要时进行实例化以支持fail fast
def get_llm_settings() -> LLMSettings:
    """获取LLM配置实例"""
    return LLMSettings() 
