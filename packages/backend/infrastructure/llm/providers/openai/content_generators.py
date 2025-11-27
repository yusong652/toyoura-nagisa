"""
Content generation utilities for OpenAI API.

Specialized generators for creating titles, image prompts, and other derived content
based on conversation context. Provides OpenAI-specific implementations while
maintaining compatibility with the unified content generation interface.
"""

from typing import Optional, Dict, Any, List
from openai.types.responses import Response, ResponseOutputMessage
from openai.types.responses.response_output_text import ResponseOutputText, AnnotationURLCitation
from backend.domain.models.messages import BaseMessage
from backend.config import get_llm_settings
from backend.infrastructure.llm.base.content_generators.web_search import BaseWebSearchGenerator
from backend.infrastructure.llm.base.content_generators.title import BaseTitleGenerator
from backend.infrastructure.llm.shared.constants import (
    DEFAULT_WEB_SEARCH_SYSTEM_PROMPT,
    DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT
)
from backend.infrastructure.llm.shared.utils.text_processing import parse_title_response
from .response_processor import OpenAIResponseProcessor
from .message_formatter import OpenAIMessageFormatter
from .debug import OpenAIDebugger
from .constants import *


class TitleGenerator(BaseTitleGenerator):
    """
    Handles conversation title generation using OpenAI API.

    Generates concise, descriptive titles based on the first exchange
    in a conversation to help users identify and organize their chats.
    Inherits from BaseTitleGenerator for consistency with other providers.
    """

    @staticmethod
    async def generate_title_from_messages(
        client,  # OpenAI client instance
        latest_messages: List[BaseMessage]
    ) -> Optional[str]:
        """
        Generate a concise conversation title based on recent messages.

        Args:
            client: OpenAI client instance for API calls
            latest_messages: Recent conversation messages to generate title from

        Returns:
            Generated title string, or None if generation fails
        """
        try:
            # Use base class validation
            if not BaseTitleGenerator.validate_messages_for_title(latest_messages):
                return None

            # Use shared system prompt for title generation
            system_prompt = DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT

            # Extract text content from messages and assemble into conversation context
            # This approach avoids sending complex message structures
            conversation_parts = []
            for msg in latest_messages:
                role = getattr(msg, 'role', 'user')
                content = getattr(msg, 'content', '')

                # Handle content list or string
                if isinstance(content, list):
                    # Extract text from content blocks
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

            # Create simple message with conversation as context
            from backend.domain.models.messages import UserMessage
            simple_message = UserMessage(
                role="user",
                content=f"Please generate a concise title based on the following conversation:\n\n{conversation_context}"
            )

            # Format message to Responses API input
            input_items = OpenAIMessageFormatter.format_messages([simple_message])

            api_kwargs = {
                "model": DEFAULT_TITLE_MODEL,
                "instructions": system_prompt,
                "input": input_items,
                "temperature": TITLE_GENERATION_TEMPERATURE,
                "max_output_tokens": 100
            }

            response: Response = await client.responses.create(**api_kwargs)

            if not response.output:
                return None

            title_response_text = OpenAIResponseProcessor.extract_text_content(response)

            # Parse title using shared utility function
            return parse_title_response(title_response_text, max_length=TITLE_MAX_LENGTH)

        except Exception as e:
            print(f"OpenAI title generation error: {str(e)}")
            return None


from backend.infrastructure.llm.base.content_generators.image_prompt import BaseImagePromptGenerator

class ImagePromptGenerator(BaseImagePromptGenerator):
    """
    Handles text-to-image prompt generation using OpenAI API.
    
    Creates detailed and effective prompts for image generation based on
    recent conversation context, with support for positive and negative prompts.
    """

    @staticmethod
    async def generate_text_to_image_prompt(
        client,  # OpenAI client instance
        session_id: Optional[str] = None,
        debug: bool = False
    ) -> Optional[Dict[str, str]]:
        """
        Generate high-quality text-to-image prompts using recent conversation context.
        
        Args:
            client: OpenAI client instance for API calls
            session_id: Optional session ID for conversation context
            debug: Enable debug output
            
        Returns:
            Dictionary with 'text_prompt' and 'negative_prompt' keys, or None if failed
        """
        try:
            # Get OpenAI configuration for model info
            llm_settings = get_llm_settings()
            llm_openai_config = llm_settings.get_openai_config()  # This has the 'model' attribute
            
            # Prepare generation context using inherited method with provider info
            context = ImagePromptGenerator.prepare_generation_context(
                session_id=session_id,
                llm_provider="openai",
                llm_model=llm_openai_config.model
            )
            
            # Build messages using inherited method
            messages = ImagePromptGenerator.build_messages_for_generation(context)
            
            # Format messages to Responses API input
            input_items = OpenAIMessageFormatter.format_messages(messages)

            model_for_text_to_image = context.get('model', llm_openai_config.model)

            api_kwargs = {
                "model": model_for_text_to_image,
                "instructions": context['system_prompt'],
                "input": input_items,
                "temperature": context.get('temperature', 1.0),
                "max_output_tokens": 1024
            }

            if debug:
                OpenAIDebugger.print_debug_request_payload(api_kwargs)

            response: Response = await client.responses.create(**api_kwargs)

            if debug:
                OpenAIDebugger.log_raw_response(response)

            prompt_text = OpenAIResponseProcessor.extract_text_content(response)
            
            if not prompt_text:
                return None
            
            if debug:
                print(f"[text_to_image] Raw response: {prompt_text[:200]}...")
            
            # Process response using inherited method
            return ImagePromptGenerator.process_generation_response(
                prompt_text, context, session_id, debug
            )
            
        except Exception as e:
            if debug:
                print(f"[text_to_image] Error during prompt generation: {str(e)}")
            return None


