"""
OpenAI Codex client implementation using OAuth authentication.

This implementation uses the Codex API endpoint with ChatGPT Pro/Plus
subscription authentication instead of standard OpenAI API keys.
"""

import os
import platform
from typing import List, Optional, Dict, Any, AsyncGenerator

import httpx
from openai import AsyncOpenAI
from openai.types.responses import Response, ResponseCompletedEvent

from backend.infrastructure.llm.base.client import LLMClientBase
from backend.infrastructure.llm.base.call_options import parse_call_options
from backend.infrastructure.llm.base.retry import run_with_retries, stream_with_retries
from backend.domain.models.streaming import StreamingChunk
from backend.config.dev import get_dev_config
from backend.infrastructure.oauth.openai.token_manager import (
    get_token_manager,
    has_openai_oauth_accounts,
)

# Import OpenAI-specific implementations (reuse from openai provider)
from backend.infrastructure.llm.providers.openai.context_manager import OpenAIContextManager
from backend.infrastructure.llm.providers.openai.debug import OpenAIDebugger
from backend.infrastructure.llm.providers.openai.response_processor import OpenAIResponseProcessor
from backend.infrastructure.llm.providers.openai.tool_manager import OpenAIToolManager

from backend.infrastructure.llm.shared.constants.thinking import OPENAI_THINKING_LEVEL_TO_EFFORT

from .config import OpenAICodexConfig

# Codex API endpoint
CODEX_API_BASE_URL = "https://chatgpt.com/backend-api/codex"

# Version info
VERSION = "1.0.0"


