"""
Google Client Configuration

Unified configuration for Google Gemini models including API credentials,
model parameters, safety settings, and client settings.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from google.genai import types
from backend.infrastructure.llm.shared.constants.thinking import GOOGLE_THINKING_LEVEL_TO_BUDGET


class GoogleSafetySettings(BaseModel):
    """Google safety settings"""

    sexually_explicit_threshold: types.HarmBlockThreshold = Field(
        default=types.HarmBlockThreshold.BLOCK_NONE, description="Sexually explicit content blocking threshold"
    )
    harassment_threshold: types.HarmBlockThreshold = Field(
        default=types.HarmBlockThreshold.BLOCK_NONE, description="Harassment content blocking threshold"
    )
    dangerous_content_threshold: types.HarmBlockThreshold = Field(
        default=types.HarmBlockThreshold.BLOCK_NONE, description="Dangerous content blocking threshold"
    )
    hate_speech_threshold: types.HarmBlockThreshold = Field(
        default=types.HarmBlockThreshold.BLOCK_NONE, description="Hate speech blocking threshold"
    )

    def to_gemini_format(self) -> List[types.SafetySetting]:
        """Convert to Google API format safety settings"""
        return [
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=self.sexually_explicit_threshold
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=self.harassment_threshold
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=self.dangerous_content_threshold
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=self.hate_speech_threshold
            ),
        ]


class GoogleConfig(BaseSettings):
    """
    Unified Google (Gemini) configuration.

    Combines environment variable loading (API keys) with
    runtime-overridable parameters (model, temperature, etc.).

    Available Models:
    - gemini-3-flash-preview: Latest Gemini 3 Flash (recommended for most tasks)
    - gemini-3-thinking-preview: Gemini 3 with advanced reasoning
    - gemini-2.5-flash: Fast and efficient Gemini 2.5 Flash
    - gemini-2.5-pro: Most capable Gemini 2.5 Pro
    """

    # API credentials (from environment variables)
    google_api_key: Optional[str] = Field(default=None, description="Google API key")

    # Model selection (from environment variables, runtime overridable)
    model: str = Field(default="gemini-3-flash-preview", description="Default model")
    secondary_model: str = Field(default="gemini-3-flash-preview", description="Secondary model for SubAgent")

    # Model parameters (runtime overridable)
    temperature: float = Field(
        default=2.0, ge=0.0, le=2.0, description="Sampling temperature. Do not set both temperature and top_p."
    )
    max_tokens: int = Field(default=1024 * 16, ge=1, description="Maximum output token number")
    top_p: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Top-P sampling probability. Do not set both temperature and top_p."
    )
    top_k: Optional[int] = Field(default=None, ge=1, description="Top-K sampling")

    # Thinking configuration (for models that support thinking)
    default_thinking_level: str = Field(
        default="high", description="Default thinking level: 'default' (disabled), 'low', or 'high'"
    )

    # Safety settings (nested configuration for Google-specific types)
    safety_settings: GoogleSafetySettings = Field(
        default_factory=GoogleSafetySettings, description="Google safety settings"
    )

    # Client settings (runtime overridable)
    timeout: float = Field(default=60.0, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum number of retries for failed requests")

    # Tool settings
    tools_enabled: bool = Field(default=True, description="Enable tool calling functionality")

    def build_api_params(self) -> Dict[str, Any]:
        """
        Convert configuration fields to Google API format parameters.
        """
        params: Dict[str, Any] = {
            "temperature": self.temperature,
            "max_output_tokens": self.max_tokens,
            "safety_settings": self.safety_settings.to_gemini_format(),
        }

        if self.top_p is not None:
            params["top_p"] = self.top_p
        if self.top_k is not None:
            params["top_k"] = self.top_k

        # Add default thinking configuration based on model version
        if self.default_thinking_level and self.default_thinking_level != "default":
            if self.model.startswith("gemini-3"):
                # Gemini 3 models use thinking_level enum
                level_map = {"low": types.ThinkingLevel.LOW, "high": types.ThinkingLevel.HIGH}
                thinking_level = level_map.get(self.default_thinking_level, types.ThinkingLevel.HIGH)
                params["thinking_config"] = types.ThinkingConfig(
                    thinking_level=thinking_level,
                    include_thoughts=True
                )
            elif self.model.startswith("gemini-2.5"):
                # Gemini 2.5 models use thinking_budget
                budget = GOOGLE_THINKING_LEVEL_TO_BUDGET.get(self.default_thinking_level, -1)
                params["thinking_config"] = types.ThinkingConfig(
                    thinking_budget=budget,
                    include_thoughts=True
                )

        return params
