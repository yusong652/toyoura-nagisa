"""
OpenAI Message Formatter

Handles conversion of internal message formats to OpenAI API format.
Supports multimodal content, tool calls, and message history processing.
"""

from typing import List, Dict, Any, Union
from backend.domain.models.messages import BaseMessage
from backend.infrastructure.llm.base.message_formatter import BaseMessageFormatter


class OpenAIMessageFormatter(BaseMessageFormatter):
    """
    Format messages for OpenAI API consumption
    
    Converts internal message objects to OpenAI API format while preserving
    all content types including text, images, tool calls, and tool results.
    """
    
    @staticmethod
    def format_messages(
        messages: List[BaseMessage], 
        preserve_thinking: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Convert internal messages to OpenAI API format
        
        Args:
            messages: List of internal message objects
            preserve_thinking: Whether to preserve thinking content in context
            
        Returns:
            List of OpenAI-formatted message dictionaries
        """
        formatted_messages = []
        
        for msg in messages:
            # Handle assistant messages with tool calls
            if msg.role == "assistant" and hasattr(msg, "tool_calls") and msg.tool_calls:
                formatted_messages.append({
                    "role": "assistant",
                    "content": OpenAIMessageFormatter._extract_text_content(msg.content),
                    "tool_calls": OpenAIMessageFormatter._format_tool_calls(msg.tool_calls)
                })
                continue
            
            # Handle tool result messages
            if hasattr(msg, "role") and msg.role == "tool":
                formatted_content = OpenAIMessageFormatter._format_tool_result(msg.content)
                formatted_messages.append({
                    "role": "tool",
                    "content": formatted_content,
                    "tool_call_id": getattr(msg, "tool_call_id", "")
                })
                continue
            
            # Handle regular messages with multimodal content
            if isinstance(msg.content, list):
                openai_content = OpenAIMessageFormatter._format_multimodal_content(
                    msg.content, preserve_thinking
                )
                formatted_messages.append({
                    "role": msg.role,
                    "content": openai_content
                })
            else:
                # Simple text content
                text_content = str(msg.content) if msg.content else ""
                formatted_messages.append({
                    "role": msg.role,
                    "content": text_content
                })
        
        return formatted_messages
    
    @staticmethod
    def _format_multimodal_content(
        content: List[Dict[str, Any]], 
        preserve_thinking: bool = True
    ) -> Union[str, List[Dict[str, Any]]]:
        """
        Format multimodal content for OpenAI API
        
        Args:
            content: List of content blocks
            preserve_thinking: Whether to preserve thinking content
            
        Returns:
            OpenAI-formatted content - either string for text-only or array for multimodal
        """
        formatted_content = []
        has_non_text_content = False
        
        for block in content:
            if not isinstance(block, dict):
                # Handle non-dict content
                formatted_content.append({
                    "type": "text",
                    "text": str(block)
                })
                continue
            
            # Handle text content
            if "text" in block and block["text"]:
                if block.get("type") == "text" or "type" not in block:
                    formatted_content.append({
                        "type": "text",
                        "text": block["text"]
                    })
            elif block.get("type") == "text" and block.get("text"):
                formatted_content.append({
                    "type": "text",
                    "text": block["text"]
                })
            
            # Handle image content (inline_data format)
            elif "inline_data" in block:
                inline_data = block["inline_data"]
                # Validate inline_data has actual data
                if OpenAIMessageFormatter.validate_inline_data(inline_data):
                    mime_type = inline_data.get("mime_type", "image/png")
                    data = inline_data["data"]
                    
                    # Convert bytes to base64 string if needed
                    if isinstance(data, bytes):
                        import base64
                        data = base64.b64encode(data).decode('utf-8')
                    
                    # Ensure base64 string is clean
                    if isinstance(data, str):
                        data = data.strip().replace('\n', '').replace('\r', '').replace(' ', '')
                    
                    # Validate mime type
                    supported_types = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp']
                    if mime_type not in supported_types:
                        mime_type = 'image/png'
                    
                    formatted_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{data}",
                            "detail": "high"  # Use high detail for better image understanding
                        }
                    })
                    has_non_text_content = True
            
            # Handle image content (direct image_url format)
            elif block.get("type") == "image_url":
                formatted_content.append(block)
                has_non_text_content = True
            
            # Handle image content (legacy format with type="image")
            elif block.get("type") == "image" and "inline_data" in block:
                inline_data = block["inline_data"]
                if OpenAIMessageFormatter.validate_inline_data(inline_data):
                    mime_type = inline_data.get("mime_type", "image/png")
                    data = inline_data["data"]
                    
                    # Convert bytes to base64 string if needed
                    if isinstance(data, bytes):
                        import base64
                        data = base64.b64encode(data).decode('utf-8')
                    
                    formatted_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{data}",
                            "detail": "high"
                        }
                    })
                    has_non_text_content = True
            
            # Handle thinking content
            elif block.get("type") == "thinking" and preserve_thinking:
                # Preserve model thoughts as normal text for context
                thinking_text = block.get("thinking", "")
                if thinking_text:
                    formatted_content.append({
                        "type": "text", 
                        "text": f"<thinking>{thinking_text}</thinking>"
                    })
            
            # Skip redacted thinking content
            elif block.get("type") == "redacted_thinking":
                continue
        
        # If only text content, return as simple string (OpenAI optimization)
        if not has_non_text_content and len(formatted_content) == 1 and formatted_content[0].get("type") == "text":
            return formatted_content[0]["text"]
        
        # If only text content with multiple blocks, concatenate
        if not has_non_text_content:
            text_parts = [block.get("text", "") for block in formatted_content if block.get("type") == "text"]
            return "".join(text_parts) if text_parts else ""
        
        # Return multimodal content array
        return formatted_content
    
    @staticmethod
    def _extract_text_content(content: Union[str, List[Dict[str, Any]]]) -> str:
        """
        Extract plain text from content for tool call messages
        
        Args:
            content: Message content (string or list of blocks)
            
        Returns:
            Extracted text content
        """
        if isinstance(content, str):
            return content
        
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    if "text" in block:
                        text_parts.append(block["text"])
                    elif block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif block.get("type") == "thinking":
                        # Include thinking in text extraction for assistant messages
                        thinking_text = block.get("thinking", "")
                        if thinking_text:
                            text_parts.append(f"<thinking>{thinking_text}</thinking>")
                else:
                    text_parts.append(str(block))
            return "".join(text_parts)
        
        return str(content) if content else ""
    
    @staticmethod
    def _format_tool_calls(tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Format tool calls for OpenAI API
        
        Args:
            tool_calls: Internal tool call format
            
        Returns:
            OpenAI-formatted tool calls
        """
        formatted_calls = []
        
        for call in tool_calls:
            formatted_calls.append({
                "id": call.get("id", ""),
                "type": "function",
                "function": {
                    "name": call.get("name", ""),
                    "arguments": OpenAIMessageFormatter._format_arguments(call.get("arguments", {}))
                }
            })
        
        return formatted_calls
    
    @staticmethod
    def _format_arguments(arguments: Union[Dict[str, Any], str]) -> str:
        """
        Format tool call arguments as JSON string
        
        Args:
            arguments: Tool arguments (dict or string)
            
        Returns:
            JSON-formatted arguments string
        """
        if isinstance(arguments, str):
            return arguments
        
        return OpenAIMessageFormatter.safe_json_serialize(arguments, ensure_ascii=False)
    
    @staticmethod
    def _format_tool_result(content: Any) -> Union[str, List[Dict[str, Any]]]:
        """
        Format tool result content for OpenAI API with proper multimodal support
        
        OpenAI supports images in tool results when formatted as multimodal content.
        This method now correctly handles inline_data from tools and converts them
        to proper OpenAI image_url format.
        
        Args:
            content: Tool result content (can contain inline_data for images)
            
        Returns:
            Formatted tool result - multimodal array if contains images, string otherwise
        """
        print(f"[DEBUG] _format_tool_result called with content type: {type(content)}")
        if isinstance(content, dict):
            print(f"[DEBUG] Content keys: {list(content.keys())}")
        elif isinstance(content, str):
            print(f"[DEBUG] Content string length: {len(content)}")
        print(f"[DEBUG] Content preview: {str(content)[:200]}...")
        # Handle tool results with llm_content structure and top-level inline_data
        if isinstance(content, dict) and 'llm_content' in content and 'inline_data' in content:
            print(f"[DEBUG] Found combined llm_content + inline_data structure")
            
            llm_content = content['llm_content']
            inline_data = content['inline_data']  # inline_data is at top level, not in llm_content
            
            print(f"[DEBUG] llm_content type: {type(llm_content)}")
            print(f"[DEBUG] inline_data type: {type(inline_data)}")
            
            if isinstance(llm_content, dict):
                print(f"[DEBUG] llm_content keys: {list(llm_content.keys())}")
            if isinstance(inline_data, dict):
                print(f"[DEBUG] inline_data keys: {list(inline_data.keys())}")
            
            # Check if inline_data actually contains image data
            validation_result = OpenAIMessageFormatter.validate_inline_data(inline_data)
            print(f"[DEBUG] inline_data validation result: {validation_result}")
            
            if validation_result:
                print(f"[DEBUG] Creating multimodal content for combined structure")
                # Create multimodal content for OpenAI
                multimodal_content = []
                
                # Add text description first
                text_parts = []
                
                # Add operation info if available
                if isinstance(llm_content, dict) and 'operation' in llm_content:
                    operation = llm_content['operation']
                    if isinstance(operation, dict):
                        op_type = operation.get('type', 'unknown')
                        op_path = operation.get('path', 'unknown path')
                        text_parts.append(f"Successfully executed {op_type} on {op_path}")
                
                # Add file info if available
                if isinstance(llm_content, dict) and 'file_info' in llm_content:
                    file_info = llm_content['file_info']
                    if isinstance(file_info, dict):
                        size = file_info.get('size_bytes', 0)
                        file_type = file_info.get('file_type', 'unknown')
                        text_parts.append(f"File type: {file_type}, Size: {size} bytes")
                
                # Add the text content block
                if text_parts:
                    multimodal_content.append({
                        "type": "text",
                        "text": "\n".join(text_parts)
                    })
                
                # Add the image content block
                mime_type = inline_data.get('mime_type', 'image/png')
                data = inline_data.get('data', '')
                
                # Convert bytes to base64 string if needed
                if isinstance(data, bytes):
                    import base64
                    data = base64.b64encode(data).decode('utf-8')
                
                # Clean up base64 string
                if isinstance(data, str):
                    data = data.strip().replace('\n', '').replace('\r', '').replace(' ', '')
                
                # Validate and normalize mime type
                supported_types = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp']
                if mime_type not in supported_types:
                    mime_type = 'image/png'
                
                multimodal_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{data}",
                        "detail": "high"
                    }
                })
                
                print(f"[DEBUG] Successfully created multimodal content with {len(multimodal_content)} blocks")
                return multimodal_content
            
            # inline_data exists but validation failed, serialize normally
            else:
                print(f"[DEBUG] inline_data validation failed, serializing as JSON")
                return OpenAIMessageFormatter.safe_json_serialize(content, ensure_ascii=False)
        
        # Handle tool results with llm_content but no inline_data
        elif isinstance(content, dict) and 'llm_content' in content:
            print(f"[DEBUG] Found llm_content only (no inline_data)")
            return OpenAIMessageFormatter.safe_json_serialize(content, ensure_ascii=False)
        
        # Handle direct inline_data in content (common format from tools)
        elif isinstance(content, dict) and 'inline_data' in content:
            print(f"[DEBUG] Entering direct inline_data branch")
            print(f"[DEBUG] Found direct inline_data in content")
            inline_data = content['inline_data']
            
            # Debug: Log the inline_data structure
            print(f"[DEBUG] Processing inline_data: {type(inline_data)}")
            print(f"[DEBUG] inline_data keys: {list(inline_data.keys()) if isinstance(inline_data, dict) else 'not a dict'}")
            if isinstance(inline_data, dict) and 'data' in inline_data:
                data = inline_data['data']
                print(f"[DEBUG] data type: {type(data)}, data length: {len(data) if hasattr(data, '__len__') else 'no length'}")
            
            # Check if inline_data actually contains data (not just empty structure)
            validation_result = OpenAIMessageFormatter.validate_inline_data(inline_data)
            print(f"[DEBUG] inline_data validation result: {validation_result}")
            
            if validation_result:
                print(f"[DEBUG] inline_data validation passed - creating multimodal content")
                multimodal_content = []
                
                # Add descriptive text first (since this is likely from a file read operation)
                text_parts = []
                
                # Infer operation from context
                text_parts.append("File content loaded successfully")
                
                # Add any other fields as context
                text_content = {k: v for k, v in content.items() if k != 'inline_data'}
                if text_content:
                    if 'status' in text_content:
                        text_parts.append(f"Status: {text_content['status']}")
                    if 'message' in text_content:
                        text_parts.append(f"Message: {text_content['message']}")
                    
                    # Add other fields as JSON for context  
                    other_fields = {k: v for k, v in text_content.items() 
                                  if k not in ['status', 'message']}
                    if other_fields:
                        text_parts.append(f"Details: {OpenAIMessageFormatter.safe_json_serialize(other_fields, ensure_ascii=False)}")
                
                # Add the text content block
                multimodal_content.append({
                    "type": "text",
                    "text": "\n".join(text_parts)
                })
                
                # Add the image content block
                mime_type = inline_data.get('mime_type', 'image/png')
                data = inline_data.get('data', '')
                
                # Convert bytes to base64 string if needed
                if isinstance(data, bytes):
                    import base64
                    data = base64.b64encode(data).decode('utf-8')
                
                # Clean up base64 string
                if isinstance(data, str):
                    data = data.strip().replace('\n', '').replace('\r', '').replace(' ', '')
                
                # Validate and normalize mime type
                supported_types = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp']
                if mime_type not in supported_types:
                    mime_type = 'image/png'
                
                multimodal_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{data}",
                        "detail": "high"
                    }
                })
                
                print(f"[DEBUG] Created multimodal content with {len(multimodal_content)} blocks")
                return multimodal_content
            else:
                # inline_data exists but has no actual data, treat as regular structured data
                print(f"[DEBUG] inline_data validation failed - serializing as JSON string")
                return OpenAIMessageFormatter.safe_json_serialize(content, ensure_ascii=False)
        
        # Handle content that might already be in multimodal format (list of content blocks)
        elif isinstance(content, list):
            # Process multimodal content list and convert to proper OpenAI format
            multimodal_content = []
            
            for item in content:
                if isinstance(item, dict):
                    # Handle text blocks
                    if item.get("type") == "text":
                        multimodal_content.append({
                            "type": "text",
                            "text": item.get("text", "")
                        })
                    # Handle inline_data blocks - convert to image_url format
                    elif "inline_data" in item:
                        inline_data = item["inline_data"]
                        if OpenAIMessageFormatter.validate_inline_data(inline_data):
                            mime_type = inline_data.get('mime_type', 'image/png')
                            data = inline_data.get('data', '')
                            
                            # Convert bytes to base64 string if needed
                            if isinstance(data, bytes):
                                import base64
                                data = base64.b64encode(data).decode('utf-8')
                            
                            multimodal_content.append({
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{data}",
                                    "detail": "high"
                                }
                            })
                    # Handle already formatted image_url blocks
                    elif item.get("type") == "image_url":
                        multimodal_content.append(item)
                    # Handle other structured content as text
                    else:
                        multimodal_content.append({
                            "type": "text", 
                            "text": OpenAIMessageFormatter.safe_json_serialize(item, ensure_ascii=False)
                        })
                else:
                    # Handle non-dict items as text
                    multimodal_content.append({
                        "type": "text",
                        "text": str(item)
                    })
            
            return multimodal_content if multimodal_content else ""
        
        # Regular structured data, serialize to JSON string
        elif isinstance(content, dict):
            print(f"[DEBUG] Entering final dict serialization branch")
            return OpenAIMessageFormatter.safe_json_serialize(content, ensure_ascii=False)
        
        # Simple string or other types, convert to string
        else:
            print(f"[DEBUG] Entering final string conversion branch")
            return str(content) if content else ""