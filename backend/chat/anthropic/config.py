"""
Anthropic Client Configuration Module

This module contains all Anthropic-specific configuration settings,
including safety settings, model parameters, and other Anthropic-specific options.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class AnthropicModelConfig(BaseModel):
    """Anthropic model configuration"""
    
    # 模型参数
    model: str = Field(
        default="claude-3-5-sonnet-20241022",  # 平衡性能和成本的优秀选择
        description="Claude model to use"
    )
    max_tokens: int = Field(
        default=4096,
        ge=1,
        le=64000,  # Claude 4 系列支持更高输出限制
        description="Maximum number of tokens to generate"
    )
    temperature: float = Field(
        default=1.0,
        ge=0.0,
        le=2.0,
        description="Sampling temperature"
    )
    top_p: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling parameter"
    )
    top_k: Optional[int] = Field(
        default=None,
        ge=1,
        description="Top-K sampling parameter"
    )
    
    # API设置
    api_version: str = Field(
        default="2023-06-01",
        description="Anthropic API version"
    )
    timeout: int = Field(
        default=60,
        ge=1,
        description="Request timeout in seconds"
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum number of retries for failed requests"
    )


class AnthropicClientConfig(BaseModel):
    """Complete Anthropic client configuration"""
    
    model_config_data: AnthropicModelConfig = Field(
        default_factory=AnthropicModelConfig,
        description="Model-specific configuration"
    )
    
    # 工具调用设置
    enable_tools: bool = Field(
        default=True,
        description="Enable tool calling functionality"
    )
    max_tool_iterations: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of tool call iterations"
    )
    tool_timeout: int = Field(
        default=30,
        ge=1,
        description="Tool execution timeout in seconds"
    )
    
    # 调试设置
    debug_mode: bool = Field(
        default=False,
        description="Enable debug logging"
    )
    log_requests: bool = Field(
        default=False,
        description="Log API requests and responses"
    )


def get_anthropic_config(**overrides) -> AnthropicClientConfig:
    """
    Get Anthropic client configuration with optional overrides
    
    Args:
        **overrides: Configuration overrides
        
    Returns:
        AnthropicClientConfig: Complete configuration object
    """
    return AnthropicClientConfig(**overrides)