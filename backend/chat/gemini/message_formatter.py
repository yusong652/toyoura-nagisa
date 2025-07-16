"""
Message formatting utilities for Gemini API.

Handles conversion between internal message formats and Gemini API compatible formats,
including multimodal content processing and role mapping.
"""

import json
import base64
from typing import List, Dict, Any, Optional
from google.genai import types

from backend.chat.models import BaseMessage, ToolResultMessage


class MessageFormatter:
    """
    Handles message formatting for Gemini API interactions.
    
    This class provides methods for:
    - Converting internal message formats to Gemini API format
    - Processing multimodal content (images, documents)
    - Handling tool calls and responses
    - Role mapping between formats
    """

    @staticmethod
    def map_role(role: str) -> str:
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
    def process_inline_data(inline_data: Dict[str, Any]) -> Optional[types.Blob]:
        """
        Process inline_data, converting base64 strings to Gemini API Blob format.
        
        Args:
            inline_data: Dictionary containing mime_type and data
            
        Returns:
            types.Blob object, or None if processing fails
        """
        try:
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
    def format_messages_for_gemini(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """
        Format messages into Gemini API compatible format with enhanced multimodal support.
        
        Handles:
        - Text messages with thinking blocks
        - Function calls and tool responses  
        - Multimodal content (images, documents) from tool outputs
        - Standard inline_data format and structured tool results
        
        For tool responses containing multimodal content, creates separate Parts:
        1. Image/document Part with decoded binary data
        2. Function response Part with status information
        
        Args:
            messages: List of BaseMessage objects to format
            
        Returns:
            List of formatted message dictionaries for Gemini API
        """
        contents = []
        for msg in messages:
            # Gemini function call标准：
            # - assistant function_call消息用model+function_call结构
            # - tool响应用user+function_response结构
            if msg.role == "assistant" and getattr(msg, "tool_calls", None):
                # function_call消息，可以包含思考过程和工具调用
                parts = []
                
                # 1. 提取思考过程 (thinking)
                # 这部分作为上下文提供给模型，了解它为何调用工具
                if isinstance(msg.content, list):
                    for item in msg.content:
                        if item.get("type") == "thinking" and item.get("thinking"):
                            # For thinking parts, we create a Part object where the text is the thought.
                            # The Gemini API doesn't have a 'thought=True' flag on request Parts.
                            # The model's own output format (thoughts as text) is the expected input format.
                            parts.append(types.Part(text=item["thinking"], thought=True))
                        elif item.get("type") == "text" and item.get("text"):
                            parts.append(types.Part(text=item["text"]))
                
                # 3. 添加工具调用 (tool_calls)
                for tool_call in msg.tool_calls:
                    arguments = tool_call["function"].get("arguments", {})
                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except (json.JSONDecodeError, TypeError):
                            # 如果无法解析，则保留为字符串或空字典
                            arguments = {"error": "invalid JSON arguments", "raw": arguments}
                    parts.append(types.Part(function_call=types.FunctionCall(
                        name=tool_call["function"]["name"],
                        args=arguments,
                        id=tool_call.get("id", tool_call["function"]["name"])
                    )))
                
                if parts:
                    contents.append({"role": "model", "parts": parts})
                continue

            # 处理工具响应消息
            if isinstance(msg, ToolResultMessage):
                tool_name = msg.name
                if not tool_name:
                    print(f"[WARNING] Tool response missing name: {msg}")
                    continue
                
                # 优化的多模态内容检测逻辑
                is_image = False
                inline_data = None
                
                if isinstance(msg.content, dict):
                    # 检查标准化格式: content.data.inline_data
                    if (msg.content.get("content", {}).get("format") == "inline_data" and 
                        isinstance(msg.content.get("content", {}).get("data"), dict) and
                        "inline_data" in msg.content["content"]["data"]):
                        is_image = True
                        inline_data = msg.content["content"]["data"]["inline_data"]
                    # 检查直接格式: content.inline_data (兼容性)
                    elif 'inline_data' in msg.content:
                        is_image = True
                        inline_data = msg.content['inline_data']
                
                if is_image and inline_data:
                    data_field = inline_data['data']
                    mime_type = inline_data.get('mime_type', 'image/png')
                    try:
                        image_bytes = base64.b64decode(data_field)
                        parts = [
                            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                            types.Part(function_response=types.FunctionResponse(
                                name=tool_name,
                                response={'status': 'success', 'content': 'Image file read successfully.'}
                            ))
                        ]
                    except Exception as e:
                        print(f"[WARNING] Failed to decode inline_data in tool response: {e}")
                        parts = [types.Part(function_response=types.FunctionResponse(
                            name=tool_name,
                            response={'status': 'error', 'content': 'Failed to decode image data'}
                        ))]
                    contents.append({"role": "user", "parts": parts})
                    continue
                else:
                    response_dict = msg.content if isinstance(msg.content, dict) else {"result": str(msg.content)}
                    parts = [types.Part(function_response=types.FunctionResponse(
                        name=tool_name,
                        response=response_dict
                    ))]
                contents.append({"role": "user", "parts": parts})
                continue

            # 普通消息
            parts = []
            if isinstance(msg.content, list):
                for item in msg.content:
                    # 1. 先处理图片内容
                    if "inline_data" in item:
                        inline_data = item["inline_data"]
                        data_field = inline_data["data"]
                        mime_type = inline_data.get("mime_type", "image/png")
                        try:
                            image_bytes = base64.b64decode(data_field)
                            parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
                        except Exception as e:
                            print(f"[WARNING] Failed to decode inline_data: {e}")
                            continue
                    # 2. 再处理文本内容
                    if "text" in item:
                        parts.append(types.Part(text=item["text"]))
            else:
                parts.append(types.Part(text=str(msg.content)))
            
            mapped_role = MessageFormatter.map_role(msg.role)
            contents.append({"role": mapped_role, "parts": parts})
        
        return contents 