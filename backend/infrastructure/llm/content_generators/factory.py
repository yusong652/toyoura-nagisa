"""Content Generator Factory for Multi-LLM Support.

This factory provides unified interfaces for content generation tasks across
different LLM providers (Gemini, Anthropic, OpenAI), following the same
architecture pattern as WebSearchToolFactory.
"""

from typing import Dict, Any, Optional, List
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
            LLM type string ('gemini', 'anthropic', 'openai', or 'kimi')

        Raises:
            ValueError: If LLM type cannot be detected
        """
        client_type = type(llm_client).__name__.lower()
        client_module = type(llm_client).__module__.lower()

        # Check specific providers FIRST (Kimi, OpenRouter) before OpenAI
        # (since they use OpenAI-compatible API)
        if 'kimi' in client_type or 'kimi' in client_module:
            return 'kimi'
        elif 'openrouter' in client_type or 'openrouter' in client_module:
            return 'openrouter'
        elif 'gemini' in client_type or 'gemini' in client_module:
            return 'gemini'
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
                return 'gemini'
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
            llm_type: Type of LLM client ('gemini', 'anthropic', 'openai', or 'kimi')

        Returns:
            TitleGenerator class for the specified LLM type

        Raises:
            ValueError: If LLM type is not supported
        """
        if llm_type.lower() == 'gemini':
            from backend.infrastructure.llm.providers.gemini.content_generators import GeminiTitleGenerator
            return GeminiTitleGenerator
        elif llm_type.lower() == 'anthropic':
            from backend.infrastructure.llm.providers.anthropic.content_generators import TitleGenerator
            return TitleGenerator
        elif llm_type.lower() == 'openai':
            from backend.infrastructure.llm.providers.openai.content_generators import TitleGenerator
            return TitleGenerator
        elif llm_type.lower() == 'kimi':
            # Kimi has its own TitleGenerator using Chat Completions API
            from backend.infrastructure.llm.providers.kimi.content_generators import TitleGenerator
            return TitleGenerator
        elif llm_type.lower() == 'openrouter':
            # OpenRouter uses Chat Completions API (similar to Kimi)
            from backend.infrastructure.llm.providers.openrouter.content_generators import TitleGenerator
            return TitleGenerator
        else:
            raise ValueError(f"Unsupported LLM type for title generation: {llm_type}")

    @staticmethod
    def get_image_prompt_generator(llm_type: str):
        """
        Get the appropriate image prompt generator based on LLM type.

        Args:
            llm_type: Type of LLM client ('gemini', 'anthropic', 'openai', or 'kimi')

        Returns:
            ImagePromptGenerator class for the specified LLM type

        Raises:
            ValueError: If LLM type is not supported
        """
        if llm_type.lower() == 'gemini':
            from backend.infrastructure.llm.providers.gemini.content_generators import GeminiImagePromptGenerator
            return GeminiImagePromptGenerator
        elif llm_type.lower() == 'anthropic':
            from backend.infrastructure.llm.providers.anthropic.content_generators import ImagePromptGenerator
            return ImagePromptGenerator
        elif llm_type.lower() == 'openai':
            from backend.infrastructure.llm.providers.openai.content_generators import ImagePromptGenerator
            return ImagePromptGenerator
        elif llm_type.lower() == 'kimi':
            # Kimi has its own ImagePromptGenerator using Chat Completions API
            from backend.infrastructure.llm.providers.kimi.content_generators import ImagePromptGenerator
            return ImagePromptGenerator
        elif llm_type.lower() == 'openrouter':
            # OpenRouter uses Chat Completions API (similar to Kimi)
            from backend.infrastructure.llm.providers.openrouter.content_generators import ImagePromptGenerator
            return ImagePromptGenerator
        else:
            raise ValueError(f"Unsupported LLM type for image prompt generation: {llm_type}")

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

            # Get the appropriate title generator
            TitleGenerator = ContentGeneratorFactory.get_title_generator(llm_type)

            # Extract the async client for generator (use async_client for OpenAI-compatible APIs)
            # Fallback to 'client' for providers that don't have separate async/sync clients
            client = getattr(llm_client, 'async_client', None) or getattr(llm_client, 'client', llm_client)

            # Call provider-specific generator
            title = await TitleGenerator.generate_title_from_messages(
                client=client,
                latest_messages=latest_messages
            )

            return title

        except Exception as e:
            print(f"[ERROR] Title generation failed: {e}")
            import traceback
            traceback.print_exc()
            raise

    @staticmethod
    async def generate_text_to_image_prompt(
        llm_client: LLMClientBase,
        session_id: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        """
        Generate text-to-image prompt using appropriate LLM client.

        Args:
            llm_client: The LLM client instance
            session_id: Session ID for getting conversation context

        Returns:
            Dictionary containing text prompt and negative prompt, or None if failed

        Raises:
            ValueError: If LLM type cannot be detected
            Exception: If prompt generation fails
        """
        try:
            # Auto-detect LLM type
            llm_type = ContentGeneratorFactory.detect_llm_type(llm_client)

            # Get the appropriate image prompt generator
            ImagePromptGenerator = ContentGeneratorFactory.get_image_prompt_generator(llm_type)

            # Extract the async client for generator (use async_client for OpenAI-compatible APIs)
            # Fallback to 'client' for providers that don't have separate async/sync clients
            client = getattr(llm_client, 'async_client', None) or getattr(llm_client, 'client', llm_client)

            # Call provider-specific generator
            prompt_result = await ImagePromptGenerator.generate_text_to_image_prompt(
                client=client,
                session_id=session_id
            )

            return prompt_result

        except Exception as e:
            print(f"[ERROR] Image prompt generation failed: {e}")
            raise
