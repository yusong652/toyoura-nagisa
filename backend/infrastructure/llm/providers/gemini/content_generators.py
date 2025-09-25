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
from backend.infrastructure.llm.base.content_generators.unified import BaseUnifiedPromptGenerator, PromptType
from backend.infrastructure.llm.shared.utils.text_processing import parse_title_response
from backend.infrastructure.llm.shared.constants.defaults import (
    DEFAULT_TITLE_MAX_LENGTH,
    DEFAULT_TITLE_GENERATION_TEMPERATURE,
    DEFAULT_WEB_SEARCH_TEMPERATURE)
from backend.infrastructure.llm.shared.constants.prompts import (
    DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT,
    TITLE_GENERATION_REQUEST_TEXT,
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
        latest_messages: List[BaseMessage]
    ) -> Optional[str]:
        """
        Generate a concise conversation title based on recent messages.
        
        Uses Gemini API with shared processing logic.
        """
        try:
            # Use base class validation
            if not BaseTitleGenerator.validate_messages_for_title(latest_messages):
                return None
            
            # Read Gemini configuration
            gemini_config = get_gemini_client_config()
            
            system_prompt = DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT
            
            # Configure title generation parameters
            title_config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=DEFAULT_TITLE_GENERATION_TEMPERATURE,
                max_output_tokens=gemini_config.model_settings.max_output_tokens
            )
            
            # Build message sequence using base class method
            messages = BaseTitleGenerator.prepare_title_generation_messages(
                latest_messages, TITLE_GENERATION_REQUEST_TEXT
            )
            
            # Use MessageFormatter for unified message format conversion
            contents = GeminiMessageFormatter.format_messages(messages)
            
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
            
            if debug:
                GeminiDebugger.print_debug_request(contents, search_config)
                print(f"[WebSearch] Note: max_uses={max_uses} parameter ignored for Gemini (API limitation)")
            
            # Get model from configuration
            llm_settings = get_llm_settings()
            gemini_config = llm_settings.get_gemini_config()
            model = gemini_config.model
            
            # Call the model with the query (async version)
            response = await client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=search_config
            )
            
            # Use base class debug method
            BaseWebSearchGenerator.debug_search_complete(debug)
            if debug:
                GeminiDebugger.print_debug_response(response)
            
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
    Gemini-specific image prompt generation delegating to unified generator.
    
    Maintains backward compatibility while using the new unified approach.
    """
    
    @staticmethod
    async def generate_text_to_image_prompt(
        client,  # Gemini client instance
        session_id: Optional[str] = None,
        debug: bool = False
    ) -> Optional[Dict[str, str]]:
        """
        Generate high-quality text-to-image prompts using unified generator.
        
        This method now delegates to the unified prompt generator for consistency
        and reduced code duplication.
        """
        return await GeminiUnifiedPromptGenerator.generate_prompt(
            client=client,
            prompt_type=PromptType.TEXT_TO_IMAGE,
            session_id=session_id,
            debug=debug
        )


class GeminiVideoPromptGenerator(BaseVideoPromptGenerator):
    """
    Gemini-specific video prompt generation delegating to unified generator.
    
    Maintains backward compatibility while using the new unified approach.
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
        Generate optimized video prompt using unified generator.
        
        This method now delegates to the unified prompt generator, which handles
        conversation context and few-shot learning directly.
        
        Args:
            client: Gemini client instance
            original_prompt: Original static image generation prompt (not used directly)
            image_base64: Optional base64 encoded image (not sent to LLM)
            motion_type: Type of motion for the video (converted to motion_style)
            few_shot_history: Optional few-shot examples (handled by unified generator)
            session_id: Session ID for context and history
            
        Returns:
            Dict with 'video_prompt' and 'negative_prompt' keys, or None if failed
        """
        # Convert motion_type to motion_style description
        motion_descriptions = {
            "gentle": "subtle, gentle movements like gentle breeze, slow motion, peaceful transitions",
            "dynamic": "energetic, dynamic motion with action sequences and fast movements", 
            "cinematic": "cinematic camera movements, smooth panning, professional film-like motion",
            "loop": "seamless looping motion with cyclic, repeating patterns"
        }
        motion_style = motion_descriptions.get(motion_type, motion_descriptions["cinematic"])
        
        # Delegate to unified generator
        # Note: image_base64 is not passed since it shouldn't be sent to LLM
        # few_shot_history is also not passed as it's loaded automatically by session_id
        return await GeminiUnifiedPromptGenerator.generate_prompt(
            client=client,
            prompt_type=PromptType.IMAGE_TO_VIDEO,
            session_id=session_id,
            motion_style=motion_style,
            debug=True  # Keep debug enabled for video prompts
        )


class GeminiUnifiedPromptGenerator(BaseUnifiedPromptGenerator):
    """
    Gemini-specific unified prompt generator for both text-to-image and image-to-video.
    
    Provides a single interface that handles both prompt types using conversation
    context and few-shot learning, reducing code duplication and improving consistency.
    """
    
    @staticmethod
    async def generate_prompt(
        client,  # Gemini client instance
        prompt_type: PromptType,
        session_id: Optional[str] = None,
        motion_style: Optional[str] = None,
        image_base64: Optional[str] = None,
        debug: bool = False
    ) -> Optional[Dict[str, str]]:
        """
        Generate high-quality prompts using unified approach with Gemini API.
        
        Args:
            client: Gemini client instance
            prompt_type: Type of prompt to generate (text_to_image or image_to_video)
            session_id: Optional session ID for conversation context and few-shot learning
            motion_style: Optional motion style description (for video prompts)
            image_base64: Optional base64 image (for image-to-video)
            debug: Enable debug output
            
        Returns:
            Dictionary with appropriate prompt keys based on type
        """
        try:
            # Get Gemini configuration
            from backend.config import get_llm_settings
            llm_settings = get_llm_settings()
            llm_gemini_config = llm_settings.get_gemini_config()
            
            # Read Gemini client configuration
            gemini_client_config = get_gemini_client_config()
            
            # Prepare unified context with provider info
            context = GeminiUnifiedPromptGenerator.prepare_unified_context(
                prompt_type=prompt_type,
                session_id=session_id,
                motion_style=motion_style,
                llm_provider="gemini",
                llm_model=llm_gemini_config.model
            )
            
            # Create API call configuration
            config_kwargs = {
                "system_instruction": context['system_prompt'],
                "safety_settings": gemini_client_config.safety_settings.to_gemini_format(),
                "temperature": context['temperature'],
                "max_output_tokens": gemini_client_config.model_settings.max_output_tokens
            }
            
            # Use the model from context
            model = context.get('model', llm_gemini_config.model)
            
            # Add thinking configuration if applicable
            if (model.startswith("gemini-2.5") and 
                gemini_client_config.model_settings.enable_thinking_for_gemini_2_5):
                config_kwargs["thinking_config"] = types.ThinkingConfig(
                    include_thoughts=gemini_client_config.model_settings.include_thoughts_in_response
                )
            
            prompt_config = types.GenerateContentConfig(**config_kwargs)
            
            # Build messages using unified method
            messages = GeminiUnifiedPromptGenerator.build_unified_messages(context)
            
            # Format messages using Gemini formatter
            contents = GeminiMessageFormatter.format_messages(messages)
            
            # Note: We do NOT send the image to the LLM for prompt generation
            # The image is only sent to the video generation server
            # The LLM only needs the conversation context to generate appropriate prompts
            
            if debug:
                print(f"[{prompt_type.value}] Formatted contents for Gemini:")
                GeminiDebugger.print_debug_request(contents, prompt_config)
            
            # Make API call
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=prompt_config
            )
            
            if debug:
                print(f"[{prompt_type.value}] Response received:")
                GeminiDebugger.print_debug_response(response)
            
            # Extract response text
            prompt_text = GeminiResponseProcessor.extract_text_content(response)
            
            if prompt_text:
                # Process response using unified method
                return GeminiUnifiedPromptGenerator.process_unified_response(
                    prompt_text, context, session_id, debug
                )
            
            return None
            
        except Exception as e:
            if debug:
                print(f"[{prompt_type.value}] Error during unified prompt generation: {str(e)}")
            # Propagate exception so service layer can return detailed error to frontend
            raise
