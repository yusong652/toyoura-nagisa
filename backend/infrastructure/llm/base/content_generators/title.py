"""
Base title generator for conversation title generation.

Handles conversation title generation using LLM APIs.
"""

from abc import abstractmethod
from typing import Optional, List, Union, Awaitable
from backend.domain.models.messages import BaseMessage, UserMessage
from .base import BaseContentGenerator


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
        *args, **kwargs
    ) -> Union[Optional[str], Awaitable[Optional[str]]]:
        """
        Generate a concise conversation title based on recent messages.

        This method signature allows for provider-specific implementations
        with different parameter requirements (client, debug flags, etc.)
        and supports both sync and async implementations.

        Common Args:
            latest_messages: Recent conversation messages to generate title from
            client (optional): LLM client instance for API calls
            debug (optional): Enable debug output

        Returns:
            Generated title string, None if generation fails, or awaitable for async implementations
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
        return bool(latest_messages) and len(latest_messages) >= 2
    
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