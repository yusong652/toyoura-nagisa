"""
LLM配置模块
包含所有大语言模型相关的配置
"""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class GPTConfig(BaseSettings):
    """GPT配置"""
    
    # 必需的敏感信息 - 字段名直接匹配环境变量OPENAI_API_KEY
    openai_api_key: str = Field(description="OpenAI API密钥")
    
    # 有合理默认值的配置
    model: str = Field(default="gpt-4o-2024-08-06", description="模型名称")
    temperature: float = Field(default=1.0, ge=0.0, le=2.0, description="采样温度")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="核采样概率")
    top_k: Optional[int] = Field(default=None, ge=1, description="Top-K采样")
    max_tokens: Optional[int] = Field(default=None, ge=1, description="最大输出token数")
    
    model_config = SettingsConfigDict(
        env_file='.env',
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
    model: str = Field(default="gemini-2.5-flash", description="模型名称")
    temperature: float = Field(default=1.0, ge=0.0, le=2.0, description="采样温度")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="核采样概率")
    top_k: Optional[int] = Field(default=None, ge=1, description="Top-K采样")
    max_output_tokens: int = Field(default=8192, alias="maxOutputTokens", ge=1, description="最大输出token数")
    web_search_max_uses: int = Field(default=5, ge=1, le=20, description="Web搜索工具最大使用次数(注意:Gemini忽略此参数)")
    
    model_config = SettingsConfigDict(
        env_file='.env',
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
    """LLM总配置"""
    
    # 当前使用的LLM类型
    type: Literal["gpt", "gemini", "anthropic"] = Field(default="gemini", description="当前使用的LLM类型")
    debug: bool = Field(default=False, description="是否开启调试模式")
    recent_messages_length: int = Field(default=20, ge=1, le=100, description="Number of recent messages to use for context (recent 消息条数)")
    # 各个LLM的配置 - 使用动态实例化以支持fail fast
    model_config = SettingsConfigDict(
        env_file='.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='LLM__',
        extra='ignore'
    )
    
    def get_gpt_config(self) -> GPTConfig:
        """获取GPT配置"""
        return GPTConfig()
    
    def get_gemini_config(self) -> GeminiConfig:
        """获取Gemini配置"""
        return GeminiConfig()
    
    def get_anthropic_config(self) -> AnthropicConfig:
        """获取Anthropic配置"""
        return AnthropicConfig()
    
    def get_current_llm_config(self):
        """获取当前LLM配置"""
        if self.type == "gpt":
            return self.get_gpt_config()
        elif self.type == "gemini":
            return self.get_gemini_config()
        elif self.type == "anthropic":
            return self.get_anthropic_config()
        else:
            raise ValueError(f"不支持的LLM类型: {self.type}")
    
    def validate_current_llm(self):
        """验证当前LLM配置 - 实现fail fast"""
        try:
            config = self.get_current_llm_config()
            # 这里会触发API密钥验证
            return config
        except Exception as e:
            raise ValueError(f"当前LLM配置验证失败: {e}")


# 全局LLM配置实例
# 注意：这里不直接实例化，而是在需要时进行实例化以支持fail fast
def get_llm_settings() -> LLMSettings:
    """获取LLM配置实例"""
    return LLMSettings() 