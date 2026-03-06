"""
Gemini client implementation using unified architecture.

This implementation inherits from the base LLMClientBase and uses shared components
where possible, while implementing Gemini-specific functionality.
"""

from typing import List, Optional, Dict, Any, cast, AsyncGenerator
from datetime import datetime
import os

from google import genai
from google.genai import types
from google.oauth2.credentials import Credentials as GoogleCredentials
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.infrastructure.llm.base.call_options import parse_call_options
from backend.infrastructure.llm.base.retry import run_with_retries, stream_with_retries
from backend.domain.models.messages import BaseMessage
from backend.domain.models.streaming import StreamingChunk
from backend.infrastructure.llm.shared.constants.thinking import GOOGLE_THINKING_LEVEL_TO_BUDGET
from backend.config.dev import get_dev_config

# Import Gemini-specific implementations
from .config import GoogleConfig
from .context_manager import GoogleContextManager
from .debug import GoogleDebugger
from .response_processor import GoogleResponseProcessor
from .tool_manager import GoogleToolManager
from backend.infrastructure.oauth.google.token_manager import GoogleTokenManager
from backend.infrastructure.oauth.google.oauth_client import (
    get_default_oauth_client,
    TOKEN_URL,
    SCOPES,
)
from backend.infrastructure.oauth.base.types import OAuthCredentials


# Thinking level to Gemini ThinkingLevel enum mapping
# Must be defined here due to google.genai.types dependency
GOOGLE_THINKING_LEVEL_MAP = {
    "low": types.ThinkingLevel.LOW,
    "high": types.ThinkingLevel.HIGH,
}


