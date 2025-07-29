"""
Gemini-specific message formatter.

Handles conversion from aiNagisa's internal message format to Gemini API format.
"""

from typing import List, Dict, Any
from backend.domain.models.messages import BaseMessage
from backend.infrastructure.llm.base.message_formatter import BaseMessageFormatter


class GeminiMessageFormatter(BaseMessageFormatter):
    """
    Gemini-specific message formatter.
    
    Converts aiNagisa BaseMessage objects to Gemini API format with proper
    handling of multimodal content, roles, and metadata.
    """
    
    @staticmethod
    def format_messages_for_api(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """
        Convert aiNagisa BaseMessage objects to Gemini API format.
        
        Args:
            messages: List of BaseMessage objects from aiNagisa's internal format
            
        Returns:
            List[Dict[str, Any]]: Messages formatted for Gemini API
        """
        gemini_contents = []
        
        for message in messages:
            if message is not None:
                gemini_message = GeminiMessageFormatter.format_single_message(message)
                if gemini_message:
                    gemini_contents.append(gemini_message)
        
        return gemini_contents
    
    @staticmethod
    def format_single_message(message: BaseMessage) -> Dict[str, Any]:
        """
        Convert a single BaseMessage to Gemini API format.
        
        Args:
            message: Single BaseMessage object
            
        Returns:
            Dict[str, Any]: Message formatted for Gemini API
        """
        # Handle role mapping
        role = message.role
        if role == "assistant":
            role = "model"  # Gemini uses "model" instead of "assistant"
        
        # Format content based on type
        if isinstance(message.content, str):
            # Simple text content
            parts = [{"text": message.content}]
        elif isinstance(message.content, list):
            # Multimodal content
            parts = []
            for item in message.content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        parts.append({"text": item.get("text", "")})
                    elif item.get("type") == "image":
                        # Handle image content for Gemini
                        image_part = GeminiMessageFormatter._format_image_content(item)
                        if image_part:
                            parts.append(image_part)
                    elif item.get("type") == "tool_result":
                        # Handle tool result content
                        tool_part = GeminiMessageFormatter._format_tool_result(item)
                        if tool_part:
                            parts.append(tool_part)
                    else:
                        # Generic content - try to extract text
                        text_content = item.get("text") or str(item)
                        if text_content:
                            parts.append({"text": text_content})
        else:
            # Fallback: convert to string
            parts = [{"text": str(message.content)}]
        
        return {
            "role": role,
            "parts": parts
        }
    
    @staticmethod
    def _format_image_content(image_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format image content for Gemini API.
        
        Args:
            image_item: Image content dictionary
            
        Returns:
            Dict[str, Any]: Formatted image part for Gemini
        """
        # Handle different image formats
        if "url" in image_item:
            # Image URL
            return {
                "fileData": {
                    "fileUri": image_item["url"]
                }
            }
        elif "data" in image_item:
            # Base64 image data
            return {
                "inlineData": {
                    "mimeType": image_item.get("mime_type", "image/jpeg"),
                    "data": image_item["data"]
                }
            }
        elif "file_path" in image_item:
            # Local file path (need to handle upload)
            # This would require additional file upload logic
            return {
                "text": f"[Image: {image_item['file_path']}]"
            }
        
        return None
    
    @staticmethod
    def _format_tool_result(tool_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format tool result content for Gemini API.
        
        Args:
            tool_item: Tool result dictionary
            
        Returns:
            Dict[str, Any]: Formatted tool result part for Gemini
        """
        return {
            "functionResponse": {
                "name": tool_item.get("name", "unknown_tool"),
                "response": {
                    "content": tool_item.get("content", ""),
                    "result": tool_item.get("result", tool_item.get("content", ""))
                }
            }
        }
    
    @staticmethod
    def format_messages_for_gemini(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """
        Legacy method name for backward compatibility.
        
        Args:
            messages: List of BaseMessage objects
            
        Returns:
            List[Dict[str, Any]]: Messages formatted for Gemini API
        """
        return GeminiMessageFormatter.format_messages_for_api(messages)