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
        params = {
            'model': self.model,
            'temperature': self.temperature,
            'top_p': self.top_p,
            'frequency_penalty': self.frequency_penalty,
            'presence_penalty': self.presence_penalty
        }
        
        if self.max_tokens is not None:
            params['max_tokens'] = self.max_tokens
            
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
        system_prompt: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Build complete kwargs for OpenAI API call
        
        Args:
            system_prompt: System instruction
            messages: Formatted message history
            tools: Optional tool schemas
            
        Returns:
            Dict containing all API call parameters
        """
        # Insert system prompt as first message
        api_messages = [{"role": "system", "content": system_prompt}] + messages
        
        # Build base parameters
        kwargs = {
            "messages": api_messages,
            "timeout": self.timeout,
            **self.model_settings.to_api_params()
        }
        
        # Add tools if provided
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