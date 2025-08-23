"""
Content generation utilities for OpenAI API.

Specialized generators for creating titles, image prompts, and other derived content
based on conversation context. Provides OpenAI-specific implementations while
maintaining compatibility with the unified content generation interface.
"""

from typing import Optional, Dict, Any, List
from backend.domain.models.messages import BaseMessage, UserMessage
from backend.config import get_llm_settings
from backend.infrastructure.llm.base.content_generators import (
    BaseWebSearchGenerator, 
    BaseTitleGenerator
)
from backend.infrastructure.llm.shared.constants import (
    DEFAULT_WEB_SEARCH_SYSTEM_PROMPT,
    DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT
)
from backend.infrastructure.llm.shared.utils.text_processing import parse_title_response
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
        latest_messages: List[BaseMessage],
        debug: bool = False
    ) -> Optional[str]:
        """
        Generate a concise conversation title based on recent messages.
        
        Args:
            client: OpenAI client instance for API calls
            latest_messages: Recent conversation messages to generate title from
            debug: Enable debug logging for API calls
            
        Returns:
            Generated title string, or None if generation fails
        """
        try:
            if not latest_messages or len(latest_messages) < 2:
                return None
            
            # Use shared system prompt for title generation
            system_prompt = DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT
            
            # Build conversation messages
            messages = list(latest_messages) + [
                UserMessage(role="user", content=[{"type": "text", "text": "Please generate a title for the above conversation"}])
            ]
            
            # Format messages for OpenAI API
            formatted_messages = OpenAIMessageFormatter.format_messages(messages)
            
            # Add system prompt
            api_messages = [{"role": "system", "content": system_prompt}] + formatted_messages
            
            # Prepare API kwargs for debugging
            api_kwargs = {
                "model": DEFAULT_TITLE_MODEL,
                "messages": api_messages,
                "temperature": TITLE_GENERATION_TEMPERATURE,
                "max_tokens": 100
            }
            
            # Use smaller model for title generation
            response = client.chat.completions.create(**api_kwargs)
            
            # Debug response printing (similar to Gemini)
            if debug:
                print("[DEBUG] Title generation response:")
                OpenAIDebugger.log_raw_response(response)
            
            if not response.choices:
                return None
            
            title_response_text = response.choices[0].message.content or ""
            
            # Parse title using shared utility function
            return parse_title_response(title_response_text, max_length=TITLE_MAX_LENGTH, debug=debug)
            
        except Exception as e:
            print(f"OpenAI title generation error: {str(e)}")
            return None


