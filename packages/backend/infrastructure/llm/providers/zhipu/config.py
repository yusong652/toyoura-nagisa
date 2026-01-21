"""
Zhipu (智谱) Client Configuration

Handles configuration settings for Zhipu GLM models including
model parameters, API settings, and debug options.

Uses official zai-sdk for API access.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from backend.config import get_llm_settings


class ZhipuConfig(BaseSettings):
    """Zhipu configuration loaded from environment variables."""

    zhipu_api_key: str = Field(description="Zhipu API key")
    model: str = Field(default="glm-4.7", description="Default model")
    secondary_model: str = Field(
        default="glm-4.7",
        description="Secondary model for SubAgent"
    )

    model_config = SettingsConfigDict(
        env_file='packages/backend/.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )


@dataclass
class ZhipuModelSettings:
    """Zhipu model-specific settings"""
    model: str = "glm-4.6"  # Default to GLM-4 Plus model
    temperature: Union[float, str] = 0.95  # Recommended temperature for Zhipu API (range: 0-1)
    max_tokens: Optional[Union[int, str]] = 1024*16
    top_p: Union[float, str] = 0.7

    # Zhipu-specific features
    # Models: glm-4-plus, glm-4-0520, glm-4, glm-4-air, glm-4-airx, glm-4-flash, glm-4-long
    # Note: glm-4-long supports up to 1M tokens context

    def to_api_params(self) -> Dict[str, Any]:
        """Convert to Zhipu API parameters (OpenAI-compatible format)"""
        params = {
            'model': self.model,
            'temperature': self.temperature,
            'top_p': self.top_p
        }

        if self.max_tokens is not None:
            params['max_tokens'] = self.max_tokens

        return params


@dataclass
class ZhipuClientConfig:
    """Complete Zhipu client configuration"""
    model_settings: ZhipuModelSettings = field(default_factory=ZhipuModelSettings)
    api_key: Optional[str] = None
    base_url: str = "https://open.bigmodel.cn/api/paas/v4/"
    debug: bool = False
    timeout: float = 60.0
    max_retries: int = 3

    def get_api_call_kwargs(
        self,
        *,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = True
    ) -> Dict[str, Any]:
        """
        Build complete kwargs for Zhipu API call (OpenAI-compatible).

        Args:
            messages: Conversation messages in OpenAI format.
            tools: Optional tool schemas in OpenAI format.
            stream: Whether to stream the response.

        Returns:
            Dict containing all API call parameters.
        """
        kwargs: Dict[str, Any] = {
            "messages": messages,
            "stream": stream,
            "timeout": self.timeout,
        }

        kwargs.update(self.model_settings.to_api_params())

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        return kwargs


def get_zhipu_client_config(**overrides: Any) -> ZhipuClientConfig:
    """
    Get Zhipu client configuration with optional overrides

    Args:
        **overrides: Configuration overrides

    Returns:
        ZhipuClientConfig instance
    """
    # Get base settings from global config
    llm_settings = get_llm_settings()

    # Check if there's a zhipu_config method, otherwise use defaults
    try:
        zhipu_config = llm_settings.get_zhipu_config()
        model = zhipu_config.model
        api_key = zhipu_config.zhipu_api_key
    except (AttributeError, KeyError):
        # Fallback to defaults if zhipu config not available
        model = "glm-4.6"
        api_key = None

    model_settings = ZhipuModelSettings()
    model_settings.model = model

    model_overrides = overrides.get('model_settings')
    if isinstance(model_overrides, dict):
        for key, value in model_overrides.items():
            setattr(model_settings, key, value)

    # Build client config
    config_dict: Dict[str, Any] = {
        'model_settings': model_settings,
        'api_key': overrides.get('api_key', api_key),
        'base_url': overrides.get('base_url', "https://open.bigmodel.cn/api/paas/v4/"),
        'debug': overrides.get('debug', llm_settings.debug),
        'timeout': overrides.get('timeout', 60.0),
        'max_retries': overrides.get('max_retries', 3)
    }

    return ZhipuClientConfig(**config_dict)
