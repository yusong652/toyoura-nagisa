"""Content Generator Factory for Multi-LLM Support.

This factory provides unified interfaces for content generation tasks across
different LLM providers (Gemini, Anthropic, OpenAI, Moonshot, OpenRouter, Zhipu),
following the same architecture pattern as WebSearchToolFactory.
"""

from typing import Optional, List
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.domain.models.messages import BaseMessage


class ContentGeneratorFactory:
    """Factory class to handle content generation across different LLM providers."""

    @staticmethod
    def detect_llm_type(llm_client: LLMClientBase) -> str:
        """
        Auto-detect LLM type from client instance.

        Args:
            llm_client: The LLM client instance

        Returns:
            LLM type string ('google', 'anthropic', 'openai', 'moonshot', 'openrouter', or 'zhipu')

        Raises:
            ValueError: If LLM type cannot be detected
        """
        client_type = type(llm_client).__name__.lower()
        client_module = type(llm_client).__module__.lower()

        # Check specific providers FIRST (Moonshot, OpenRouter, Zhipu) before OpenAI
        # (since they use OpenAI-compatible API)
        if 'moonshot' in client_type or 'moonshot' in client_module:
            return 'moonshot'
        elif 'openrouter' in client_type or 'openrouter' in client_module:
            return 'openrouter'
        elif 'zhipu' in client_type or 'zhipu' in client_module:
            return 'zhipu'
        elif 'google' in client_type or 'google' in client_module:
            return 'google'
        elif 'anthropic' in client_type or 'anthropic' in client_module:
            return 'anthropic'
        elif 'openai' in client_type or 'openai' in client_module:
            return 'openai'
        elif hasattr(llm_client, 'client'):
            # Try to detect from wrapped client
            return ContentGeneratorFactory.detect_llm_type(llm_client.client)
        else:
            # Fallback: check for specific attributes
            if hasattr(llm_client, 'models') and hasattr(llm_client, 'generate_content'):
                return 'google'
            elif hasattr(llm_client, 'messages') and hasattr(llm_client, 'create'):
                return 'anthropic'
            elif hasattr(llm_client, 'chat') and hasattr(llm_client.chat, 'completions'):
                return 'openai'
            else:
                raise ValueError(f"Unable to detect LLM type from client: {type(llm_client)}")

    @staticmethod
    def get_title_generator(llm_type: str):
        """
        Get the appropriate title generator based on LLM type.

        Args:
            llm_type: Type of LLM client ('google', 'anthropic', 'openai', 'moonshot', 'openrouter', or 'zhipu')

        Returns:
            TitleGenerator class for the specified LLM type

        Raises:
            ValueError: If LLM type is not supported
        """
        if llm_type.lower() == 'google':
            from backend.infrastructure.llm.providers.google.content_generators import GoogleTitleGenerator
            return GoogleTitleGenerator
        elif llm_type.lower() == 'anthropic':
            from backend.infrastructure.llm.providers.anthropic.content_generators import AnthropicTitleGenerator
            return AnthropicTitleGenerator
        elif llm_type.lower() == 'openai':
            from backend.infrastructure.llm.providers.openai.content_generators import OpenAITitleGenerator
            return OpenAITitleGenerator
        elif llm_type.lower() == 'moonshot':
            # Moonshot has its own TitleGenerator using Chat Completions API
            from backend.infrastructure.llm.providers.moonshot.content_generators import MoonshotTitleGenerator
            return MoonshotTitleGenerator
        elif llm_type.lower() == 'openrouter':
            # OpenRouter uses Chat Completions API (similar to Moonshot)
            from backend.infrastructure.llm.providers.openrouter.content_generators import OpenRouterTitleGenerator
            return OpenRouterTitleGenerator
        elif llm_type.lower() == 'zhipu':
            # Zhipu uses Chat Completions API via zai SDK
            from backend.infrastructure.llm.providers.zhipu.content_generators import ZhipuTitleGenerator
            return ZhipuTitleGenerator
        else:
            raise ValueError(f"Unsupported LLM type for title generation: {llm_type}")

    @staticmethod
    @staticmethod
    async def generate_title_from_messages(
        llm_client: LLMClientBase,
        latest_messages: List[BaseMessage]
    ) -> Optional[str]:
        """
        Generate title from conversation messages using appropriate LLM client.

        Args:
            llm_client: The LLM client instance
            latest_messages: Recent conversation messages to generate title from

        Returns:
            Generated title string, or None if failed

        Raises:
            ValueError: If LLM type cannot be detected
            Exception: If title generation fails
        """
        try:
            # Auto-detect LLM type
            llm_type = ContentGeneratorFactory.detect_llm_type(llm_client)

            # Get the appropriate title generator class
            TitleGeneratorClass = ContentGeneratorFactory.get_title_generator(llm_type)

            # Extract the async client for generator (use async_client for OpenAI-compatible APIs)
            # Fallback to 'client' for providers that don't have separate async/sync clients
            client = getattr(llm_client, 'async_client', None) or getattr(llm_client, 'client', llm_client)

            # Instantiate the generator with the client
            generator = TitleGeneratorClass(client=client)

            # Call provider-specific generator (now an instance method)
            title = await generator.generate_title_from_messages(
                latest_messages=latest_messages
            )

            return title

        except Exception as e:
            print(f"[ERROR] Title generation failed: {e}")
            import traceback
            traceback.print_exc()
            raise
