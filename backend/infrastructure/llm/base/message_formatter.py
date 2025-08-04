"""
Base message formatter - Abstract base class for message formatting.

This module provides the foundation for all provider-specific message formatters,
ensuring consistent message processing across different LLM providers.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from backend.domain.models.messages import BaseMessage


class BaseMessageFormatter(ABC):
    """
    Abstract base class for message formatters.
    
    Defines unified interface for converting aiNagisa's internal message format
    to provider-specific API formats. Each LLM provider has different requirements
    for message structure, content types, and metadata handling.
    """
    
    @staticmethod
    @abstractmethod
    def format_messages(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """
        Convert aiNagisa BaseMessage objects to provider-specific API format.
        
        Args:
            messages: List of BaseMessage objects from aiNagisa's internal format
            
        Returns:
            List[Dict[str, Any]]: Messages formatted for specific LLM provider API
        """
        pass
    
    @staticmethod
    def extract_text_from_content(content) -> str:
        """
        Extract text content from message content (shared utility).
        
        Args:
            content: Message content in various formats (str, List[dict], etc.)
            
        Returns:
            str: Extracted text content
        """
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
            return " ".join(text_parts)
        return str(content)
    
    @staticmethod
    def has_image_content(content) -> bool:
        """
        Check if message content contains images (shared utility).
        
        Args:
            content: Message content to check
            
        Returns:
            bool: True if content contains images
        """
        if isinstance(content, list):
            return any(
                isinstance(item, dict) and (
                    item.get("type") == "image" or "inline_data" in item
                )
                for item in content
            )
        return False
    
    @staticmethod
    def safe_json_serialize(data: Any, ensure_ascii: bool = False, indent: int = None) -> str:
        """
        Safely serialize data to JSON string (shared utility).
        
        Args:
            data: Data to serialize
            ensure_ascii: Whether to ensure ASCII encoding
            indent: JSON indentation level
            
        Returns:
            str: JSON string or string representation if serialization fails
        """
        if isinstance(data, str):
            return data
        
        import json
        try:
            return json.dumps(data, ensure_ascii=ensure_ascii, indent=indent)
        except (TypeError, ValueError):
            return str(data)
    
    @staticmethod
    def validate_inline_data(inline_data: Dict[str, Any]) -> bool:
        """
        Validate inline_data structure (shared utility).
        
        Args:
            inline_data: Dictionary containing mime_type and data
            
        Returns:
            bool: True if inline_data is valid and has data
        """
        if not isinstance(inline_data, dict):
            return False
        
        return (
            'data' in inline_data and 
            inline_data['data'] and 
            'mime_type' in inline_data
        )