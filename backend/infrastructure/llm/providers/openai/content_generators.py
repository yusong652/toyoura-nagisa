"""
Content generation utilities for OpenAI API.

Specialized generators for creating titles, image prompts, and other derived content
based on conversation context. Provides OpenAI-specific implementations while
maintaining compatibility with the unified content generation interface.
"""

from typing import Optional, Dict, Any, List
import re
import json
from backend.domain.models.messages import BaseMessage, UserMessage
from backend.config import get_text_to_image_settings, get_llm_settings
from backend.infrastructure.storage.session_manager import get_latest_n_messages
from .message_formatter import OpenAIMessageFormatter
from .debug import OpenAIDebugger
from .constants import *


class TitleGenerator:
    """
    Handles conversation title generation using OpenAI API.
    
    Generates concise, descriptive titles based on the first exchange
    in a conversation to help users identify and organize their chats.
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
            
            # Default system prompt for title generation
            system_prompt = (
                "You are a professional conversation title generator. Generate a concise title (5-15 words) "
                "that accurately summarizes the main topic or intent of the conversation. "
                "Put the title in <title></title> tags and output nothing else."
            )
            
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
            
            # Debug payload printing (similar to Gemini)
            if debug:
                print("[DEBUG] Title generation API call:")
                OpenAIDebugger.print_debug_request_payload(api_kwargs)
            
            # Use smaller model for title generation
            response = client.chat.completions.create(**api_kwargs)
            
            # Debug response printing (similar to Gemini)
            if debug:
                print("[DEBUG] Title generation response:")
                OpenAIDebugger.log_raw_response(response)
            
            if not response.choices:
                return None
            
            title_response_text = response.choices[0].message.content or ""
            
            # Extract title from tags
            title_match = re.search(r'<title>(.*?)</title>', title_response_text, re.DOTALL)
            if title_match:
                title = title_match.group(1).strip()
                if title and len(title) <= TITLE_MAX_LENGTH:
                    return title
            
            # Fallback: clean the response directly
            cleaned_title = title_response_text.strip().strip('"\'').strip()
            if cleaned_title and len(cleaned_title) <= TITLE_MAX_LENGTH:
                return cleaned_title
            
            return None
            
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


class WebSearchGenerator:
    """
    Handles web search using OpenAI API.
    
    Note: OpenAI doesn't have built-in web search capabilities like Gemini.
    This implementation provides a placeholder that should integrate with
    MCP tools for actual web search functionality.
    """

    @staticmethod
    async def perform_web_search(
        client,  # OpenAI client instance
        query: str,
        debug: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Perform a web search using MCP tools (OpenAI doesn't have built-in search).
        
        Args:
            client: OpenAI client instance (not used for search)
            query: The search query
            debug: Enable debug output
            
        Returns:
            Dictionary indicating that OpenAI requires external tools for search
        """
        if debug:
            print(f"[WebSearch] OpenAI client requested search for: {query}")
            print("[WebSearch] Note: OpenAI requires external MCP tools for web search")
        
        return {
            "error": "OpenAI client requires MCP web search tools",
            "query": query,
            "suggestion": "Use MCP tools like 'web_search' or 'google_search' for web search functionality",
            "sources": [],
            "total_sources": 0
        }