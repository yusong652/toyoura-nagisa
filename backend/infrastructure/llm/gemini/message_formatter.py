"""
Message formatting utilities for Gemini API.

Handles conversion between internal message formats and Gemini API compatible formats,
including multimodal content processing and role mapping.
"""

import base64
from typing import List, Dict, Any, Optional
from google.genai import types

from backend.infrastructure.llm.models import BaseMessage


class MessageFormatter:
    """
    Handles message formatting for Gemini API interactions.
    
    This class provides methods for:
    - Converting history messages to Gemini API format
    - Processing multimodal content (images, documents) in user messages
    - Role mapping between formats
    
    Optimized for historical message processing only - working context
    is handled directly in context manager without formatting.
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
        Format history messages for Gemini API initialization.
        
        Optimized for historical message processing - only handles message types 
        that actually appear in stored conversation history:
        - User messages (text + optional multimodal content)  
        - Assistant final responses (text only)
        
        REMOVED (not in history):
        - Tool calls, tool responses, thinking blocks, intermediate states
        
        Args:
            messages: List of BaseMessage objects from conversation history
            
        Returns:
            List of formatted message dictionaries for Gemini API
        """
        contents = []
        
        for msg in messages:
            parts = []
            
            # Handle message content based on format
            if isinstance(msg.content, list):
                # Multi-part message (text + optional multimodal content)
                for item in msg.content:
                    if "text" in item and item["text"]:
                        parts.append(types.Part(text=item["text"]))
                    elif "inline_data" in item:
                        # 使用统一的 inline_data 处理方法，保持架构一致性
                        blob = MessageFormatter.process_inline_data(item['inline_data'])
                        if blob:
                            parts.append(types.Part(inline_data=blob))
            else:
                # Simple text message
                parts.append(types.Part(text=str(msg.content)))
            
            # Map role and add to contents
            mapped_role = MessageFormatter.map_role(msg.role)
            contents.append({"role": mapped_role, "parts": parts})
        
        return contents 