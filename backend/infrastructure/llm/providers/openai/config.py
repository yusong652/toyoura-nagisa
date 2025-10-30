"""
OpenAI Client Configuration

Handles configuration settings for OpenAI GPT models including
model parameters, API settings, and debug options.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from backend.config import get_llm_settings


@dataclass
class OpenAIModelSettings:
    """OpenAI model-specific settings"""
    model: str = "gpt-4o-2024-11-20"  # Use specific version that supports function calling + vision
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    
    def to_api_params(self) -> Dict[str, Any]:
        """Convert to OpenAI API parameters"""
        # Responses API ignores frequency/presence penalties; omit for compatibility.
        params = {
            'model': self.model,
            'temperature': self.temperature,
            'top_p': self.top_p
        }
        
        if self.max_tokens is not None:
            params['max_output_tokens'] = self.max_tokens
            
        return params


@dataclass 
class OpenAIClientConfig:
    """Complete OpenAI client configuration"""
    model_settings: OpenAIModelSettings = field(default_factory=OpenAIModelSettings)
    debug: bool = False
    timeout: float = 30.0
    max_retries: int = 3
    
    def get_api_call_kwargs(
        self,
        *,
        instructions: Optional[str],
        input_items: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Build complete kwargs for OpenAI Responses API call.

        Args:
            instructions: System instructions to provide via Responses API.
            input_items: Conversation items formatted for Responses API.
            tools: Optional tool schemas in Responses API format.

        Returns:
            Dict containing all API call parameters.
        """
        kwargs: Dict[str, Any] = {
            "input": input_items,
            "timeout": self.timeout,
        }

        kwargs.update(self.model_settings.to_api_params())

        if instructions:
            kwargs["instructions"] = instructions

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        return kwargs


def get_openai_client_config(**overrides) -> OpenAIClientConfig:
    """
    Get OpenAI client configuration with optional overrides
    
    Args:
        **overrides: Configuration overrides
        
    Returns:
        OpenAIClientConfig instance
    """
    # Get base settings from global config
    llm_settings = get_llm_settings()
    
    # Build model settings
    model_settings_dict = {}
    if 'model_settings' in overrides:
        model_settings_dict.update(overrides['model_settings'])
    
    model_settings = OpenAIModelSettings(**model_settings_dict)
    
    # Build client config
    config_dict = {
        'model_settings': model_settings,
        'debug': overrides.get('debug', False),
        'timeout': overrides.get('timeout', 30.0),
        'max_retries': overrides.get('max_retries', 3)
    }
    
    return OpenAIClientConfig(**config_dict)
