"""
Gemini-specific content generators using shared components.

Specialized generators that leverage shared logic while implementing
Gemini-specific API calls and response handling.
"""

from typing import Optional, Dict, Any
from google.genai import types
from backend.domain.models.messages import BaseMessage, UserMessage
from backend.config import get_text_to_image_settings, get_llm_settings

# Import shared components
from backend.infrastructure.llm.shared.content_generators import (
    SharedImagePromptGenerator, 
    SharedWebSearchGenerator
)
from backend.infrastructure.llm.shared.utils.text_processing import parse_title_response
from backend.infrastructure.llm.shared.constants.defaults import (
    DEFAULT_TITLE_MAX_LENGTH,
    DEFAULT_TITLE_GENERATION_TEMPERATURE,
    DEFAULT_WEB_SEARCH_TEMPERATURE)
from backend.infrastructure.llm.shared.constants.prompts import (
    DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT,
    TITLE_GENERATION_REQUEST_TEXT,
    DEFAULT_WEB_SEARCH_SYSTEM_PROMPT
)

# Import Gemini-specific components
from .config import get_gemini_client_config
from .debug import GeminiDebugger
from .message_formatter import GeminiMessageFormatter
from .response_processor import GeminiResponseProcessor


class GeminiTitleGenerator:
    """
    Gemini-specific title generation using shared logic where possible.
    """
    
    @staticmethod
    async def generate_title_from_messages(
        client,  # Gemini client instance
        first_user_message: BaseMessage,
        first_assistant_message: BaseMessage,
        title_generation_system_prompt: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate a concise conversation title based on the first message exchange.
        
        Uses Gemini API with shared processing logic.
        """
        try:
            # Read Gemini configuration
            gemini_config = get_gemini_client_config()
            
            system_prompt = title_generation_system_prompt or DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT
            
            # Configure title generation parameters
            title_config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=DEFAULT_TITLE_GENERATION_TEMPERATURE,
                max_output_tokens=gemini_config.model_settings.max_output_tokens
            )
            
            # Build message sequence, ending with user
            messages = [
                first_user_message,
                first_assistant_message,
                UserMessage(role="user", content=[{"type": "text", "text": TITLE_GENERATION_REQUEST_TEXT}])
            ]
            
            # Use MessageFormatter for unified message format conversion
            contents = GeminiMessageFormatter.format_messages_for_api(messages)
            
            # Get model from configuration
            llm_settings = get_llm_settings()
            gemini_config = llm_settings.get_gemini_config()
            model = gemini_config.model
            
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=title_config
            )
            
            # Extract response text using ResponseProcessor
            title_response_text = GeminiResponseProcessor.extract_text_content(response)
            
            # Parse title using shared utility function
            return parse_title_response(title_response_text, max_length=DEFAULT_TITLE_MAX_LENGTH)
            
        except Exception as e:
            print(f"Gemini title generation error: {str(e)}")
            return None


class GeminiWebSearchGenerator:
    """
    Gemini-specific web search using shared logic and Gemini's google_search tool.
    """
    
    @staticmethod
    async def perform_web_search(
        client,  # Gemini client instance
        query: str,
        debug: bool = False,
        max_uses: int = 5
    ) -> Dict[str, Any]:
        """
        Perform a web search using Google Search via the Gemini API.
        
        Uses Gemini's modern google_search tool with shared result processing.
        """
        try:
            if debug:
                print(f"[WebSearch] Performing search for query: {query}")
            
            # Prepare search context using shared logic
            context = SharedWebSearchGenerator.prepare_search_context(
                query=query,
                system_prompt=DEFAULT_WEB_SEARCH_SYSTEM_PROMPT,
                temperature=DEFAULT_WEB_SEARCH_TEMPERATURE
            )
            
            # Read Gemini configuration
            gemini_config = get_gemini_client_config()
            
            # Configure the Gemini model with the web search tool
            search_config = types.GenerateContentConfig(
                system_instruction=context['system_prompt'],
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=context['temperature'],
                max_output_tokens=gemini_config.model_settings.max_output_tokens
            )
            
            # Format message using MessageFormatter
            contents = GeminiMessageFormatter.format_messages_for_api([context['user_message']])
            
            if debug:
                GeminiDebugger.print_debug_request(contents, search_config)
                print(f"[WebSearch] Note: max_uses={max_uses} parameter ignored for Gemini (API limitation)")
            
            # Get model from configuration
            llm_settings = get_llm_settings()
            gemini_config = llm_settings.get_gemini_config()
            model = gemini_config.model
            
            # Call the model with the query
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=search_config
            )
            
            if debug:
                print(f"[WebSearch] API call completed")
                GeminiDebugger.print_debug_response(response)
            
            # Check for candidates
            if hasattr(response, 'candidates') and response.candidates:
                # Extract sources using ResponseProcessor
                sources = GeminiResponseProcessor.extract_web_search_sources(response, debug=debug)
                
                # Extract response text using ResponseProcessor
                response_text = GeminiResponseProcessor.extract_text_content(response)
                
                # Build structured result
                result = {
                    "query": query,
                    "response_text": response_text,
                    "sources": sources,
                    "total_sources": len(sources),
                    "error": None
                }
                
                if debug:
                    print(f"[WebSearch] Extracted {len(sources)} sources")
                    print(f"[WebSearch] Response text length: {len(response_text)}")
                
                return result
            else:
                if debug:
                    print("[WebSearch] No candidates found in response")
                return SharedWebSearchGenerator.format_search_error(query, "No search results found")
                
        except Exception as e:
            error_msg = f"An error occurred during web search: {str(e)}"
            if debug:
                print(f"[WebSearch] Error: {error_msg}")
            return SharedWebSearchGenerator.format_search_error(query, error_msg)

class GeminiImagePromptGenerator:
    """
    Gemini-specific image prompt generation using shared logic.
    """
    
    @staticmethod
    async def generate_text_to_image_prompt(
        client,  # Gemini client instance
        session_id: Optional[str] = None,
        debug: bool = False
    ) -> Optional[Dict[str, str]]:
        """
        Generate high-quality text-to-image prompts using shared context preparation.
        """
        try:
            # Prepare generation context using shared logic
            context = SharedImagePromptGenerator.prepare_generation_context(
                session_id=session_id
            )
            
            # Note: Context preparation already handles empty conversation validation
            
            # Read Gemini configuration
            gemini_config = get_gemini_client_config()
            
            # Create API call configuration
            config_kwargs = {
                "system_instruction": context['system_prompt'],
                "safety_settings": gemini_config.safety_settings.to_gemini_format(),
                "temperature": context['temperature'],
                "max_output_tokens": gemini_config.model_settings.max_output_tokens
            }
            
            # Add thinking configuration if applicable
            model_for_text_to_image = context.get('model', gemini_config.model_settings.model)
            if (model_for_text_to_image.startswith("gemini-2.5") and 
                gemini_config.model_settings.enable_thinking_for_gemini_2_5):
                config_kwargs["thinking_config"] = types.ThinkingConfig(
                    include_thoughts=gemini_config.model_settings.include_thoughts_in_response
                )
            
            prompt_config = types.GenerateContentConfig(**config_kwargs)
            
            # Build messages using shared logic
            messages = SharedImagePromptGenerator.build_messages_for_generation(context)
            
            # Format messages using Gemini formatter
            contents = GeminiMessageFormatter.format_messages_for_api(messages)
            
            if debug:
                print("[text_to_image] Formatted contents (simplified):")
                GeminiDebugger.print_debug_request(contents, prompt_config)
            
            response = client.models.generate_content(
                model=model_for_text_to_image,
                contents=contents,
                config=prompt_config
            )
            
            if debug:
                print("[text_to_image] Response received:")
                GeminiDebugger.print_debug_response(response)
            
            # Extract response text using ResponseProcessor
            prompt_text = GeminiResponseProcessor.extract_text_content(response)
            
            if prompt_text:
                # Process response using shared logic
                return SharedImagePromptGenerator.process_generation_response(
                    prompt_text, context, session_id, debug
                )
            
            return None
            
        except Exception as e:
            if debug:
                print(f"[text_to_image] Error during prompt generation: {str(e)}")
            return None