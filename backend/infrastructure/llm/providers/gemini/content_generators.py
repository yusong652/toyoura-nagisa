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
from backend.infrastructure.llm.base.content_generators import BaseImagePromptGenerator, BaseTitleGenerator, BaseWebSearchGenerator, BaseVideoPromptGenerator
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
        max_uses: int = 5
    ) -> Dict[str, Any]:
        """
        Perform a web search using Google Search via the Gemini API.
        
        Uses Gemini's modern google_search tool with shared result processing.
        """
        try:
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
    Gemini-specific image prompt generation inheriting base functionality.
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
            # Get Gemini configuration for model info
            from backend.config import get_llm_settings
            llm_settings = get_llm_settings()
            llm_gemini_config = llm_settings.get_gemini_config()  # This has the 'model' attribute
            
            # Prepare generation context using inherited method with provider info
            context = GeminiImagePromptGenerator.prepare_generation_context(
                session_id=session_id,
                llm_provider="gemini",
                llm_model=llm_gemini_config.model
            )
            
            # Note: Context preparation already handles empty conversation validation
            
            # Read Gemini client configuration for detailed settings
            gemini_client_config = get_gemini_client_config()
            
            # Create API call configuration
            config_kwargs = {
                "system_instruction": context['system_prompt'],
                "safety_settings": gemini_client_config.safety_settings.to_gemini_format(),
                "temperature": context['temperature'],
                "max_output_tokens": gemini_client_config.model_settings.max_output_tokens
            }
            
            # Use the model from context (which now correctly uses Gemini's model)
            model_for_text_to_image = context.get('model', llm_gemini_config.model)
            
            # Add thinking configuration if applicable
            if (model_for_text_to_image.startswith("gemini-2.5") and 
                gemini_client_config.model_settings.enable_thinking_for_gemini_2_5):
                config_kwargs["thinking_config"] = types.ThinkingConfig(
                    include_thoughts=gemini_client_config.model_settings.include_thoughts_in_response
                )
            
            prompt_config = types.GenerateContentConfig(**config_kwargs)
            
            # Build messages using inherited method
            messages = GeminiImagePromptGenerator.build_messages_for_generation(context)
            
            # Format messages using Gemini formatter
            contents = GeminiMessageFormatter.format_messages(messages)
            
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
                # Process response using inherited method
                return GeminiImagePromptGenerator.process_generation_response(
                    prompt_text, context, session_id, debug
                )
            
            return None
            
        except Exception as e:
            if debug:
                print(f"[text_to_image] Error during prompt generation: {str(e)}")
            return None


