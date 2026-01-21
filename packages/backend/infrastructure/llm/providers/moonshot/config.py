"""
Moonshot (Moonshot) Client Configuration

Handles configuration settings for Moonshot/Moonshot models including
model parameters, API settings, and debug options.

Moonshot uses OpenAI-compatible API format with base URL: https://api.moonshot.ai/v1
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from backend.config import get_llm_settings


@dataclass
class MoonshotModelSettings:
    """Moonshot model-specific settings"""
    model: str = "kimi-k2-thinking"  # Default to K2 Thinking model with reasoning support
    temperature: float = 0.6  # Recommended temperature for Moonshot API (range: 0-1)
    max_tokens: Optional[int] = 1024*16
    top_p: float = 1.0

    # Moonshot-specific features
    # Models: kimi-k2-thinking, kimi-k2-0905-preview, kimi-k2-turbo-preview,
    #         moonshot-v1-8k, moonshot-v1-32k, moonshot-v1-128k
    # Note: Moonshot excels at long-context understanding (up to 200K tokens)
    # K2 Thinking models expose reasoning_content field with intermediate thinking steps

    def to_api_params(self) -> Dict[str, Any]:
        """Convert to Moonshot API parameters (OpenAI-compatible format)"""
        params = {
            'model': self.model,
            'temperature': self.temperature,
            'top_p': self.top_p
        }

        if self.max_tokens is not None:
            params['max_tokens'] = self.max_tokens

        return params


@dataclass
class MoonshotClientConfig:
    """Complete Moonshot client configuration"""
    model_settings: MoonshotModelSettings = field(default_factory=MoonshotModelSettings)
    api_key: Optional[str] = None
    base_url: str = "https://api.moonshot.ai/v1"
    debug: bool = False
    timeout: float = 60.0  # Longer timeout for long-context processing
    max_retries: int = 3

    def get_api_call_kwargs(
        self,
        *,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = True
    ) -> Dict[str, Any]:
        """
        Build complete kwargs for Moonshot API call (OpenAI-compatible).

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


def get_moonshot_client_config(**overrides) -> MoonshotClientConfig:
    """
    Get Moonshot client configuration with optional overrides.

    Args:
        **overrides: Configuration overrides

    Returns:
        MoonshotClientConfig instance
    """
    llm_settings = get_llm_settings()

    # Get Moonshot config from settings
    try:
        moonshot_config = llm_settings.get_moonshot_config()
        model = moonshot_config.model
        api_key = moonshot_config.moonshot_api_key
    except (AttributeError, KeyError):
        # Fallback to defaults
        model = "kimi-k2-0905-preview"
        api_key = None

    # Build model settings
    model_settings_dict = {
        'model': model,
    }

    # Apply overrides to model settings
    if 'model_settings' in overrides:
        model_settings_dict.update(overrides['model_settings'])

    model_settings = MoonshotModelSettings(**model_settings_dict)

    # Build client config
    return MoonshotClientConfig(
        model_settings=model_settings,
        api_key=overrides.get('api_key', api_key),
        base_url=overrides.get('base_url', "https://api.moonshot.ai/v1"),
        debug=overrides.get('debug', llm_settings.debug),
        timeout=overrides.get('timeout', 60.0),
        max_retries=overrides.get('max_retries', 3)
    )
