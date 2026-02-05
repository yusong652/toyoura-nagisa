"""
OpenAI Codex Client Configuration

Configuration for OpenAI Codex models using OAuth authentication.
Uses ChatGPT Pro/Plus subscription for API access.
"""

from typing import Dict, Any, Optional
from pydantic import Field
from pydantic_settings import BaseSettings


# Available Codex models (included with ChatGPT subscription)
CODEX_MODELS = [
    "gpt-5.1-codex",
    "gpt-5.1-codex-mini",
    "gpt-5.1-codex-max",
    "gpt-5.2",
    "gpt-5.2-codex",
]

# Default model
DEFAULT_CODEX_MODEL = "gpt-5.1-codex"


class OpenAICodexConfig(BaseSettings):
    """
    OpenAI Codex configuration.

    Uses OAuth authentication instead of API keys.
    Models are included with ChatGPT Pro/Plus subscription (no additional cost).

    Available Models:
    - gpt-5.1-codex: Standard Codex model (recommended)
    - gpt-5.1-codex-mini: Smaller, faster Codex model
    - gpt-5.1-codex-max: Larger Codex model with extended context
    - gpt-5.2: GPT-5.2 model
    - gpt-5.2-codex: GPT-5.2 Codex variant
    """

    # OAuth account (from environment variables or runtime)
    oauth_account_id: Optional[str] = Field(
        default=None,
        description="OAuth account ID to use (defaults to default account)"
    )

    # Model selection
    model: str = Field(
        default=DEFAULT_CODEX_MODEL,
        description="Codex model to use"
    )
    secondary_model: str = Field(
        default=DEFAULT_CODEX_MODEL,
        description="Secondary model for SubAgent"
    )

    # Model parameters (runtime overridable)
    temperature: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Sampling temperature"
    )
    top_p: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling threshold"
    )

    # Reasoning configuration (for reasoning models)
    reasoning_effort: Optional[str] = Field(
        default=None,
        description="Reasoning effort: minimal, medium, high"
    )

    # Client settings
    timeout: float = Field(
        default=120.0,
        description="Request timeout in seconds"
    )
    max_retries: int = Field(
        default=3,
        description="Maximum number of retries for failed requests"
    )

    def build_api_params(self) -> Dict[str, Any]:
        """
        Convert configuration fields to OpenAI API parameters.
        """
        params: Dict[str, Any] = {
            "model": self.model,
        }

        if self.temperature is not None:
            params["temperature"] = self.temperature
        if self.top_p is not None:
            params["top_p"] = self.top_p

        # Base reasoning config
        reasoning_config = {}
        if self.reasoning_effort:
            reasoning_config["effort"] = self.reasoning_effort
            # Default to detailed summary if effort is specified
            reasoning_config["summary"] = "detailed"
            
        if reasoning_config:
            params["reasoning"] = reasoning_config
            # Opt-in to reasoning output items
            # Matching codex-rs: vec!["reasoning.encrypted_content".to_string()]
            params["include"] = ["reasoning.encrypted_content", "reasoning.text"]

        return params

    def is_valid_model(self, model: str) -> bool:
        """Check if the model is a valid Codex model."""
        return model in CODEX_MODELS

    @classmethod
    def get_available_models(cls) -> list[str]:
        """Get list of available Codex models."""
        return CODEX_MODELS.copy()
