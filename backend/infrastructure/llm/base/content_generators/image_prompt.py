"""
Base image prompt generator for text-to-image generation.

Handles text-to-image prompt generation using conversation context and few-shot learning.
"""

from abc import abstractmethod
from typing import Optional, Dict, Any, List
from backend.domain.models.messages import BaseMessage, UserMessage, AssistantMessage
from backend.infrastructure.storage.session_manager import get_latest_n_messages
from backend.config import get_text_to_image_settings
from backend.infrastructure.llm.shared.utils.text_processing import extract_text_content, parse_text_to_image_response, enhance_prompts_with_defaults
from backend.infrastructure.llm.shared.utils.text_to_image import load_text_to_image_history, save_text_to_image_generation
from backend.infrastructure.llm.shared.constants.defaults import DEFAULT_FEW_SHOT_MAX_LENGTH, DEFAULT_CONTEXT_MESSAGE_COUNT
from backend.infrastructure.llm.shared.constants.prompts import DEFAULT_TEXT_TO_IMAGE_SYSTEM_PROMPT, CONVERSATION_TEXT_PROMPT_PREFIX
from .base import BaseContentGenerator


class BaseImagePromptGenerator(BaseContentGenerator):
    """
    Abstract base class for image prompt generation.
    
    Handles text-to-image prompt generation using LLM APIs.
    Creates detailed and effective prompts for image generation based on
    recent conversation context, with support for positive and negative prompts.
    """
    
    @staticmethod
    @abstractmethod
    def generate_text_to_image_prompt(
        client,  # LLM client instance
        session_id: Optional[str] = None,
        debug: bool = False
    ) -> Optional[Dict[str, str]]:
        """
        Generate high-quality text-to-image prompts using recent conversation context.
        
        Args:
            client: LLM client instance for API calls
            session_id: Optional session ID for conversation context
            debug: Enable debug output
            
        Returns:
            Dictionary with 'text_prompt' and 'negative_prompt' keys, or None if failed
        """
        pass
    
    @staticmethod
    def prepare_generation_context(
        session_id: Optional[str] = None,
        few_shot_max_length: int = DEFAULT_FEW_SHOT_MAX_LENGTH,
        context_message_count: int = DEFAULT_CONTEXT_MESSAGE_COUNT,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Prepare context data for image prompt generation.
        
        Args:
            session_id: Optional session ID for conversation context
            few_shot_max_length: Maximum number of few-shot examples
            context_message_count: Number of recent messages to include
            llm_provider: Optional LLM provider name
            llm_model: Optional LLM model name
            
        Returns:
            Dictionary containing prepared context data
        """
        # Load text-to-image settings
        text_to_image_settings = get_text_to_image_settings()
        
        # Get latest conversation messages
        latest_messages = get_latest_n_messages(session_id, context_message_count) if session_id else tuple([None] * context_message_count)
        print(f"[text_to_image] Loaded {len(latest_messages)} latest messages for session {session_id}")
        # Load few-shot history
        few_shot_history = load_text_to_image_history(session_id) if session_id else []
        
        # Build conversation context
        conversation_text = CONVERSATION_TEXT_PROMPT_PREFIX
        for msg in latest_messages:
            if msg is not None:
                text_content = extract_text_content(msg.content)
                conversation_text += f"{msg.role}: {text_content}\n"
        
        # Get the appropriate model for prompt generation
        if llm_provider and llm_model:
            # Use just the model name, not provider:model format
            prompt_model = llm_model
        else:
            # Fallback to default text-to-image model or None
            try:
                from backend.config import get_llm_settings
                llm_settings = get_llm_settings()
                prompt_model = llm_settings.get_current_model()
            except Exception:
                # Safe fallback if configuration is incomplete
                prompt_model = None
        
        return {
            'system_prompt': text_to_image_settings.text_to_image_system_prompt or DEFAULT_TEXT_TO_IMAGE_SYSTEM_PROMPT,
            'conversation_text': conversation_text,
            'few_shot_history': few_shot_history[-few_shot_max_length:],  # Use most recent examples
            'temperature': getattr(text_to_image_settings, 'text_to_image_temperature', 1.0),
            'model': prompt_model
        }
    
    @staticmethod
    def build_messages_for_generation(context: Dict[str, Any]) -> List[BaseMessage]:
        """
        Build message sequence for prompt generation including few-shot examples.
        
        Args:
            context: Context data from prepare_generation_context
            
        Returns:
            List of BaseMessage objects ready for API call
        """
        messages = []
        
        # Add few-shot examples as historical conversation
        for record in context['few_shot_history']:
            user_msg = UserMessage(role="user", content=record['user_message']['content'])
            messages.append(user_msg)
            
            assistant_msg = AssistantMessage(role="assistant", content=record['assistant_message']['content'])
            messages.append(assistant_msg)
        
        # Add current request
        current_request = UserMessage(role="user", content=context['conversation_text'])
        messages.append(current_request)
        
        return messages
    
    @staticmethod
    def process_generation_response(
        response_text: str,
        context: Dict[str, Any],
        session_id: Optional[str] = None,
        debug: bool = False
    ) -> Optional[Dict[str, str]]:
        """
        Process the raw generation response and extract prompts.
        
        Args:
            response_text: Raw response text from LLM
            context: Context data used for generation
            session_id: Optional session ID for saving history
            debug: Enable debug output
            
        Returns:
            Dictionary with 'text_prompt' and 'negative_prompt' keys, or None if failed
        """
        if not response_text:
            return None
        
        # Parse the response
        parsed_result = parse_text_to_image_response(
            response_text,
            debug=debug
        )
        
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
                    print(f"[text_to_image] Saved generation to history for session {session_id}")
            except Exception as e:
                if debug:
                    print(f"[text_to_image] Warning: Failed to save generation to history: {e}")
        
        return {
            "text_prompt": text_prompt,
            "negative_prompt": negative_prompt
        }