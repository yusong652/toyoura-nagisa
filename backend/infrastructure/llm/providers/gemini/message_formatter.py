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
    def format_messages(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """
        Convert aiNagisa BaseMessage objects to Gemini API format.
        
        Args:
            messages: List of BaseMessage objects from aiNagisa's internal format
            
        Returns:
            List[Dict[str, Any]]: Messages formatted for Gemini API
        """
        from google.genai import types
        
        contents = []
        
        for msg in messages:
            if msg is None:
                continue
                
            parts = []
            
            # Handle message content based on format
            if isinstance(msg.content, list):
                # Multi-part message (text + optional multimodal content)
                for item in msg.content:
                    if isinstance(item, dict):
                        # Skip thinking content - don't include in API calls
                        if item.get("type") in ["thinking", "redacted_thinking"]:
                            continue
                            
                        if item.get("type") == "text" and item.get("text"):
                            parts.append(types.Part(text=item["text"]))
                        elif item.get("type") == "image" and "inline_data" in item:
                            # Handle image content using unified processing
                            blob = GeminiMessageFormatter._process_inline_data(item['inline_data'])
                            if blob:
                                parts.append(types.Part(inline_data=blob))
                        elif item.get("type") == "tool_result":
                            # Handle tool result content
                            tool_part = GeminiMessageFormatter._format_tool_result(item)
                            if tool_part:
                                parts.append(tool_part)
                        elif "text" in item and item["text"]:
                            # Generic text content
                            parts.append(types.Part(text=item["text"]))
                        elif "inline_data" in item:
                            # Generic inline data (images, etc.)
                            blob = GeminiMessageFormatter._process_inline_data(item['inline_data'])
                            if blob:
                                parts.append(types.Part(inline_data=blob))
            else:
                # Simple text message
                parts.append(types.Part(text=str(msg.content)))
            
            # Map role and add to contents if we have parts
            if parts:
                mapped_role = GeminiMessageFormatter._map_role(msg.role)
                contents.append({"role": mapped_role, "parts": parts})
        
        return contents
    
    
    @staticmethod
    def _map_role(role: str) -> str:
        """
        Map internal role names to Gemini API role names.
        
        Args:
            role: Internal role name
            
        Returns:
            Gemini API compatible role name
        """
        if role == "assistant":
            return "model"
        return "user"

    @staticmethod
    def _process_inline_data(inline_data: Dict[str, Any]) -> Any:
        """
        Process inline_data, converting base64 strings to Gemini API Blob format.
        
        Args:
            inline_data: Dictionary containing mime_type and data
            
        Returns:
            types.Blob object, or None if processing fails
        """
        try:
            from google.genai import types
            import base64
            
            data_field = inline_data['data']
            mime_type = inline_data.get('mime_type', 'image/png')
            
            # If data is a string (base64), decode to bytes
            if isinstance(data_field, str):
                data_field = base64.b64decode(data_field)
            
            # Ensure data is in bytes format
            if not isinstance(data_field, bytes):
                print(f"[WARNING] Invalid data format: expected bytes, got {type(data_field)}")
                return None
            
            return types.Blob(mime_type=mime_type, data=data_field)
            
        except Exception as e:
            print(f"[WARNING] Failed to process inline_data: {e}")
            return None

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
    def _format_tool_result(tool_item: Dict[str, Any]) -> Any:
        """
        Format tool result content for Gemini API.
        
        Args:
            tool_item: Tool result dictionary
            
        Returns:
            types.Part: Formatted tool result part for Gemini
        """
        try:
            from google.genai import types
            
            return types.Part(
                function_response=types.FunctionResponse(
                    name=tool_item.get("name", "unknown_tool"),
                    response={
                        "result": tool_item.get("content", tool_item.get("result", ""))
                    }
                )
            )
        except Exception as e:
            print(f"[WARNING] Failed to format tool result: {e}")
            # Fallback to text representation
            from google.genai import types
            return types.Part(text=f"Tool result: {tool_item.get('content', '')}")
    
    @staticmethod
    def format_tool_result_for_context(tool_name: str, result: Any) -> Dict[str, Any]:
        """
        Format tool result for Gemini working context.
        
        Creates complete working context entry with proper multimodal handling
        and function response formatting for Gemini API.
        
        Args:
            tool_name: Name of the tool that was executed
            result: Tool execution result (can contain inline_data for multimodal)
            
        Returns:
            Dict[str, Any]: Complete working context entry for Gemini API
        """
        from google.genai import types
        
        parts = []
        
        # Handle multimodal content (inline_data) if present
        if isinstance(result, dict) and 'inline_data' in result:
            inline_data = result['inline_data']
            # Check if inline_data actually contains data
            if inline_data and 'data' in inline_data and inline_data['data']:
                blob = GeminiMessageFormatter._process_inline_data(inline_data)
                if blob:
                    parts.append(types.Part(inline_data=blob))
        
        # Create function response part
        # Filter out inline_data to avoid duplication in function response
        filtered_result = {k: v for k, v in result.items() if k != 'inline_data'} if isinstance(result, dict) else result
        
        function_response = types.FunctionResponse(
            name=tool_name,
            response=filtered_result if filtered_result else result
        )
        parts.append(types.Part(function_response=function_response))
        
        # Return complete working context entry
        return {
            "role": "user",
            "parts": parts
        }

    @staticmethod
    def format_messages_for_gemini(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """
        Legacy method name for backward compatibility.
        
        Format history messages for Gemini API initialization.
        
        Optimized for historical message processing - only handles message types 
        that actually appear in stored conversation history:
        - User messages (text + optional multimodal content)  
        - Assistant final responses (text only)
        
        REMOVED (not in history):
        - Tool calls, tool responses, thinking blocks, intermediate states
        
        Args:
            messages: List of BaseMessage objects
            
        Returns:
            List[Dict[str, Any]]: Messages formatted for Gemini API
        """
        return GeminiMessageFormatter.format_messages(messages)