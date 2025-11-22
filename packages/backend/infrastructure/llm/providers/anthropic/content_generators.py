"""
Content generation utilities for Anthropic Claude API.

Specialized generators for creating titles, image prompts, and other derived content
based on conversation context. Separates content generation concerns from the main client.
"""

from typing import Optional, Dict, List, Any, cast
import anthropic
from backend.domain.models.messages import BaseMessage, UserMessage
from backend.infrastructure.llm.base.content_generators.title import BaseTitleGenerator
from backend.infrastructure.llm.base.content_generators.web_search import BaseWebSearchGenerator
from backend.infrastructure.llm.base.content_generators.image_prompt import BaseImagePromptGenerator
from backend.infrastructure.llm.shared.constants import (
    DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT,
    DEFAULT_WEB_SEARCH_SYSTEM_PROMPT
)
from backend.infrastructure.llm.shared.utils.text_processing import parse_title_response
from .message_formatter import MessageFormatter
from backend.config import get_llm_settings
from .config import get_anthropic_client_config
from .response_processor import AnthropicResponseProcessor


class TitleGenerator(BaseTitleGenerator):
    """
    Handles conversation title generation using Anthropic Claude API.

    Generates concise, descriptive titles based on the first exchange
    in a conversation to help users identify and organize their chats.
    Inherits from BaseTitleGenerator for consistency with other providers.
    """

    @staticmethod
    async def generate_title_from_messages(
        client: anthropic.AsyncAnthropic,
        latest_messages: List[BaseMessage],
    ) -> Optional[str]:
        """
        Generate a concise conversation title based on recent messages.

        Args:
            client: Anthropic client instance for API calls
            latest_messages: Recent conversation messages to generate title from

        Returns:
            Generated title string, or None if generation fails
        """
        try:
            # Use base class validation
            if not BaseTitleGenerator.validate_messages_for_title(latest_messages):
                return None

            # Get Anthropic configuration
            anthropic_config = get_anthropic_client_config()

            # Extract text content from messages and assemble into conversation context
            # This approach avoids sending complex message structures (thinking blocks, etc.)
            conversation_parts = []
            for msg in latest_messages:
                role = getattr(msg, 'role', 'user')
                content = getattr(msg, 'content', '')

                # Handle content list or string
                if isinstance(content, list):
                    # Extract text from content blocks (skip thinking blocks)
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict):
                            block_type = block.get('type')
                            if block_type == 'text':
                                text_parts.append(block.get('text', ''))
                    content_str = '\n'.join(text_parts)
                else:
                    content_str = str(content)

                # Add to conversation with role label
                role_label = "User" if role == "user" else "Assistant"
                conversation_parts.append(f"{role_label}: {content_str}")

            # Combine conversation into single context
            conversation_context = '\n'.join(conversation_parts)

            # Build simple message structure with conversation as context
            # This prevents issues with complex message structures (thinking blocks, etc.)
            messages = [
                {
                    "role": "user",
                    "content": f"Please generate a concise title based on the following conversation:\n\n{conversation_context}"
                }
            ]

            # Use shared system prompt for consistency
            system_prompt = DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT

            # Build API call parameters using the configuration system
            api_kwargs = anthropic_config.get_api_call_kwargs(
                system_prompt=system_prompt,
                messages=messages
            )

            # Override parameters specific to title generation
            api_kwargs.update({
                "max_tokens": 100,  # Sufficient for title generation
                "temperature": 1.0
            })

            # Disable thinking for title generation (simple task, no need for extended thinking)
            if "thinking" in api_kwargs:
                del api_kwargs["thinking"]

            from backend.config import get_llm_settings
            llm_settings = get_llm_settings()
            debug = llm_settings.debug
            if debug:
                print("[DEBUG] Anthropic title generation API kwargs:")
                import pprint
                pprint.pprint(api_kwargs)

            response = await client.messages.create(**api_kwargs)

            # Extract text content using ResponseProcessor (skips thinking blocks)
            title_response_text = AnthropicResponseProcessor.extract_text_content(response)

            if title_response_text:
                # Parse title using shared utility function
                # Using max_length=30 to match original Anthropic behavior
                return parse_title_response(title_response_text, max_length=30)
            return None

        except Exception as e:
            print(f"Anthropic title generation error: {str(e)}")
            return None


