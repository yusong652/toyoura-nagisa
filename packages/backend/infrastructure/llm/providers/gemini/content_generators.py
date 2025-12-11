"""
Gemini-specific content generators using shared components.

Specialized generators that leverage shared logic while implementing
Gemini-specific API calls and response handling.
"""

from typing import Optional, Dict, Any, List
from google.genai import types
from backend.domain.models.messages import BaseMessage
from backend.config import get_llm_settings

# Import base components
from backend.infrastructure.llm.base.content_generators.image_prompt import BaseImagePromptGenerator
from backend.infrastructure.llm.base.content_generators.title import BaseTitleGenerator
from backend.infrastructure.llm.base.content_generators.web_search import BaseWebSearchGenerator
from backend.infrastructure.llm.base.content_generators.video_prompt import BaseVideoPromptGenerator
from backend.infrastructure.llm.shared.utils.text_processing import parse_title_response
from backend.infrastructure.llm.shared.constants.defaults import (
    DEFAULT_TITLE_MAX_LENGTH,
    DEFAULT_TITLE_GENERATION_TEMPERATURE,
    DEFAULT_WEB_SEARCH_TEMPERATURE)
from backend.infrastructure.llm.shared.constants.prompts import (
    DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT,
    DEFAULT_WEB_SEARCH_SYSTEM_PROMPT,
    DEFAULT_VIDEO_PROMPT_SYSTEM_PROMPT
)

# Import Gemini-specific components
from .config import get_gemini_client_config
from .debug import GeminiDebugger
from .message_formatter import GeminiMessageFormatter
from .response_processor import GeminiResponseProcessor


