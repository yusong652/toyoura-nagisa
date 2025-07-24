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
    
    # Thinking配置 - 为支持thinking的模型
    enable_thinking: bool = Field(
        default=True,
        description="Whether to enable thinking for supported models"
    )
    thinking_budget_tokens: int = Field(
        default=10000,
        ge=1000,
        le=50000,
        description="Budget tokens for thinking process"
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
    
    def supports_thinking(self) -> bool:
        """Check if the current model supports thinking"""
        return (
            self.model.startswith("claude-3-7-") or
            self.model.startswith("claude-sonnet-4-") or
            self.model.startswith("claude-4-") or
            self.model.startswith("claude-3-opus-")
        )


class AnthropicClientConfig(BaseModel):
    """Complete Anthropic client configuration"""
    
    # 模型配置
    model_settings: AnthropicModelConfig = Field(
        default_factory=AnthropicModelConfig,
        description="Model-specific configuration"
    )
    
    # 工具调用设置
    tools_enabled: bool = Field(
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
    debug: bool = Field(
        default=False,
        description="Enable debug logging"
    )
    log_requests: bool = Field(
        default=False,
        description="Log API requests and responses"
    )
    
    def get_api_call_kwargs(
        self, 
        system_prompt: str, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Get API call parameters for Anthropic messages.create
        
        Args:
            system_prompt: System prompt
            messages: Formatted messages for Anthropic API
            tools: Optional tool schemas
            
        Returns:
            Dict[str, Any]: API call parameters
        """
        kwargs = {
            "model": self.model_settings.model,
            "max_tokens": self.model_settings.max_tokens,
            "messages": messages,
            "system": system_prompt,
            "temperature": self.model_settings.temperature,
        }
        
        # Add optional parameters
        if self.model_settings.top_p is not None:
            kwargs["top_p"] = self.model_settings.top_p
        if self.model_settings.top_k is not None:
            kwargs["top_k"] = self.model_settings.top_k
        
        # Add tools if provided
        if tools and len(tools) > 0:
            kwargs["tools"] = tools
        
        # Add thinking configuration for supported models
        if (self.model_settings.supports_thinking() and 
            self.model_settings.enable_thinking):
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.model_settings.thinking_budget_tokens
            }
        
        return kwargs


# Default configuration instance
DEFAULT_ANTHROPIC_CONFIG = AnthropicClientConfig()


def get_anthropic_client_config(**overrides) -> AnthropicClientConfig:
    """
    Get Anthropic Client configuration, support runtime overrides
    
    Args:
        **overrides: Configuration items to override
        
    Returns:
        AnthropicClientConfig: Configuration instance
    """
    if not overrides:
        return DEFAULT_ANTHROPIC_CONFIG
    
    # Create configuration copy and apply overrides
    config_dict = DEFAULT_ANTHROPIC_CONFIG.model_dump()
    
    # Process nested configuration overrides
    for key, value in overrides.items():
        if key == "model_settings" and isinstance(value, dict):
            config_dict["model_settings"].update(value)
        else:
            config_dict[key] = value
    
    return AnthropicClientConfig(**config_dict)


# Backward compatibility alias
get_anthropic_config = get_anthropic_client_config