"""
Unified prompt generator supporting multiple generation types.

Provides a single interface for generating both text-to-image and 
image-to-video prompts using conversation context and few-shot learning.
"""

from abc import abstractmethod
from enum import Enum
from typing import Optional, Dict, Any, List
from backend.domain.models.messages import BaseMessage, UserMessage, AssistantMessage
from backend.infrastructure.storage.session_manager import get_latest_n_messages
from backend.infrastructure.llm.shared.utils.text_processing import extract_text_content, parse_text_to_image_response, enhance_prompts_with_defaults
from backend.infrastructure.llm.shared.utils.text_to_image import load_text_to_image_history, save_text_to_image_generation
from backend.infrastructure.llm.shared.utils.image_to_video import load_video_prompt_history, save_video_prompt_generation
from backend.infrastructure.llm.shared.constants.defaults import DEFAULT_FEW_SHOT_MAX_LENGTH, DEFAULT_CONTEXT_MESSAGE_COUNT
from backend.infrastructure.llm.shared.constants.prompts import DEFAULT_TEXT_TO_IMAGE_SYSTEM_PROMPT, CONVERSATION_TEXT_PROMPT_PREFIX, CONVERSATION_VIDEO_PROMPT_PREFIX, DEFAULT_VIDEO_PROMPT_SYSTEM_PROMPT
from .base import BaseContentGenerator
from .video_prompt import BaseVideoPromptGenerator


class PromptType(Enum):
    """
    Enumeration of supported prompt generation types.
    
    Defines the different types of prompts that can be generated,
    allowing unified handling of various generation scenarios.
    """
    TEXT_TO_IMAGE = "text_to_image"
    IMAGE_TO_VIDEO = "image_to_video"
    # Future extensibility for other types
    # TEXT_TO_VIDEO = "text_to_video"
    # IMAGE_EDIT = "image_edit"