from backend.infrastructure.llm.base.content_generators import BaseImagePromptGenerator

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
            
            # Format messages using OpenAI formatter
            formatted_messages = OpenAIMessageFormatter.format_messages(messages)
            
            # Add system prompt
            api_messages = [{"role": "system", "content": context['system_prompt']}] + formatted_messages
            
            if debug:
                OpenAIDebugger.print_debug_request_payload({
                    'model': DEFAULT_IMAGE_PROMPT_MODEL,
                    'messages': api_messages
                })
            
            # Use the model from context (which now correctly uses OpenAI's model)
            model_for_text_to_image = context.get('model', llm_openai_config.model)
            
            # Call OpenAI API
            response = client.chat.completions.create(
                model=model_for_text_to_image,
                messages=api_messages,
                temperature=context.get('temperature', 1.0),
                max_tokens=1024
            )
            
            # Debug response printing (similar to Gemini)
            if debug:
                print("[DEBUG] Image prompt generation response:")
                OpenAIDebugger.log_raw_response(response)
            
            if not response.choices:
                return None
            
            prompt_text = response.choices[0].message.content or ""
            
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
    
    Uses the gpt-4o-search-preview model with web_search_options to perform
    searches and return structured results with sources.
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
        print(f"[WebSearchGenerator] perform_web_search called with query: {query}")
        print(f"[WebSearchGenerator] Debug mode: {debug}")
        print(f"[WebSearchGenerator] Client type: {type(client)}")
        if kwargs:
            print(f"[WebSearchGenerator] Additional params (ignored): {kwargs}")
        
        try:
            # Use base class debug method
            BaseWebSearchGenerator.debug_search_start(query, debug)
            
            # Create user message using base class method
            user_message = BaseWebSearchGenerator.create_search_user_message(query)
            
            # Format message for OpenAI API
            formatted_messages = OpenAIMessageFormatter.format_messages([user_message])
            
            # Build API messages with system prompt
            api_messages = [
                {"role": "system", "content": DEFAULT_WEB_SEARCH_SYSTEM_PROMPT}
            ] + formatted_messages
            
            # Prepare API kwargs for web search
            # Note: gpt-4o-search-preview doesn't support temperature parameter
            api_kwargs = {
                "model": "gpt-4o-search-preview",  # Specific model for web search
                "web_search_options": {},  # Enable web search
                "messages": api_messages,
                "max_tokens": 2048
            }
            
            print(f"[WebSearchGenerator] About to call OpenAI API with model: {api_kwargs['model']}")
            print(f"[WebSearchGenerator] Web search options: {api_kwargs.get('web_search_options', {})}")
            
            # Debug request
            if debug:
                print("[DEBUG] Web search API call:")
                OpenAIDebugger.print_debug_request_payload(api_kwargs)
            
            # Perform the web search
            print("[WebSearchGenerator] Making API call...")
            # Check if client is async or sync
            if hasattr(client, 'chat') and hasattr(client.chat, 'completions'):
                response = client.chat.completions.create(**api_kwargs)     
            # Debug response
            if debug:
                print("[DEBUG] Web search response:")
                OpenAIDebugger.log_raw_response(response)
            
            # Use base class debug method
            BaseWebSearchGenerator.debug_search_complete(debug)
            
            if response.choices and response.choices[0].message:
                response_text = response.choices[0].message.content or ""
                print(f"[WebSearchGenerator] Response text length: {len(response_text)}")
                
                # Extract sources from annotations in the response
                sources = []
                
                # Check if the response has annotations with url_citations
                print(f"[WebSearchGenerator] Checking for annotations...")
                print(f"[WebSearchGenerator] Has 'annotations' attr: {hasattr(response.choices[0].message, 'annotations')}")
                
                if hasattr(response.choices[0].message, 'annotations') and response.choices[0].message.annotations:
                    print(f"[WebSearchGenerator] Found {len(response.choices[0].message.annotations)} annotations")
                    for i, annotation in enumerate(response.choices[0].message.annotations):
                        print(f"[WebSearchGenerator] Annotation {i}: type={getattr(annotation, 'type', 'unknown')}")
                        if annotation.type == 'url_citation' and hasattr(annotation, 'url_citation'):
                            citation = annotation.url_citation
                            sources.append({
                                'title': citation.title if hasattr(citation, 'title') else '',
                                'url': citation.url if hasattr(citation, 'url') else '',
                                'snippet': response_text[citation.start_index:citation.end_index] if hasattr(citation, 'start_index') and hasattr(citation, 'end_index') else ''
                            })
                            print(f"[WebSearchGenerator] Added source: {citation.url if hasattr(citation, 'url') else 'no-url'}")
                    
                    if debug:
                        print(f"[WebSearch] Found {len(sources)} URL citations in annotations")
                else:
                    print("[WebSearchGenerator] No annotations found in response")
                
                # If no sources found, log for debugging
                if not sources:
                    print(f"[WebSearchGenerator] No sources found in annotations, using response text only")
                    if debug:
                        print("[WebSearch] No sources found in annotations, using response text only")
                
                # Build structured result using base class method
                result = BaseWebSearchGenerator.format_search_result(
                    query=query,
                    response_text=response_text,
                    sources=sources
                )
                
                # Use base class debug method
                BaseWebSearchGenerator.debug_search_results(
                    len(sources), len(response_text), debug
                )
                
                return result
            else:
                if debug:
                    print("[WebSearch] No response content found")
                return BaseWebSearchGenerator.format_search_error(
                    query, "No search results found"
                )
                
        except Exception as e:
            error_msg = f"An error occurred during web search: {str(e)}"
            print(f"[WebSearchGenerator] ERROR: {error_msg}")
            import traceback
            print(f"[WebSearchGenerator] Traceback: {traceback.format_exc()}")
            if debug:
                print(f"[WebSearch] Error: {error_msg}")
            return BaseWebSearchGenerator.format_search_error(query, error_msg)