class AnthropicWebSearchGenerator(BaseWebSearchGenerator):
    """
    Handles web search using Anthropic Claude API with web_search_20250305 tool.

    Performs web searches using the native web search capability via the Anthropic API.
    Returns structured results with proper error handling and debugging support.
    """

    @staticmethod
    async def perform_web_search(
        client: anthropic.AsyncAnthropic,
        query: str,
        debug: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Perform a web search using the native web search tool via Anthropic API.

        Uses the web_search_20250305 tool. The model will automatically
        decide whether to perform a search based on the query requirements.

        Args:
            client: Anthropic Claude client instance
            query: The search query to find information on the web
            debug: Enable debug output
            **kwargs: Additional search parameters:
                - max_uses: Maximum number of search tool uses (default: 5)

        Returns:
            Dictionary containing search results or error information
        """
        max_uses = kwargs.get('max_uses', 5)
        try:
            # Create user message with search query
            user_message = UserMessage(role="user", content=query)
            
            # Format message using MessageFormatter
            formatted_messages = MessageFormatter.format_messages([user_message])
            
            # Use shared web search system prompt for consistency
            web_search_system_prompt = DEFAULT_WEB_SEARCH_SYSTEM_PROMPT
            
            # Use the new Anthropic configuration system
            anthropic_config = get_anthropic_client_config()
            
            # Build API call parameters using the configuration system
            api_kwargs = anthropic_config.get_api_call_kwargs(
                system_prompt=web_search_system_prompt,
                messages=formatted_messages,
                tools=[{
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": max_uses
                }]
            )
            
            # Override some parameters specific to web search
            api_kwargs.update({
                "max_tokens": 4096,
                "temperature": 1.0
            })
            # Update thinking budget if thinking is enabled
            if "thinking" in api_kwargs:
                api_kwargs["thinking"]["budget_tokens"] = 2048
            
            # Call the API with web search tool (async version)
            response = await client.messages.create(**api_kwargs)
            
            # Extract response text and tool usage information
            response_text = ""
            tool_calls = []
            sources = []
            
            if response.content:
                for content_block in response.content:
                    if hasattr(content_block, 'text'):
                        response_text += content_block.text
                    elif hasattr(content_block, 'type') and content_block.type == 'tool_use':
                        # Track tool calls for debugging
                        tool_calls.append({
                            'tool_name': getattr(content_block, 'name', 'unknown'),
                            'tool_id': getattr(content_block, 'id', 'unknown'),
                            'input': getattr(content_block, 'input', {})
                        })
                        
            
            # Note: Unlike Gemini, Anthropic's web_search_20250305 tool doesn't expose
            # individual source URLs in the response structure. The search results
            # are synthesized into the response text directly.
            
            # Build structured result
            result = {
                "query": query,
                "response_text": response_text,
                "sources": sources,  # Empty for Anthropic as sources aren't exposed
                "total_sources": len(sources),
                "tool_calls": tool_calls,
                "note": "Anthropic web search synthesizes results directly into response text"
            }
             
            return result
            
        except Exception as e:
            error_msg = f"An error occurred during web search: {str(e)}"
            if debug:
                print(f"[WebSearch] Error: {error_msg}")
            return {"error": error_msg, "query": query}

from backend.infrastructure.llm.base.content_generators.image_prompt import BaseImagePromptGenerator

class ImagePromptGenerator(BaseImagePromptGenerator):
    """
    Handles text-to-image prompt generation using Anthropic Claude API.
    
    Creates detailed and effective prompts for image generation based on
    recent conversation context, with support for positive and negative prompts.
    """

    @staticmethod
    async def generate_text_to_image_prompt(
        client: anthropic.AsyncAnthropic,
        session_id: Optional[str] = None,
        debug: bool = False
    ) -> Optional[Dict[str, str]]:
        """
        Generate high-quality text-to-image prompts using recent conversation context.
        
        Args:
            client: Anthropic Claude client instance for API calls
            session_id: Optional session ID for conversation context
            debug: Enable debug output
            
        Returns:
            Dictionary with 'text_prompt' and 'negative_prompt' keys, or None if failed
        """
        try:
            # Get Anthropic configuration for model info
            llm_settings = get_llm_settings()
            llm_anthropic_config = llm_settings.get_anthropic_config()  # This has the 'model' attribute
            
            # Prepare generation context using inherited method with provider info
            context = ImagePromptGenerator.prepare_generation_context(
                session_id=session_id,
                llm_provider="anthropic",
                llm_model=llm_anthropic_config.model
            )
            
            # Build messages using inherited method
            messages = ImagePromptGenerator.build_messages_for_generation(context)
            
            # Use MessageFormatter for message format conversion
            formatted_messages = MessageFormatter.format_messages(messages)
            
            # Use the model from context (which now correctly uses Anthropic's model)
            model_for_text_to_image = context.get('model', llm_anthropic_config.model)

            response = await client.messages.create(
                model=model_for_text_to_image,
                max_tokens=4096,
                temperature=context.get('temperature', 1.0),
                system=context['system_prompt'],
                messages=cast(Any, formatted_messages)
            )

            if response.content and len(response.content) > 0:
                # Handle different content block types safely
                first_content = response.content[0]
                prompt_text = getattr(first_content, 'text', str(first_content))
                
                # Process response using inherited method
                return ImagePromptGenerator.process_generation_response(
                    prompt_text, context, session_id, debug
                )
            return None
            
        except Exception as e:
            if debug:
                print(f"[text_to_image] Error during prompt generation: {str(e)}")
            return None