class OpenAICodexClient(LLMClientBase):
    """
    OpenAI Codex client using OAuth authentication.

    Key Features:
    - OAuth authentication (ChatGPT Pro/Plus subscription)
    - Codex API endpoint instead of standard OpenAI API
    - Automatic token refresh
    - Full streaming support with tool calling
    - Zero additional cost (included with subscription)
    """

    def __init__(self, config: OpenAICodexConfig, extra_config: Optional[Dict[str, Any]] = None, **kwargs):
        """
        Initialize OpenAI Codex client.

        Args:
            config: Codex-specific configuration
            extra_config: Additional configuration parameters
            **kwargs: Catch-all for extra arguments from factory
        """
        super().__init__(extra_config=extra_config)
        self.provider_name = "openai-codex"
        self.codex_config = config
        self.tool_manager = OpenAIToolManager()

        # Token manager for OAuth authentication
        self._token_manager = get_token_manager()

        # Async client will be created lazily with current OAuth token
        self._async_client: Optional[AsyncOpenAI] = None
        self._current_account_id: Optional[str] = None
        self._chatgpt_account_id: Optional[str] = None

    async def _ensure_client(self, session_id: Optional[str] = None) -> AsyncOpenAI:
        """
        Ensure we have a valid async client with current OAuth credentials.

        Args:
            session_id: Optional session ID to include in headers

        Returns:
            Configured AsyncOpenAI client
        """
        # Get current credentials
        account_id_override = self.codex_config.oauth_account_id or os.getenv("OPENAI_OAUTH_ACCOUNT_ID")

        access_token, account_id = await self._token_manager.get_access_token(account_id_override)
        chatgpt_account_id, _ = await self._token_manager.get_chatgpt_account_id(account_id_override)

        # Recreate client if account changed, session changed, or first time
        if (
            self._async_client is None
            or self._current_account_id != account_id
            or self.extra_config.get("session_id") != session_id
        ):
            self._async_client = self._create_client(
                access_token=access_token,
                chatgpt_account_id=chatgpt_account_id,
                session_id_override=session_id,
            )
            self._current_account_id = account_id
            self._chatgpt_account_id = chatgpt_account_id

        return self._async_client

    def _create_client(
        self,
        access_token: str,
        chatgpt_account_id: Optional[str],
        session_id_override: Optional[str] = None,
    ) -> AsyncOpenAI:
        """
        Create an AsyncOpenAI client configured for Codex API.

        Args:
            access_token: OAuth access token
            chatgpt_account_id: ChatGPT account ID for subscription tracking
            session_id_override: Optional session ID override

        Returns:
            Configured AsyncOpenAI client
        """
        # Build headers for http_client
        # Note: Authorization will be added by the OpenAI SDK using the api_key
        headers = {
            "User-Agent": self._build_user_agent(),
            "originator": "codex_cli_rs",
        }

        # Add turn metadata header (matches codex-rs x-codex-turn-metadata)
        # This includes information about the current workspace and git status
        # For now, we use a simplified version containing the project root
        project_root = os.getcwd()
        metadata = {
            "workspaces": {
                project_root: {
                    # Optional fields like associated_remote_urls or latest_git_commit_hash
                    # could be added here for better context
                }
            }
        }
        import json

        headers["x-codex-turn-metadata"] = json.dumps(metadata)

        # Add ChatGPT account ID if available (for organization subscriptions)
        if chatgpt_account_id:
            headers["ChatGPT-Account-Id"] = chatgpt_account_id

        # Add session ID if available
        session_id = session_id_override or self.extra_config.get("session_id")
        if session_id:
            headers["session_id"] = session_id

        # Create custom HTTP client with common headers

        http_client = httpx.AsyncClient(
            headers=headers,
            timeout=httpx.Timeout(self.codex_config.timeout, connect=30.0),
        )

        # Create OpenAI client pointing to Codex endpoint
        # We pass access_token as api_key so the SDK correctly handles Bearer authentication
        # We also pass headers to default_headers to ensure the SDK uses our originator and User-Agent
        return AsyncOpenAI(
            api_key=access_token,
            base_url=CODEX_API_BASE_URL,
            http_client=http_client,
            default_headers=headers,
        )

    def _build_user_agent(self) -> str:
        """Build User-Agent header string following codex-rs convention."""
        system = platform.system()
        # Map system names to what codex-rs/os_info expects/returns
        if system == "Darwin":
            os_name = "Mac OS"
        elif system == "Windows":
            os_name = "Windows"
        else:
            os_name = system

        release = platform.release()
        arch = platform.machine()

        # codex_cli_rs/1.0.0 (Mac OS 15.2.0; arm64) toyoura-nagisa/1.0.0
        return f"codex_cli_rs/1.0.0 ({os_name} {release}; {arch}) toyoura-nagisa/{VERSION}"

    async def call_api_with_context(
        self, context_contents: List[Dict[str, Any]], api_config: Dict[str, Any], **kwargs
    ) -> Response:
        """
        Execute a stateless OpenAI Codex API call with prepared context.

        Since Codex API requires streaming (stream: true), this method internally
        uses streaming and aggregates the result into a single Response object
        to support unary call patterns.

        Args:
            context_contents: Conversation messages in provider-neutral format.
            api_config: Provider configuration including tools and instructions.
            **kwargs: Optional overrides (temperature, top_p).

        Returns:
            OpenAI Responses API `Response` object.
        """
        # Collect all chunks from streaming call
        collected_chunks: List[StreamingChunk] = []
        async for chunk in self.call_api_with_context_streaming(
            context_contents=context_contents, api_config=api_config, **kwargs
        ):
            collected_chunks.append(chunk)

        # Reconstruct Response object using OpenAIResponseProcessor
        return OpenAIResponseProcessor.construct_response_from_chunks(collected_chunks)

    def _get_response_processor(self):
        """Get OpenAI-specific response processor instance."""
        return OpenAIResponseProcessor()

    def _get_context_manager_class(self):
        """Get OpenAI-specific context manager class."""
        return OpenAIContextManager

    def _build_api_config(self, system_prompt: str, tool_schemas: Optional[List[Any]]) -> Dict[str, Any]:
        """
        Build OpenAI-specific API configuration.

        Args:
            system_prompt: Pre-built system prompt
            tool_schemas: Tool schemas in OpenAI format

        Returns:
            Dict with 'tools' and 'instructions' keys
        """
        return {
            "tools": tool_schemas or [],
            "instructions": system_prompt,
        }

    def _get_provider_config(self):
        """Get Codex-specific configuration object."""
        return self.codex_config

    async def call_api_with_context_streaming(
        self, context_contents: List[Dict[str, Any]], api_config: Dict[str, Any], **kwargs
    ) -> AsyncGenerator[StreamingChunk, None]:
        """
        Execute streaming Codex API call and yield standardized chunks.
        """
        call_options = parse_call_options(kwargs)
        debug = get_dev_config().debug_mode
        timeout = call_options.timeout if call_options.timeout is not None else self.codex_config.timeout
        max_retries = (
            call_options.max_retries if call_options.max_retries is not None else self.codex_config.max_retries
        )

        tools = api_config.get("tools", []) or []
        instructions = api_config.get("instructions")

        input_items = context_contents

        kwargs_api = self.codex_config.build_api_params()
        kwargs_api.update(
            {
                "instructions": instructions,
                "input": input_items,
                "tools": tools,
                "tool_choice": "auto" if tools else None,
                "parallel_tool_calls": True,  # Match codex-rs default
                "store": False,  # Explicitly set to False as required by Codex API
            }
        )

        # Add session ID if provided in call_options or extra_config
        effective_session_id = call_options.session_id or self.extra_config.get("session_id")

        # Handle thinking mode (reasoning effort for reasoning models)
        # Resolution: call_options > config > "default" (which maps to "medium")
        effective_thinking_level = call_options.thinking_level or self.codex_config.reasoning_effort or "default"

        # Ensure include list is initialized
        if "include" not in kwargs_api:
            kwargs_api["include"] = []

        # Map thinking level to OpenAI effort value
        # "default" → "medium", "low" → "low", "high" → "high"
        effort = OPENAI_THINKING_LEVEL_TO_EFFORT.get(effective_thinking_level)
        if effort is not None:
            kwargs_api["reasoning"] = {"effort": effort, "summary": "auto"}
            # Opt-in to reasoning output (matches codex-rs/opencode)
            if "reasoning.encrypted_content" not in kwargs_api.get("include", []):
                kwargs_api["include"].append("reasoning.encrypted_content")

        if debug:
            OpenAIDebugger.log_api_call_info(tools_count=len(tools), model=self.codex_config.model)
            OpenAIDebugger.print_debug_request_payload(kwargs_api)

        async def _stream_once():
            final_response: Optional[Response] = None

            try:
                # Ensure client with current OAuth token and session ID
                client = await self._ensure_client(session_id=effective_session_id)

                # Create stateful streaming processor
                streaming_processor = self._get_response_processor().create_streaming_processor()

                async with client.responses.stream(**kwargs_api) as stream:
                    async for event in stream:
                        # Delegate event processing to streaming processor
                        processed_chunks = streaming_processor.process_event(event)
                        for chunk in processed_chunks:
                            yield chunk

                        # Capture final response metadata
                        if isinstance(event, ResponseCompletedEvent):
                            final_response = event.response

            except Exception:
                if debug:
                    OpenAIDebugger.print_debug_request_payload(kwargs_api)
                raise

            if final_response:
                # Extract usage metadata from final response
                final_metadata: Dict[str, Any] = {"__openai_final_response": final_response}

                if hasattr(final_response, "usage") and final_response.usage:
                    usage = final_response.usage
                    final_metadata.update(
                        {
                            "prompt_token_count": getattr(usage, "input_tokens", None),
                            "candidates_token_count": getattr(usage, "output_tokens", None),
                            "total_token_count": getattr(usage, "total_tokens", None),
                        }
                    )

                    # Extract detailed token counts
                    if hasattr(usage, "output_tokens_details") and usage.output_tokens_details:
                        final_metadata["reasoning_tokens"] = getattr(
                            usage.output_tokens_details,
                            "reasoning_tokens",
                            None,
                        )

                    if hasattr(usage, "input_tokens_details") and usage.input_tokens_details:
                        final_metadata["cached_tokens"] = getattr(
                            usage.input_tokens_details,
                            "cached_tokens",
                            None,
                        )

                yield StreamingChunk(
                    chunk_type="text",
                    content="",
                    metadata=final_metadata,
                )

        async for chunk in stream_with_retries(
            _stream_once,
            max_retries=max_retries,
            timeout=timeout,
            debug=debug,
        ):
            yield chunk


def is_codex_available() -> bool:
    """
    Check if Codex provider is available (has OAuth credentials).

    Returns:
        True if at least one OpenAI OAuth account is configured
    """
    return has_openai_oauth_accounts()