class WebSearchGenerator(BaseWebSearchGenerator):
    """
    Handles web search using OpenAI's native web search capabilities.

    Uses the gpt-5 model with web_search tool to perform searches
    and return structured results with sources.
    """

    @staticmethod
    async def perform_web_search(
        client,  # OpenAI client instance
        query: str,
        debug: bool = False,
        **kwargs  # Accept additional parameters for compatibility (e.g., max_uses)
    ) -> Dict[str, Any]:
        """
        Perform a web search using OpenAI's native web search API.
        
        Args:
            client: OpenAI client instance for API calls
            query: The search query to find information on the web
            debug: Enable debug output
            **kwargs: Additional search parameters (accepted for compatibility but not used)
            
        Returns:
            Dictionary containing search results with sources and metadata
        """
        if kwargs:
            print(f"[WebSearchGenerator] Additional params (ignored): {kwargs}")
        
        try:
            # Use base class debug method
            BaseWebSearchGenerator.debug_search_start(query, debug)
            
            # Create user message using base class method
            user_message = BaseWebSearchGenerator.create_search_user_message(query)
            
            # Format message to Responses API input
            input_items = OpenAIMessageFormatter.format_messages([user_message])
            
            # Prepare API kwargs for web search (Responses API)
            api_kwargs = {
                "model": "gpt-5",  # GPT-5 supports web_search tool in Responses API
                "instructions": DEFAULT_WEB_SEARCH_SYSTEM_PROMPT,
                "input": input_items,
                "max_output_tokens": 2048,
                "tools": [{"type": "web_search"}],
                "metadata": {"generator": "web_search"}
            }

            if debug:
                OpenAIDebugger.print_debug_request_payload(api_kwargs)

            # Perform the web search using async API
            response: Response = await client.responses.create(**api_kwargs)

            if debug:
                OpenAIDebugger.log_raw_response(response)

            # Use base class debug method
            BaseWebSearchGenerator.debug_search_complete(debug)
            
            if not response.output:
                if debug:
                    print("[WebSearch] No response content found")
                return BaseWebSearchGenerator.format_search_error(query, "No search results found")
            
            response_text = ""
            sources: List[Dict[str, Any]] = []
            
            for item in response.output:
                if not isinstance(item, ResponseOutputMessage):
                    continue
                
                for part in item.content:
                    if not isinstance(part, ResponseOutputText):
                        continue
                    
                    text_segment = part.text or ""
                    response_text += text_segment
                    
                    for annotation in part.annotations or []:
                        if isinstance(annotation, AnnotationURLCitation):
                            snippet = text_segment[
                                annotation.start_index:annotation.end_index
                            ]
                            sources.append({
                                "title": getattr(annotation, "title", ""),
                                "url": getattr(annotation, "url", ""),
                                "snippet": snippet
                            })
                            print(f"[WebSearchGenerator] Added source: {annotation.url}")
            
            if not sources:
                print("[WebSearchGenerator] No URL citations returned; using response text only")
            
            result = BaseWebSearchGenerator.format_search_result(
                query=query,
                response_text=response_text,
                sources=sources
            )
            
            BaseWebSearchGenerator.debug_search_results(
                len(sources), len(response_text), debug
            )
            
            return result

        except Exception as e:
            error_msg = f"An error occurred during web search: {str(e)}"
            print(f"[WebSearchGenerator] ERROR: {error_msg}")
            import traceback
            print(f"[WebSearchGenerator] Traceback: {traceback.format_exc()}")
            if debug:
                print(f"[WebSearch] Error: {error_msg}")
            return BaseWebSearchGenerator.format_search_error(query, error_msg)
