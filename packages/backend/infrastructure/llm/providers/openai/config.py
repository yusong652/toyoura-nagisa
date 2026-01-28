"""
OpenAI Client Configuration

Unified configuration for OpenAI GPT models including API credentials,
model parameters, and client settings.
"""

from typing import Dict, Any, List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class OpenAIConfig(BaseSettings):
    """
    Unified OpenAI configuration.

    Combines environment variable loading (API keys) with
    runtime-overridable parameters (model, temperature, etc.).

    Available Models:
    - gpt-5-mini-2025-08-07: Latest GPT-5 Mini (recommended for most tasks)
    - gpt-5-2025-08-07: GPT-5 full model
    - gpt-4o: GPT-4 Omni with vision
    - o1, o3: Reasoning models
    """

    # API credentials (from environment variables)
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")

    # Model selection (from environment variables, runtime overridable)
    model: str = Field(default="gpt-5-mini-2025-08-07", description="Default model")
    secondary_model: str = Field(default="gpt-5-mini-2025-08-07", description="Secondary model for SubAgent")

    # Model parameters (runtime overridable)
    temperature: Optional[float] = Field(
        default=None, ge=0.0, le=2.0, description="Sampling temperature. Do not set both temperature and top_p."
    )
    max_tokens: Optional[int] = Field(default=1024 * 16, description="Maximum tokens to generate")
    top_p: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Nucleus sampling threshold. Do not set both temperature and top_p."
    )

    # Reasoning configuration (for reasoning models like o1, o3, gpt-5)
    reasoning_effort: Optional[str] = Field(
        default=None, description="Reasoning effort: minimal, medium, high (for reasoning models)"
    )

    # Client settings (runtime overridable)
    timeout: float = Field(default=120.0, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum number of retries for failed requests")

    def build_api_params(self) -> Dict[str, Any]:
        """
        Convert configuration fields to OpenAI API parameters.
        Renames fields as required by the API (e.g., max_tokens -> max_output_tokens).
        """
        params: Dict[str, Any] = {
            "model": self.model,
        }

        if self.temperature is not None:
            params["temperature"] = self.temperature
        if self.top_p is not None:
            params["top_p"] = self.top_p
        if self.max_tokens is not None:
            params["max_output_tokens"] = self.max_tokens
        
        # Note: reasoning effort is typically handled separately in client.py 
        # to support runtime overrides via call_options
        if self.reasoning_effort:
            params["reasoning"] = {"effort": self.reasoning_effort}

        return params