class GeminiVideoPromptGenerator(BaseVideoPromptGenerator):
    """
    Gemini-specific video prompt generation from static image prompts.
    """
    
    @staticmethod
    async def generate_video_prompt(
        client,  # Gemini client instance
        original_prompt: str,
        image_base64: Optional[str] = None,
        motion_type: str = "cinematic",
        few_shot_history: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Dict[str, str]]:
        """
        Generate optimized video prompt using Gemini's native API with few-shot learning.
        
        Args:
            client: Gemini client instance
            original_prompt: Original static image generation prompt
            image_base64: Optional base64 encoded image for visual context
            motion_type: Type of motion for the video
            few_shot_history: Optional few-shot examples for better generation
            
        Returns:
            Dict with 'video_prompt' and 'negative_prompt' keys, or None if failed
        """
        try:
            print(f"[video_prompt] Starting Gemini video prompt generation")
            print(f"[video_prompt] Original prompt length: {len(original_prompt)}")
            print(f"[video_prompt] Motion type: {motion_type}")
            print(f"[video_prompt] Has image: {bool(image_base64)}")
            print(f"[video_prompt] Few-shot history count: {len(few_shot_history) if few_shot_history else 0}")
            
            from backend.config import get_llm_settings, get_image_to_video_settings
            llm_settings = get_llm_settings()
            gemini_config = llm_settings.get_gemini_config()
            video_settings = get_image_to_video_settings()
            
            # Read Gemini client configuration
            gemini_client_config = get_gemini_client_config()
            
            # Use video prompt system or fallback to default
            system_prompt = getattr(video_settings, 'video_prompt_system', DEFAULT_VIDEO_PROMPT_SYSTEM_PROMPT)
            
            # Configure generation parameters
            config_kwargs = {
                "system_instruction": system_prompt,
                "temperature": getattr(video_settings, 'video_prompt_temperature', 1.2),
                "max_output_tokens": gemini_client_config.model_settings.max_output_tokens
            }
            
            # Add thinking configuration if applicable
            model = gemini_config.model
            if (model.startswith("gemini-2.5") and 
                gemini_client_config.model_settings.enable_thinking_for_gemini_2_5):
                config_kwargs["thinking_config"] = types.ThinkingConfig(
                    include_thoughts=gemini_client_config.model_settings.include_thoughts_in_response
                )
            
            prompt_config = types.GenerateContentConfig(**config_kwargs)
            
            print(f"[video_prompt] Using model: {model}")
            print(f"[video_prompt] Temperature: {config_kwargs['temperature']}")
            print(f"[video_prompt] Max output tokens: {config_kwargs['max_output_tokens']}")
            
            # Build request message with motion type context
            user_message = BaseVideoPromptGenerator.create_video_prompt_request(original_prompt, motion_type)
            print(f"[video_prompt] Built user message length: {len(user_message)}")
            
            # Create contents list
            contents = []
            
            # Add few-shot examples if available
            if few_shot_history:
                print(f"[video_prompt] Adding {len(few_shot_history)} few-shot examples")
                for i, example in enumerate(few_shot_history):
                    print(f"[video_prompt] Adding few-shot example {i+1}")
                    # Add user example (from user_message.content)
                    user_msg = example.get('user_message', {})
                    user_content = user_msg.get('content', '')
                    contents.append({
                        "role": "user",
                        "parts": [{"text": user_content}]
                    })
                    
                    # Add assistant example (from assistant_message.content)
                    assistant_msg = example.get('assistant_message', {})
                    assistant_content = assistant_msg.get('content', '')
                    contents.append({
                        "role": "model",
                        "parts": [{"text": assistant_content}]
                    })
            else:
                print(f"[video_prompt] No few-shot examples available")
            
            # Add current request
            if image_base64:
                print(f"[video_prompt] Adding current request with image")
                contents.append({
                    "role": "user",
                    "parts": [
                        {"text": user_message},
                        {"inline_data": {"mime_type": "image/jpeg", "data": image_base64}}
                    ]
                })
            else:
                print(f"[video_prompt] Adding current request without image")
                contents.append({
                    "role": "user", 
                    "parts": [{"text": user_message}]
                })
            
            print(f"[video_prompt] Total content parts: {len(contents)}")
            print(f"[video_prompt] ===== PAYLOAD DEBUG =====")
            print(f"[video_prompt] Model: {model}")
            print(f"[video_prompt] Config: {prompt_config}")
            print(f"[video_prompt] Contents:")
            for i, content in enumerate(contents):
                print(f"[video_prompt]   [{i}] Role: {content.get('role')}")
                parts = content.get('parts', [])
                for j, part in enumerate(parts):
                    if 'text' in part:
                        text_preview = part['text'][:200] + "..." if len(part['text']) > 200 else part['text']
                        print(f"[video_prompt]     Part[{j}] Text: {text_preview}")
                    elif 'inline_data' in part:
                        print(f"[video_prompt]     Part[{j}] Image: {part['inline_data']['mime_type']}")
            print(f"[video_prompt] ===== END PAYLOAD =====")
            print(f"[video_prompt] Calling Gemini API...")
            
            # Call Gemini API
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=prompt_config
            )
            
            print(f"[video_prompt] Received response from Gemini API")
            print(f"[video_prompt] ===== RESPONSE DEBUG =====")
            print(f"[video_prompt] Response type: {type(response)}")
            print(f"[video_prompt] Response dir: {dir(response)}")
            if hasattr(response, 'candidates'):
                print(f"[video_prompt] Candidates count: {len(response.candidates) if response.candidates else 0}")
                if response.candidates:
                    for i, candidate in enumerate(response.candidates):
                        print(f"[video_prompt]   Candidate[{i}]: {type(candidate)}")
                        if hasattr(candidate, 'content'):
                            print(f"[video_prompt]     Content: {candidate.content}")
                        if hasattr(candidate, 'finish_reason'):
                            print(f"[video_prompt]     Finish reason: {candidate.finish_reason}")
            print(f"[video_prompt] ===== END RESPONSE =====")
            
            # Extract response text
            response_text = GeminiResponseProcessor.extract_text_content(response)
            print(f"[video_prompt] Response text length: {len(response_text) if response_text else 0}")
            if response_text:
                print(f"[video_prompt] Response text preview: {response_text[:300]}...")
            
            if response_text:
                print(f"[video_prompt] Parsing response text...")
                # Parse and return the response
                parsed_result = BaseVideoPromptGenerator.parse_video_prompt_response(
                    response_text, original_prompt
                )
                if parsed_result:
                    print(f"[video_prompt] Successfully parsed video prompt")
                    print(f"[video_prompt] Video prompt length: {len(parsed_result.get('video_prompt', ''))}")
                    print(f"[video_prompt] Negative prompt length: {len(parsed_result.get('negative_prompt', ''))}")
                else:
                    print(f"[video_prompt] Failed to parse response")
                return parsed_result
            else:
                print(f"[video_prompt] No response text received")
            
            return None
            
        except Exception as e:
            print(f"[video_prompt] Error during Gemini video prompt generation: {str(e)}")
            return None