class GeminiTitleGenerator(BaseTitleGenerator):
    """
    Gemini-specific title generation using shared logic where possible.
    """

    @staticmethod
    async def generate_title_from_messages(
        client,  # Gemini client instance
        latest_messages: List[BaseMessage],
        debug: bool = False
    ) -> Optional[str]:
        """
        Generate a concise conversation title based on recent messages.

        Args:
            client: Gemini client instance for API calls
            latest_messages: Recent conversation messages to generate title from
            debug: Enable debug output for troubleshooting (unused, kept for interface consistency)

        Returns:
            Generated title string, or None if generation fails
        """
        try:
            # Explicit validation before base class validation
            if latest_messages is None or not latest_messages:
                return None

            # Use base class validation
            if not BaseTitleGenerator.validate_messages_for_title(latest_messages):
                return None

            # Read Gemini configuration
            gemini_config = get_gemini_client_config()

            system_prompt = DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT

            # Extract text content from messages and assemble into conversation context
            # This unified approach is consistent with other providers (Anthropic, OpenAI, Kimi, OpenRouter)
            conversation_parts = []
            for msg in latest_messages:
                role = getattr(msg, 'role', 'user')
                content = getattr(msg, 'content', '')

                # Handle content list or string
                if isinstance(content, list):
                    # Extract text from content blocks (skip thinking blocks, tool_use, tool_result)
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict):
                            block_type = block.get('type')
                            if block_type == 'text':
                                text_parts.append(block.get('text', ''))
                    content_str = '\n'.join(text_parts)
                else:
                    content_str = str(content) if content else ''

                # Skip messages with no text content
                if not content_str or not content_str.strip():
                    continue

                # Add to conversation with role label
                role_label = "User" if role == "user" else "Assistant"
                conversation_parts.append(f"{role_label}: {content_str}")

            # Ensure we have at least some conversation content
            if not conversation_parts:
                return None

            # Combine conversation into single context
            conversation_context = '\n'.join(conversation_parts)

            # Build simple content with conversation as context
            # This prevents issues with complex message structures
            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part(text=f"Please generate a concise title based on the following conversation:\n\n{conversation_context}")]
                )
            ]

            # Configure title generation parameters
            title_config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=DEFAULT_TITLE_GENERATION_TEMPERATURE,
                max_output_tokens=2048  # Large buffer for non-thinking models
            )

            # Get model from configuration
            llm_settings = get_llm_settings()
            gemini_config = llm_settings.get_gemini_config()

            # Use a reliable non-thinking model for title generation
            # Thinking models (gemini-2.5-pro, gemini-exp-*) may refuse or return
            # empty responses for simple tasks like title generation
            title_generation_model = "gemini-2.0-flash"

            # Use async non-streaming for better performance
            response = await client.aio.models.generate_content(
                model=title_generation_model,
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


class GeminiWebSearchGenerator(BaseWebSearchGenerator):
    """
    Gemini-specific web search using shared logic and Gemini's google_search tool.
    """
    
    @staticmethod
    async def perform_web_search(
        client,  # Gemini client instance
        query: str,
        debug: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Perform a web search using Google Search via the Gemini API.
        
        Uses Gemini's modern google_search tool with shared result processing.
        """
        try:
            # Extract max_uses from kwargs with default value
            max_uses = kwargs.get('max_uses', 5)

            # Use base class debug method
            BaseWebSearchGenerator.debug_search_start(query, debug)
            
            # Create user message using base class method
            user_message = BaseWebSearchGenerator.create_search_user_message(query)
            
            # Read Gemini configuration
            gemini_config = get_gemini_client_config()
            
            # Configure the Gemini model with the web search tool  
            search_config = types.GenerateContentConfig(
                system_instruction=DEFAULT_WEB_SEARCH_SYSTEM_PROMPT,
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=DEFAULT_WEB_SEARCH_TEMPERATURE,
                max_output_tokens=gemini_config.model_settings.max_output_tokens
            )
            
            # Format message using MessageFormatter
            contents = GeminiMessageFormatter.format_messages([user_message])
            
            # Get model from configuration
            llm_settings = get_llm_settings()
            gemini_config = llm_settings.get_gemini_config()
            model = gemini_config.model

            if debug:
                GeminiDebugger.print_request(contents, search_config, model)
                print(f"[WebSearch] Note: max_uses={max_uses} parameter ignored for Gemini (API limitation)")
            
            # Call the model with the query (async version)
            response = await client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=search_config
            )
            
            # Use base class debug method
            BaseWebSearchGenerator.debug_search_complete(debug)
            if debug:
                GeminiDebugger.print_response(response)
            
            # Check for candidates
            if response.candidates:
                # Extract sources using ResponseProcessor
                sources = GeminiResponseProcessor.extract_web_search_sources(response, debug=debug)
                
                # Extract response text using ResponseProcessor
                response_text = GeminiResponseProcessor.extract_text_content(response)
                
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
                    print("[WebSearch] No candidates found in response")
                return BaseWebSearchGenerator.format_search_error(
                    query, "No search results found"
                )
                
        except Exception as e:
            error_msg = f"An error occurred during web search: {str(e)}"
            if debug:
                print(f"[WebSearch] Error: {error_msg}")
            return BaseWebSearchGenerator.format_search_error(query, error_msg)

class GeminiImagePromptGenerator(BaseImagePromptGenerator):
    """
    Gemini-specific image prompt generation using direct implementation.
    """

    @staticmethod
    async def generate_text_to_image_prompt(
        client,  # Gemini client instance
        session_id: Optional[str] = None,
        debug: bool = False
    ) -> Optional[Dict[str, str]]:
        """
        Generate high-quality text-to-image prompts using Gemini API.

        Args:
            client: Gemini client instance
            session_id: Optional session ID for conversation context
            debug: Enable debug output

        Returns:
            Dictionary with 'text_prompt' and 'negative_prompt' keys, or None if failed
        """
        try:
            # Get configuration
            from backend.config import get_llm_settings, get_text_to_image_settings
            llm_settings = get_llm_settings()
            llm_gemini_config = llm_settings.get_gemini_config()
            text_to_image_settings = get_text_to_image_settings()
            gemini_client_config = get_gemini_client_config()

            # Prepare context using inherited method
            context = GeminiImagePromptGenerator.prepare_generation_context(
                session_id=session_id,
                llm_provider="gemini",
                llm_model=llm_gemini_config.model
            )

            # Build messages using inherited method
            messages = GeminiImagePromptGenerator.build_messages_for_generation(context)

            # Format messages using Gemini formatter
            contents = GeminiMessageFormatter.format_messages(messages)

            # Create API call configuration
            config_kwargs = {
                "system_instruction": context['system_prompt'],
                "safety_settings": gemini_client_config.safety_settings.to_gemini_format(),
                "temperature": context['temperature'],
                "max_output_tokens": gemini_client_config.model_settings.max_output_tokens
            }

            # Use model from context
            model = context.get('model', llm_gemini_config.model)

            # Add thinking configuration based on model version
            if gemini_client_config.model_settings.enable_thinking:
                if model.startswith("gemini-3"):
                    config_kwargs["thinking_config"] = types.ThinkingConfig(
                        thinking_level=types.ThinkingLevel.HIGH,
                        include_thoughts=gemini_client_config.model_settings.include_thoughts_in_response
                    )
                elif model.startswith("gemini-2.5"):
                    config_kwargs["thinking_config"] = types.ThinkingConfig(
                        thinking_budget=-1,
                        include_thoughts=gemini_client_config.model_settings.include_thoughts_in_response
                    )

            prompt_config = types.GenerateContentConfig(**config_kwargs)

            if debug:
                print("[text_to_image] Gemini API call configuration:")
                GeminiDebugger.print_request(contents, prompt_config, model)

            # Use async non-streaming for better performance
            response = await client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=prompt_config
            )

            if debug:
                print("[text_to_image] Gemini API response:")
                GeminiDebugger.print_response(response)

            # Extract response text
            prompt_text = GeminiResponseProcessor.extract_text_content(response)

            if prompt_text:
                # Process response using inherited method
                return GeminiImagePromptGenerator.process_generation_response(
                    prompt_text, context, session_id, debug
                )

            return None

        except Exception as e:
            if debug:
                print(f"[text_to_image] Gemini prompt generation error: {str(e)}")
            raise


class GeminiVideoPromptGenerator(BaseVideoPromptGenerator):
    """
    Gemini-specific video prompt generation using direct implementation.
    """

    @staticmethod
    async def generate_video_prompt(
        client,  # Gemini client instance
        original_prompt: str,
        image_base64: Optional[str] = None,
        motion_type: str = "cinematic",
        few_shot_history: Optional[List[Dict[str, Any]]] = None,
        session_id: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        """
        Generate optimized video prompt using Gemini API.

        Args:
            client: Gemini client instance
            original_prompt: Original static image generation prompt (not used directly)
            image_base64: Optional base64 encoded image (not sent to LLM)
            motion_type: Type of motion for the video
            few_shot_history: Optional few-shot examples (loaded from session if not provided)
            session_id: Session ID for context and history

        Returns:
            Dict with 'video_prompt' and 'negative_prompt' keys, or None if failed
        """
        try:
            # Get configuration
            from backend.config import get_llm_settings, get_image_to_video_settings
            llm_settings = get_llm_settings()
            llm_gemini_config = llm_settings.get_gemini_config()
            image_to_video_settings = get_image_to_video_settings()
            gemini_client_config = get_gemini_client_config()
            debug = llm_settings.debug

            # Convert motion_type to motion_style description
            motion_descriptions = {
                "gentle": "subtle, gentle movements like gentle breeze, slow motion, peaceful transitions",
                "dynamic": "energetic, dynamic motion with action sequences and fast movements",
                "cinematic": "cinematic camera movements, smooth panning, professional film-like motion",
                "loop": "seamless looping motion with cyclic, repeating patterns"
            }
            motion_style = motion_descriptions.get(motion_type, motion_descriptions["cinematic"])

            # Prepare context using inherited method
            context = GeminiVideoPromptGenerator.prepare_video_context(
                session_id=session_id,
                motion_style=motion_style,
                llm_provider="gemini",
                llm_model=llm_gemini_config.model
            )

            # Build messages using inherited method
            messages = GeminiVideoPromptGenerator.build_video_messages(context)

            # Format messages using Gemini formatter
            contents = GeminiMessageFormatter.format_messages(messages)

            # Create API call configuration
            config_kwargs = {
                "system_instruction": context['system_prompt'],
                "safety_settings": gemini_client_config.safety_settings.to_gemini_format(),
                "temperature": context['temperature'],
                "max_output_tokens": gemini_client_config.model_settings.max_output_tokens
            }

            # Use model from context
            model = context.get('model', llm_gemini_config.model)

            # Add thinking configuration based on model version
            if gemini_client_config.model_settings.enable_thinking:
                if model.startswith("gemini-3"):
                    config_kwargs["thinking_config"] = types.ThinkingConfig(
                        thinking_level=types.ThinkingLevel.HIGH,
                        include_thoughts=gemini_client_config.model_settings.include_thoughts_in_response
                    )
                elif model.startswith("gemini-2.5"):
                    config_kwargs["thinking_config"] = types.ThinkingConfig(
                        thinking_budget=-1,
                        include_thoughts=gemini_client_config.model_settings.include_thoughts_in_response
                    )

            prompt_config = types.GenerateContentConfig(**config_kwargs)

            if debug:
                print("[image_to_video] Gemini API call configuration:")
                GeminiDebugger.print_request(contents, prompt_config, model)

            # Use async non-streaming for better performance
            response = await client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=prompt_config
            )

            if debug:
                print("[image_to_video] Gemini API response:")
                GeminiDebugger.print_response(response)

            # Extract response text
            prompt_text = GeminiResponseProcessor.extract_text_content(response)

            if prompt_text:
                # Process response using inherited method
                return GeminiVideoPromptGenerator.process_video_response(
                    prompt_text, context, session_id, debug
                )

            return None

        except Exception as e:
            from backend.config import get_llm_settings
            debug = get_llm_settings().debug
            if debug:
                print(f"[image_to_video] Gemini video prompt generation error: {str(e)}")
            raise