class GoogleClient(LLMClientBase):
    """
    Enhanced Google Gemini client with unified architecture.

    Key Features:
    - Inherits from unified LLMClientBase
    - Uses shared components where possible
    - Implements Gemini-specific functionality
    - Original response preservation during tool calling sequences
    - Thinking chain and validation field integrity
    - Real-time streaming tool call notifications
    - Comprehensive tool management and execution
    - Modular component architecture

    Components:
    - GoogleContextManager: Manages context and state for Gemini API calls
    - GoogleDebugger: Provides detailed request/response logging in debug mode
    - GoogleResponseProcessor: Enhanced response processing with tool call extraction
    - GoogleToolManager: Advanced MCP tool integration
    - Content Generators: Specialized content generation utilities
    """

    def __init__(self, config: GoogleConfig, extra_config: Optional[Dict[str, Any]] = None, **kwargs):
        """
        Initialize enhanced Gemini client with context preservation capabilities.

        Args:
            config: Google specific configuration
            extra_config: Additional configuration parameters
            **kwargs: Catch-all for extra arguments from factory
        """
        super().__init__(extra_config=extra_config)
        self.provider_name = "google"
        self.google_config = config

        self._oauth_token_manager = GoogleTokenManager()
        self._oauth_client = get_default_oauth_client()
        self._oauth_credentials: Optional[GoogleCredentials] = None
        self._oauth_account_id: Optional[str] = None
        self._oauth_project_id: Optional[str] = None
        self._oauth_location: Optional[str] = None
        self._auth_mode: Optional[str] = None

        if self._should_use_api_key():
            if not config.google_api_key:
                raise ValueError("Google API key not configured")
            self.client = genai.Client(api_key=config.google_api_key)
            self._auth_mode = "api_key"
        else:
            self.client = None
            self._auth_mode = "oauth"

        # Initialize component managers with unified architecture
        self.tool_manager = GoogleToolManager()

    # get_response is now implemented in base class using provider-specific components

    # ========== ABSTRACT METHOD IMPLEMENTATIONS ==========

    async def call_api_with_context(
        self, context_contents: List[Dict[str, Any]], api_config: Dict[str, Any], **kwargs
    ) -> types.GenerateContentResponse:
        """
        Execute direct Gemini API call with complete pre-formatted context and config.
        """
        await self._ensure_client_ready()
        call_options = parse_call_options(kwargs)
        debug = get_dev_config().debug_mode
        timeout = call_options.timeout if call_options.timeout is not None else self.google_config.timeout
        max_retries = (
            call_options.max_retries if call_options.max_retries is not None else self.google_config.max_retries
        )

        # Build API parameters
        kwargs_api = self.google_config.build_api_params()

        # System prompt and tools from api_config
        system_prompt = api_config.get("system_prompt", "")
        tool_schemas = api_config.get("tools", [])

        # Override with api_config if present
        if system_prompt:
            kwargs_api["system_instruction"] = system_prompt
        if tool_schemas:
            kwargs_api["tools"] = tool_schemas

        # Apply call options overrides
        if call_options.temperature is not None:
            kwargs_api["temperature"] = call_options.temperature
        if call_options.max_tokens is not None:
            kwargs_api["max_output_tokens"] = call_options.max_tokens
        if call_options.top_p is not None:
            kwargs_api["top_p"] = call_options.top_p
        if call_options.top_k is not None:
            kwargs_api["top_k"] = call_options.top_k

        # Handle thinking configuration based on thinking_level
        if call_options.thinking_level == "default":
            # Keep thought summaries enabled while letting API choose default reasoning effort.
            kwargs_api["thinking_config"] = types.ThinkingConfig(include_thoughts=True)
        elif call_options.thinking_level is not None:
            model = self.google_config.model
            if model.startswith("gemini-3"):
                thinking_level = GOOGLE_THINKING_LEVEL_MAP.get(call_options.thinking_level, types.ThinkingLevel.HIGH)
                kwargs_api["thinking_config"] = types.ThinkingConfig(
                    thinking_level=thinking_level, include_thoughts=True
                )
            elif model.startswith("gemini-2.5"):
                budget = GOOGLE_THINKING_LEVEL_TO_BUDGET.get(call_options.thinking_level, -1)
                kwargs_api["thinking_config"] = types.ThinkingConfig(thinking_budget=budget, include_thoughts=True)

        config = types.GenerateContentConfig(**kwargs_api)
        model = self.google_config.model

        if debug:
            GoogleDebugger.print_request(context_contents, config, model)

        async def _call_api():
            response = await self.client.aio.models.generate_content(
                model=model,
                contents=cast(Any, context_contents),
                config=config,
            )

            # Validate response structure
            if not hasattr(response, "candidates") or not response.candidates:
                if debug:
                    GoogleDebugger.print_error("No candidates", model, response=response)
                raise Exception(f"Empty response (no candidates). Model: {model}")

            candidate = response.candidates[0]
            if not hasattr(candidate, "content") or not candidate.content:
                if debug:
                    GoogleDebugger.print_error("Empty content", model, candidate=candidate)
                raise Exception(
                    f"Empty content. Model: {model}, finish_reason: {getattr(candidate, 'finish_reason', None)}"
                )

            if not hasattr(candidate.content, "parts") or not candidate.content.parts:
                if debug:
                    GoogleDebugger.print_error("Empty parts", model, candidate=candidate)
                raise Exception(
                    f"Empty parts. Model: {model}, "
                    f"finish_reason: {getattr(candidate, 'finish_reason', None)}, "
                    f"safety_ratings: {getattr(candidate, 'safety_ratings', None)}"
                )

            if debug:
                GoogleDebugger.print_response(response)

            return response

        try:
            return await run_with_retries(
                _call_api,
                max_retries=max_retries,
                timeout=timeout,
                debug=debug,
            )
        except Exception as e:
            if debug and "Empty" not in str(e):
                print(f"[DEBUG] API error: {e}")
            raise Exception(f"Gemini API failed: {e}")

    # ========== PROVIDER-SPECIFIC METHODS FOR BASE IMPLEMENTATION ==========

    def _get_response_processor(self):
        """Get Gemini-specific response processor instance."""
        return GoogleResponseProcessor()

    def _get_context_manager_class(self):
        """Get Gemini-specific context manager class."""
        return GoogleContextManager

    def _build_api_config(self, system_prompt: str, tool_schemas: Optional[List[Any]]) -> Dict[str, Any]:
        """
        Build Gemini-specific API configuration.

        Args:
            system_prompt: Pre-built system prompt
            tool_schemas: Tool schemas in Gemini format

        Returns:
            Dict containing raw configuration components for call_api_with_context
        """
        # Return raw components so call_api_with_context can assemble the final config
        # and apply runtime overrides (temperature, etc.) correctly.
        return {"system_prompt": system_prompt, "tools": tool_schemas}

    def _get_provider_config(self):
        """Get Gemini-specific configuration object."""
        return self.google_config

    async def call_api_with_context_streaming(
        self, context_contents: List[Dict[str, Any]], api_config: Dict[str, Any], **kwargs
    ) -> AsyncGenerator[StreamingChunk, None]:
        """
        Execute streaming Gemini API call with real-time chunk delivery.
        """
        await self._ensure_client_ready()
        call_options = parse_call_options(kwargs)
        debug = get_dev_config().debug_mode
        timeout = call_options.timeout if call_options.timeout is not None else self.google_config.timeout
        max_retries = (
            call_options.max_retries if call_options.max_retries is not None else self.google_config.max_retries
        )

        # Build API parameters
        kwargs_api = self.google_config.build_api_params()

        # System prompt and tools from api_config
        system_prompt = api_config.get("system_prompt", "")
        tool_schemas = api_config.get("tools", [])

        # Override with api_config if present
        if system_prompt:
            kwargs_api["system_instruction"] = system_prompt
        if tool_schemas:
            kwargs_api["tools"] = tool_schemas

        # Apply call options overrides
        if call_options.temperature is not None:
            kwargs_api["temperature"] = call_options.temperature
        if call_options.max_tokens is not None:
            kwargs_api["max_output_tokens"] = call_options.max_tokens
        if call_options.top_p is not None:
            kwargs_api["top_p"] = call_options.top_p
        if call_options.top_k is not None:
            kwargs_api["top_k"] = call_options.top_k

        # Handle thinking configuration based on thinking_level
        if call_options.thinking_level == "default":
            # Keep thought summaries enabled while letting API choose default reasoning effort.
            kwargs_api["thinking_config"] = types.ThinkingConfig(include_thoughts=True)
        elif call_options.thinking_level is not None:
            model = self.google_config.model
            if model.startswith("gemini-3"):
                thinking_level = GOOGLE_THINKING_LEVEL_MAP.get(call_options.thinking_level, types.ThinkingLevel.HIGH)
                kwargs_api["thinking_config"] = types.ThinkingConfig(
                    thinking_level=thinking_level, include_thoughts=True
                )
            elif model.startswith("gemini-2.5"):
                budget = GOOGLE_THINKING_LEVEL_TO_BUDGET.get(call_options.thinking_level, -1)
                kwargs_api["thinking_config"] = types.ThinkingConfig(thinking_budget=budget, include_thoughts=True)

        config = types.GenerateContentConfig(**kwargs_api)
        model = self.google_config.model

        if debug:
            GoogleDebugger.print_request(context_contents, config, model)

        async def _stream_once():
            try:
                # Use streaming API
                stream_generator = self.client.aio.models.generate_content_stream(
                    model=model,
                    contents=cast(Any, context_contents),
                    config=config,
                )

                # Create stateful streaming processor
                streaming_processor = self._get_response_processor().create_streaming_processor()

                # Debug counters
                chunk_index = 0
                empty_chunk_count = 0

                async for chunk in await stream_generator:
                    # Debug: print raw chunk before processing
                    if debug:
                        GoogleDebugger.print_streaming_chunk(chunk, chunk_index)

                    # Delegate chunk processing to streaming processor
                    processed_chunks = streaming_processor.process_event(chunk)

                    # Track empty chunks for debugging
                    if debug and not processed_chunks:
                        empty_chunk_count += 1

                    for processed_chunk in processed_chunks:
                        yield processed_chunk

                    chunk_index += 1

                # Debug: print summary after streaming completes
                if debug:
                    GoogleDebugger.print_streaming_summary(chunk_index, empty_chunk_count)

            except Exception as e:
                error_message = f"Gemini streaming API call failed: {str(e)}"
                if debug:
                    print(f"[DEBUG] {error_message}")
                raise Exception(error_message)

        async for chunk in stream_with_retries(
            _stream_once,
            max_retries=max_retries,
            timeout=timeout,
            debug=debug,
        ):
            yield chunk

    def _oauth_enabled(self) -> bool:
        if self.google_config.use_oauth:
            return True
        env_flag = os.getenv("GOOGLE_USE_OAUTH")
        if env_flag:
            return env_flag.strip().lower() in {"1", "true", "yes", "on"}
        return False

    def _should_use_api_key(self) -> bool:
        if self._oauth_enabled():
            return False
        return bool(self.google_config.google_api_key)

    async def _ensure_client_ready(self) -> None:
        if self._auth_mode == "api_key" and self.client is not None:
            return
        if self._should_use_api_key():
            if not self.client:
                if not self.google_config.google_api_key:
                    raise ValueError("Google API key not configured")
                self.client = genai.Client(api_key=self.google_config.google_api_key)
                self._auth_mode = "api_key"
            return

        if not self._oauth_enabled():
            raise ValueError("Google API key not configured")

        account_id_override = self.google_config.oauth_account_id or os.getenv("GOOGLE_OAUTH_ACCOUNT_ID")
        credentials, account_id = await self._oauth_token_manager.get_credentials(account_id_override)
        project_id = self._resolve_vertex_project_id(credentials)
        location = self._resolve_vertex_location()

        if not project_id:
            raise ValueError(
                "Google OAuth requires a Vertex AI project ID. "
                "Set GOOGLE_CLOUD_PROJECT or ensure OAuth project discovery succeeds."
            )

        needs_rebuild = (
            self.client is None
            or self._auth_mode != "oauth"
            or account_id != self._oauth_account_id
            or project_id != self._oauth_project_id
            or location != self._oauth_location
        )

        if needs_rebuild:
            self._oauth_credentials = self._build_oauth_credentials(credentials)
            self.client = genai.Client(
                vertexai=True,
                credentials=self._oauth_credentials,
                project=project_id,
                location=location,
            )
            self._auth_mode = "oauth"
            self._oauth_account_id = account_id
            self._oauth_project_id = project_id
            self._oauth_location = location
        else:
            self._sync_oauth_credentials(credentials)

    def _resolve_vertex_project_id(self, credentials: OAuthCredentials) -> Optional[str]:
        if self.google_config.vertex_project_id:
            return self.google_config.vertex_project_id
        if credentials.project_id:
            return credentials.project_id

        env_project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        if env_project:
            return env_project
        env_project = os.getenv("GCLOUD_PROJECT")
        if env_project:
            return env_project
        return None

    def _resolve_vertex_location(self) -> str:
        if self.google_config.vertex_location:
            return self.google_config.vertex_location

        return (
            os.getenv("GOOGLE_CLOUD_LOCATION")
            or os.getenv("VERTEX_LOCATION")
            or os.getenv("GOOGLE_CLOUD_REGION")
            or "us-central1"
        )

    def _build_oauth_credentials(self, credentials: OAuthCredentials) -> GoogleCredentials:
        oauth_creds = GoogleCredentials(
            token=credentials.access_token,
            refresh_token=credentials.refresh_token,
            token_uri=TOKEN_URL,
            client_id=self._oauth_client.client_id,
            client_secret=self._oauth_client.client_secret,
            scopes=SCOPES,
        )
        oauth_creds.expiry = datetime.utcfromtimestamp(credentials.expires_at)
        return oauth_creds

    def _sync_oauth_credentials(self, credentials: OAuthCredentials) -> None:
        if not self._oauth_credentials:
            return
        self._oauth_credentials.token = credentials.access_token
        self._oauth_credentials.expiry = datetime.utcfromtimestamp(credentials.expires_at)

    # _streaming_tool_calling_loop is inherited from LLMClientBase
    # _construct_response_from_streaming_chunks is now handled by ResponseProcessor
