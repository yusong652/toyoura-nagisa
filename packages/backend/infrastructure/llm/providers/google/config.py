"""
Google Client Configuration

Unified configuration for Google Gemini models including API credentials,
model parameters, safety settings, and client settings.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from google.genai import types


class GoogleSafetySettings(BaseModel):
    """Google safety settings"""

    sexually_explicit_threshold: types.HarmBlockThreshold = Field(
        default=types.HarmBlockThreshold.BLOCK_NONE,
        description="Sexually explicit content blocking threshold"
    )
    harassment_threshold: types.HarmBlockThreshold = Field(
        default=types.HarmBlockThreshold.BLOCK_NONE,
        description="Harassment content blocking threshold"
    )
    dangerous_content_threshold: types.HarmBlockThreshold = Field(
        default=types.HarmBlockThreshold.BLOCK_NONE,
        description="Dangerous content blocking threshold"
    )
    hate_speech_threshold: types.HarmBlockThreshold = Field(
        default=types.HarmBlockThreshold.BLOCK_NONE,
        description="Hate speech blocking threshold"
    )

    def to_gemini_format(self) -> List[types.SafetySetting]:
        """Convert to Google API format safety settings"""
        return [
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=self.sexually_explicit_threshold
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=self.harassment_threshold
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=self.dangerous_content_threshold
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=self.hate_speech_threshold
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
    model: str = Field(
        default="gemini-3-flash-preview",
        description="Default model"
    )
    secondary_model: str = Field(
        default="gemini-3-flash-preview",
        description="Secondary model for SubAgent"
    )

    # Model parameters (runtime overridable)
    temperature: float = Field(
        default=2.0,
        ge=0.0,
        le=2.0,
        description="Sampling temperature. Do not set both temperature and top_p."
    )
    max_tokens: int = Field(
        default=1024*16,
        ge=1,
        description="Maximum output token number"
    )
    top_p: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Top-P sampling probability. Do not set both temperature and top_p."
    )
    top_k: Optional[int] = Field(
        default=None,
        ge=1,
        description="Top-K sampling"
    )

    # Thinking configuration (for models that support thinking)
    enable_thinking: bool = Field(
        default=True,
        description="Whether to enable thinking mode for supported models (Gemini 2.5+, Gemini 3+)"
    )
    include_thoughts_in_response: bool = Field(
        default=True,
        description="Whether to include thinking process in the response"
    )

    # Safety settings (nested configuration for Google-specific types)
    safety_settings: GoogleSafetySettings = Field(
        default_factory=GoogleSafetySettings,
        description="Google safety settings"
    )

    # Client settings (runtime overridable)
    debug: bool = Field(
        default=False,
        description="Enable debug logging"
    )
    timeout: float = Field(
        default=60.0,
        description="Request timeout in seconds"
    )
    max_retries: int = Field(
        default=3,
        description="Maximum number of retries for failed requests"
    )

    # Tool settings
    tools_enabled: bool = Field(
        default=True,
        description="Enable tool calling functionality"
    )

    model_config = SettingsConfigDict(
        env_file='packages/backend/.env',
        env_nested_delimiter='__',
        case_sensitive=False,
        env_prefix='',
        extra='ignore'
    )

    def to_api_params(self) -> Dict[str, Any]:
        """
        Convert model parameters to Google API format.

        Returns:
            Dict with model parameters (temperature, max_output_tokens, top_p, top_k)
        """
        params = {
            "temperature": self.temperature,
            "max_output_tokens": self.max_tokens,
        }

        if self.top_p is not None:
            params["top_p"] = self.top_p
        if self.top_k is not None:
            params["top_k"] = self.top_k

        return params

    def get_api_call_kwargs(
        self,
        system_prompt: str,
        tool_schemas: Optional[List[types.Tool]]
    ) -> Dict[str, Any]:
        """
        Get GenerateContentConfig parameters for Google API

        Args:
            system_prompt: System prompt
            tool_schemas: Tool schemas list

        Returns:
            Dict[str, Any]: GenerateContentConfig parameters
        """
        config_kwargs = {
            "system_instruction": system_prompt,
            "safety_settings": self.safety_settings.to_gemini_format(),
        }

        config_kwargs.update(self.to_api_params())

        # Add tool schemas
        if tool_schemas:
            config_kwargs["tools"] = tool_schemas

        # Add thinking configuration based on model version
        if self.enable_thinking:
            # Gemini 3 models use thinking_level parameter (enum)
            if self.model.startswith("gemini-3"):
                config_kwargs["thinking_config"] = types.ThinkingConfig(
                    thinking_level=types.ThinkingLevel.HIGH,
                    include_thoughts=self.include_thoughts_in_response
                )
            # Gemini 2.5 models use thinking_budget parameter
            elif self.model.startswith("gemini-2.5"):
                config_kwargs["thinking_config"] = types.ThinkingConfig(
                    thinking_budget=-1,  # -1 = dynamic (auto)
                    include_thoughts=self.include_thoughts_in_response
                )

        return config_kwargs

    # Backward compatibility alias
    def get_generation_config_kwargs(self, *args, **kwargs) -> Dict[str, Any]:
        """Alias for get_api_call_kwargs for backward compatibility"""
        return self.get_api_call_kwargs(*args, **kwargs)

    def model_copy(self, **overrides) -> "GoogleConfig":
        """
        Create a copy with overrides applied.

        Args:
            **overrides: Fields to override

        Returns:
            New GoogleConfig instance with overrides
        """
        config_dict = self.model_dump()

        # Handle nested overrides
        for key, value in overrides.items():
            if key == 'safety_settings' and isinstance(value, dict):
                config_dict['safety_settings'].update(value)
            else:
                config_dict[key] = value

        return GoogleConfig(**config_dict)


def get_google_client_config(**overrides: Any) -> GoogleConfig:
    """
    Get Google client configuration with optional overrides.

    This function provides backward compatibility and a convenient way
    to create GoogleConfig with overrides.

    Args:
        **overrides: Configuration overrides. Supports:
            - Direct field overrides: model, temperature, debug, etc.
            - Nested overrides: model_settings={'temperature': 0.8}
            - Safety overrides: safety_settings={'harassment_threshold': ...}

    Returns:
        GoogleConfig instance

    Example:
        >>> config = get_google_client_config(
        ...     model='gemini-2.5-pro',
        ...     temperature=1.0,
        ...     debug=True
        ... )
    """
    # Start with base config from environment
    try:
        base_config = GoogleConfig()
    except Exception:
        # If env loading fails, use defaults
        base_config = GoogleConfig(
            google_api_key="missing-key",
            model="gemini-3-flash-preview"
        )

    # Handle nested model_settings overrides for backward compatibility
    if 'model_settings' in overrides:
        model_settings = overrides.pop('model_settings')
        if isinstance(model_settings, dict):
            overrides.update(model_settings)

    # Also support "model_config" as alias
    if 'model_config' in overrides:
        model_config = overrides.pop('model_config')
        if isinstance(model_config, dict):
            overrides.update(model_config)

    # Apply overrides
    if overrides:
        return base_config.model_copy(**overrides)

    return base_config
