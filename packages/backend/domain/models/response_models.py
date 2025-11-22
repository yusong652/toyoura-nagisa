"""
LLM Response Processing Models

Defines response processing logic and data structures for the LLM client layer.
These models are specifically designed to handle LLM output and response format conversion.
"""

from typing import Union, List, Dict, Any, Optional


class LLMResponse:
    """
    Simplified LLM response class - designed for new architecture
    
    Since tool calls are now handled internally within the LLM client, this class only needs to handle final text responses.
    Removed all outdated tool call related fields and ResponseType dependencies.
    
    This is an infrastructure layer model specifically for handling LLM client response data.
    """
    
    def __init__(
        self,
        content: Union[str, List[Dict[str, Any]]],
        keyword: Optional[str] = None,
        error: Optional[str] = None,
    ):
        """
        Initialize LLM response object
        
        Args:
            content: Response content, can be string or structured list
            keyword: Emotion keyword
            error: Error message (if any)
        """
        # Ensure content is always in list format
        if isinstance(content, str):
            if error:
                # In error cases, content might be error message string
                self.content = [{"type": "text", "text": content}]
                self.is_error = True
            else:
                self.content = [{"type": "text", "text": content}]
                self.is_error = False
        else:
            self.content = content
            self.is_error = bool(error)
        
        self.keyword = keyword
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert LLMResponse to dictionary format.
        
        Mainly used for serialization and API responses.
        
        Returns:
            Dict: Dictionary representation of response data
        """
        result = {
            "content": self.content,
            "keyword": self.keyword,
        }
        if self.is_error:
            result["error"] = self.error
        return result
    
    def get_text_content(self) -> str:
        """
        Extract pure text content
        
        Returns:
            str: Merged text content
        """
        text_parts = []
        for item in self.content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        return "".join(text_parts)
    
    def has_error(self) -> bool:
        """
        Check if contains error
        
        Returns:
            bool: Whether there's an error
        """
        return self.is_error