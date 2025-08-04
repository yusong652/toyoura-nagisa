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
        
        Handles conversation history messages for context initialization and content generation.
        Tool results are handled separately via add_tool_result pathway.
        
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
