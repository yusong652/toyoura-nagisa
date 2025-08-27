"""
Base content generators - Abstract base classes for specialized content generation.

This module provides the foundation for all provider-specific content generators,
extracting common patterns and providing shared interfaces.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from backend.domain.models.messages import BaseMessage, UserMessage, AssistantMessage
from backend.infrastructure.storage.session_manager import get_latest_n_messages
from backend.config import get_text_to_image_settings
from backend.infrastructure.llm.shared.utils.text_processing import extract_text_content, parse_text_to_image_response, enhance_prompts_with_defaults
from backend.infrastructure.llm.shared.utils.text_to_image import load_text_to_image_history, save_text_to_image_generation
from backend.infrastructure.llm.shared.constants.defaults import DEFAULT_FEW_SHOT_MAX_LENGTH, DEFAULT_CONTEXT_MESSAGE_COUNT
from backend.infrastructure.llm.shared.constants.prompts import DEFAULT_TEXT_TO_IMAGE_SYSTEM_PROMPT, CONVERSATION_TEXT_PROMPT_PREFIX, DEFAULT_VIDEO_PROMPT_SYSTEM_PROMPT


class BaseContentGenerator(ABC):
    """
    Abstract base class for content generators.
    
    Provides common interface for specialized content generation utilities
    like title generation, image prompt generation, and web search.
    """
    
    def __init__(self, client, config=None):
        """
        Initialize content generator.
        
        Args:
            client: LLM client instance
            config: Optional configuration object
        """
        self.client = client
        self.config = config


class BaseTitleGenerator(BaseContentGenerator):
    """
    Abstract base class for title generation.
    
    Handles conversation title generation using LLM APIs.
    Generates concise, descriptive titles based on the first exchange
    in a conversation to help users identify and organize their chats.
    """
    
    @staticmethod
    @abstractmethod
    def generate_title_from_messages(
        client,  # LLM client instance
        latest_messages: List[BaseMessage]
    ) -> Optional[str]:
        """
        Generate a concise conversation title based on recent messages.
        
        Args:
            client: LLM client instance for API calls
            latest_messages: Recent conversation messages to generate title from
            
        Returns:
            Generated title string, or None if generation fails
        """
        pass
    
    @staticmethod
    def validate_messages_for_title(latest_messages: List[BaseMessage]) -> bool:
        """
        Validate if messages are sufficient for title generation.
        
        Args:
            latest_messages: Messages to validate
            
        Returns:
            True if messages are valid for title generation
        """
        return latest_messages and len(latest_messages) >= 2
    
    @staticmethod
    def prepare_title_generation_messages(
        latest_messages: List[BaseMessage], 
        title_request_text: str
    ) -> List[BaseMessage]:
        """
        Prepare message sequence for title generation.
        
        Args:
            latest_messages: Original conversation messages
            title_request_text: Text prompt requesting title generation
            
        Returns:
            Complete message list including title request
        """
        from backend.infrastructure.llm.shared.constants.prompts import TITLE_GENERATION_REQUEST_TEXT
        
        return list(latest_messages) + [
            UserMessage(role="user", content=[{"type": "text", "text": title_request_text or TITLE_GENERATION_REQUEST_TEXT}])
        ]


class BaseWebSearchGenerator(BaseContentGenerator):
    """
    Abstract base class for web search generation.
    
    Handles web search using LLM APIs with appropriate search tools.
    Performs web searches and returns structured results with proper error
    handling and debugging support.
    """
    
    @staticmethod
    @abstractmethod
    def perform_web_search(
        client,  # LLM client instance
        query: str,
        debug: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Perform a web search using the LLM's web search capabilities.
        
        Args:
            client: LLM client instance for API calls
            query: The search query to find information on the web
            debug: Enable debug output
            **kwargs: Additional search parameters (max_uses, etc.)
            
        Returns:
            Dictionary containing search results or error information
        """
        pass
    
    @staticmethod
    def create_search_user_message(query: str) -> UserMessage:
        """
        Create a user message for web search query.
        
        Args:
            query: The search query
            
        Returns:
            UserMessage object containing the query
        """
        return UserMessage(role="user", content=query)
    
    @staticmethod
    def format_search_result(
        query: str,
        response_text: str,
        sources: List[Dict[str, Any]],
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Format web search results into standardized structure.
        
        Args:
            query: Original search query
            response_text: Synthesized response text
            sources: List of source dictionaries
            error: Optional error message
            
        Returns:
            Standardized search result dictionary
        """
        return {
            "query": query,
            "response_text": response_text,
            "sources": sources,
            "total_sources": len(sources),
            "error": error
        }
    
    @staticmethod
    def format_search_error(query: str, error_message: str) -> Dict[str, Any]:
        """
        Format search error into standardized response.
        
        Args:
            query: Original search query
            error_message: Error description
            
        Returns:
            Standardized error response
        """
        return BaseWebSearchGenerator.format_search_result(
            query=query,
            response_text="",
            sources=[],
            error=error_message
        )
    
    @staticmethod
    def debug_search_start(query: str, debug: bool):
        """
        Print debug message for search start.
        
        Args:
            query: Search query
            debug: Whether debug is enabled
        """
        if debug:
            print(f"[WebSearch] Performing search for query: {query}")
    
    @staticmethod
    def debug_search_complete(debug: bool):
        """
        Print debug message for search completion.
        
        Args:
            debug: Whether debug is enabled
        """
        if debug:
            print(f"[WebSearch] API call completed")
    
    @staticmethod
    def debug_search_results(sources_count: int, response_length: int, debug: bool):
        """
        Print debug message for search results.
        
        Args:
            sources_count: Number of sources found
            response_length: Length of response text
            debug: Whether debug is enabled
        """
        if debug:
            print(f"[WebSearch] Extracted {sources_count} sources")
            print(f"[WebSearch] Response text length: {response_length}")


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


class BaseVideoPromptGenerator(BaseContentGenerator):
    """
    Abstract base class for video prompt generation from static image prompts.
    
    Transforms static image descriptions into dynamic video prompts with motion,
    camera movements, and temporal changes for AI video generation models.
    """
    
    @staticmethod
    @abstractmethod
    async def generate_video_prompt(
        client,  # LLM client instance (provider-specific)
        original_prompt: str,
        image_base64: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        """
        Generate optimized video prompt from static image prompt.
        
        Args:
            client: Provider-specific LLM client instance
            original_prompt: Original static image generation prompt
            image_base64: Optional base64 encoded image for visual context
            
        Returns:
            Dict with 'video_prompt' and 'negative_prompt' keys, or None if failed
        """
        pass
    
    @staticmethod
    def create_video_prompt_request(original_prompt: str, motion_type: str = "cinematic") -> str:
        """
        Create the user message for video prompt generation.
        
        Args:
            original_prompt: Original static image prompt
            motion_type: Type of motion for the video
            
        Returns:
            Formatted request message
        """
        motion_descriptions = {
            "gentle": "subtle, gentle movements like gentle breeze, slow motion, peaceful transitions",
            "dynamic": "energetic, dynamic motion with action sequences and fast movements", 
            "cinematic": "cinematic camera movements, smooth panning, professional film-like motion",
            "loop": "seamless looping motion with cyclic, repeating patterns"
        }
        
        motion_desc = motion_descriptions.get(motion_type, motion_descriptions["cinematic"])
        
        return f"""Transform this static image prompt into a dynamic video prompt:

Original prompt: {original_prompt}
Motion type: {motion_type} ({motion_desc})

Add motion descriptions, camera movements, and temporal changes that match the {motion_type} style.
Keep the core subject and artistic style, but make it dynamic with {motion_desc}.
Output format:
<video_prompt>your enhanced video prompt here</video_prompt>
<negative_prompt>negative prompt for video generation here</negative_prompt>"""
    
    @staticmethod
    def parse_video_prompt_response(response_text: str, original_prompt: str) -> Dict[str, str]:
        """
        Parse the LLM response to extract video and negative prompts using XML tags.
        
        Args:
            response_text: Raw LLM response text
            original_prompt: Original prompt as fallback
            
        Returns:
            Dict with 'video_prompt' and 'negative_prompt'
        """
        import re
        from backend.config import get_image_to_video_settings
        from backend.infrastructure.llm.shared.constants.prompts import VIDEO_PROMPT_PATTERN, NEGATIVE_PROMPT_PATTERN
        
        settings = get_image_to_video_settings()
        
        # Try to extract using XML tags first
        video_match = re.search(VIDEO_PROMPT_PATTERN, response_text, re.DOTALL)
        negative_match = re.search(NEGATIVE_PROMPT_PATTERN, response_text, re.DOTALL)
        
        if video_match:
            video_prompt = video_match.group(1).strip()
        else:
            # Fallback to old format for backward compatibility
            video_prompt = original_prompt
            for line in response_text.split("\n"):
                if line.startswith("VIDEO_PROMPT:"):
                    video_prompt = line.replace("VIDEO_PROMPT:", "").strip()
                    break
        
        if negative_match:
            negative_prompt = negative_match.group(1).strip()
        else:
            # Fallback to old format for backward compatibility
            negative_prompt = settings.default_motion_negative
            for line in response_text.split("\n"):
                if line.startswith("NEGATIVE_PROMPT:"):
                    negative_prompt = line.replace("NEGATIVE_PROMPT:", "").strip()
                    break
        
        # Add default motion keywords
        video_prompt = f"{video_prompt}, {settings.default_motion_positive}"
        
        return {
            "video_prompt": video_prompt,
            "negative_prompt": negative_prompt
        }