class BaseUnifiedPromptGenerator(BaseContentGenerator):
    """
    Unified prompt generator supporting multiple generation types.
    
    Provides a single interface for generating both text-to-image and 
    image-to-video prompts, using conversation context and few-shot learning.
    This approach ensures consistency and reduces code duplication.
    """
    
    @staticmethod
    @abstractmethod
    async def generate_prompt(
        client,  # LLM client instance
        prompt_type: PromptType,
        session_id: Optional[str] = None,
        motion_style: Optional[str] = None,
        image_base64: Optional[str] = None,
        debug: bool = False
    ) -> Optional[Dict[str, str]]:
        """
        Generate high-quality prompts based on type and conversation context.
        
        Args:
            client: LLM client instance for API calls
            prompt_type: Type of prompt to generate (text_to_image or image_to_video)
            session_id: Optional session ID for conversation context and few-shot learning
            motion_style: Optional motion style (for video prompts)
            image_base64: Optional base64 image (for image-to-video)
            debug: Enable debug output
            
        Returns:
            Dictionary with prompt keys based on type:
            - text_to_image: {'text_prompt', 'negative_prompt'}
            - image_to_video: {'video_prompt', 'negative_prompt'}
            Or None if generation fails
        """
        pass
    
    @staticmethod
    def prepare_unified_context(
        prompt_type: PromptType,
        session_id: Optional[str] = None,
        motion_style: Optional[str] = None,
        few_shot_max_length: int = DEFAULT_FEW_SHOT_MAX_LENGTH,
        context_message_count: int = DEFAULT_CONTEXT_MESSAGE_COUNT,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Prepare unified context data for any prompt generation type.
        
        Args:
            prompt_type: Type of prompt being generated
            session_id: Optional session ID for conversation context
            motion_style: Optional motion style for video prompts
            few_shot_max_length: Maximum number of few-shot examples (uses config if available, else default)
            context_message_count: Number of recent messages to include (uses config if available, else default)
            llm_provider: Optional LLM provider name
            llm_model: Optional LLM model name
            
        Returns:
            Dictionary containing prepared context data with keys:
            - system_prompt: System instruction for the LLM
            - conversation_text: Formatted conversation context
            - few_shot_history: Historical examples for few-shot learning
            - temperature: Generation temperature
            - model: Model to use for generation
            - prompt_type: The prompt type being generated
            - motion_style: Motion style (for video)
        """
        # Get appropriate settings based on type and override parameters with config values
        if prompt_type == PromptType.TEXT_TO_IMAGE:
            from backend.config import get_text_to_image_settings
            settings = get_text_to_image_settings()
            system_prompt = settings.text_to_image_system_prompt or DEFAULT_TEXT_TO_IMAGE_SYSTEM_PROMPT
            temperature = getattr(settings, 'text_to_image_temperature', 1.0)
            
            # Actively get config values, fallback to function parameter defaults
            actual_few_shot_max_length = getattr(settings, 'few_shot_max_length', few_shot_max_length)
            actual_context_message_count = getattr(settings, 'context_message_count', context_message_count)
            
            # Load text-to-image few-shot history
            few_shot_history = load_text_to_image_history(session_id) if session_id else []
            
        elif prompt_type == PromptType.IMAGE_TO_VIDEO:
            from backend.config import get_image_to_video_settings
            settings = get_image_to_video_settings()
            system_prompt = getattr(settings, 'video_prompt_system', DEFAULT_VIDEO_PROMPT_SYSTEM_PROMPT)
            temperature = getattr(settings, 'video_prompt_temperature', 1.2)
            
            # Actively get config values with fallback to function parameter defaults
            actual_few_shot_max_length = getattr(settings, 'few_shot_max_length', few_shot_max_length)
            actual_context_message_count = getattr(settings, 'context_message_count', context_message_count)
            
            # Load video prompt few-shot history
            few_shot_history = load_video_prompt_history(session_id) if session_id else []
            
        else:
            raise ValueError(f"Unsupported prompt type: {prompt_type}")
        
        # Get latest conversation messages using actual config values
        latest_messages = get_latest_n_messages(session_id, actual_context_message_count) if session_id else tuple([None] * actual_context_message_count)
        
        # Build conversation context with appropriate prefix
        if prompt_type == PromptType.TEXT_TO_IMAGE:
            conversation_text = CONVERSATION_TEXT_PROMPT_PREFIX
        elif prompt_type == PromptType.IMAGE_TO_VIDEO:
            conversation_text = CONVERSATION_VIDEO_PROMPT_PREFIX
        else:
            # Fallback to text-to-image prefix
            conversation_text = CONVERSATION_TEXT_PROMPT_PREFIX
            
        for msg in latest_messages:
            if msg is not None:
                text_content = extract_text_content(msg.content)
                conversation_text += f"{msg.role}: {text_content}\n"
        
        # Add motion style to conversation context for video prompts
        if prompt_type == PromptType.IMAGE_TO_VIDEO and motion_style:
            conversation_text += f"\n[Motion Style Requested: {motion_style}]"
        
        # Get the appropriate model for prompt generation
        if llm_provider and llm_model:
            prompt_model = llm_model
        else:
            try:
                from backend.config import get_llm_settings
                llm_settings = get_llm_settings()
                prompt_model = llm_settings.get_current_model()
            except Exception:
                prompt_model = None
        
        return {
            'system_prompt': system_prompt,
            'conversation_text': conversation_text,
            'few_shot_history': few_shot_history[-actual_few_shot_max_length:] if actual_few_shot_max_length > 0 else [],
            'temperature': temperature,
            'model': prompt_model,
            'prompt_type': prompt_type,
            'motion_style': motion_style
        }
    
    @staticmethod
    def build_unified_messages(context: Dict[str, Any]) -> List[BaseMessage]:
        """
        Build message sequence for unified prompt generation.
        
        Args:
            context: Context data from prepare_unified_context
            
        Returns:
            List of BaseMessage objects ready for API call
        """
        messages = []
        prompt_type = context['prompt_type']
        
        # Add few-shot examples based on type
        for record in context['few_shot_history']:
            # Extract content based on history format
            if prompt_type == PromptType.TEXT_TO_IMAGE:
                # Text-to-image uses 'content' field directly
                user_content = record['user_message']['content']
                assistant_content = record['assistant_message']['content']
            else:
                # Image-to-video uses same format now
                user_content = record['user_message']['content']
                assistant_content = record['assistant_message']['content']
            
            user_msg = UserMessage(role="user", content=user_content)
            messages.append(user_msg)
            
            assistant_msg = AssistantMessage(role="assistant", content=assistant_content)
            messages.append(assistant_msg)
        
        # Add current request
        current_request = UserMessage(role="user", content=context['conversation_text'])
        messages.append(current_request)
        
        return messages
    
    @staticmethod
    def process_unified_response(
        response_text: str,
        context: Dict[str, Any],
        session_id: Optional[str] = None,
        debug: bool = False
    ) -> Optional[Dict[str, str]]:
        """
        Process the raw generation response based on prompt type.
        
        Args:
            response_text: Raw response text from LLM
            context: Context data used for generation
            session_id: Optional session ID for saving history
            debug: Enable debug output
            
        Returns:
            Dictionary with appropriate keys based on prompt type
        """
        if not response_text:
            return None
        
        prompt_type = context['prompt_type']
        
        if prompt_type == PromptType.TEXT_TO_IMAGE:
            # Parse text-to-image response
            parsed_result = parse_text_to_image_response(response_text, debug=debug)
            
            if parsed_result is None:
                return None
            
            text_prompt, negative_prompt = parsed_result
            
            # Enhance prompts with defaults
            text_prompt, negative_prompt = enhance_prompts_with_defaults(
                text_prompt=text_prompt,
                negative_prompt=negative_prompt,
                debug=debug
            )
            
            # Save to history for future few-shot learning
            if session_id:
                try:
                    save_text_to_image_generation(
                        session_id, 
                        context['conversation_text'], 
                        response_text
                    )
                    if debug:
                        print(f"[{prompt_type.value}] Saved generation to history for session {session_id}")
                except Exception as e:
                    if debug:
                        print(f"[{prompt_type.value}] Warning: Failed to save generation to history: {e}")
            
            return {
                "text_prompt": text_prompt,
                "negative_prompt": negative_prompt
            }
            
        elif prompt_type == PromptType.IMAGE_TO_VIDEO:
            # Parse video prompt response using BaseVideoPromptGenerator method
            parsed_result = BaseVideoPromptGenerator.parse_video_prompt_response(
                response_text, 
                context['conversation_text']  # Use conversation as fallback
            )
            
            if not parsed_result:
                return None
            
            # Save to history for future few-shot learning
            if session_id:
                try:
                    # Save with the conversation text as the request
                    save_video_prompt_generation(
                        session_id=session_id,
                        user_request=context['conversation_text'],
                        assistant_response=response_text
                    )
                    if debug:
                        print(f"[{prompt_type.value}] Saved generation to history for session {session_id}")
                except Exception as e:
                    if debug:
                        print(f"[{prompt_type.value}] Warning: Failed to save generation to history: {e}")
            
            return parsed_result
        
        else:
            if debug:
                print(f"Unsupported prompt type: {prompt_type}")
            return None