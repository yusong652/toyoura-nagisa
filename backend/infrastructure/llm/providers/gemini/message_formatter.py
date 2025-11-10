"""
Gemini-specific message formatter.

Handles conversion from aiNagisa's internal message format to Gemini API format.
"""

from typing import List, Dict, Any, Optional
from backend.domain.models.messages import BaseMessage
from backend.infrastructure.llm.base.message_formatter import BaseMessageFormatter


class GeminiMessageFormatter(BaseMessageFormatter):
    """
    Gemini-specific message formatter.

    Converts aiNagisa BaseMessage objects to Gemini API format with proper
    handling of multimodal content, roles, and metadata.
    """

    @staticmethod
    def format_messages(
        messages: List[BaseMessage],
        preserve_thinking: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """
        Convert aiNagisa BaseMessage objects to Gemini API format.

        Handles conversation history messages for context initialization and content generation.
        Tool results are handled separately via add_tool_result pathway.

        Args:
            messages: List of BaseMessage objects from aiNagisa's internal format
            preserve_thinking: Whether to preserve thinking content with thought_signature.
                             If None, automatically reads from Gemini client configuration.
                             Explicit True/False values override the configuration.

        Returns:
            List[Dict[str, Any]]: Messages formatted for Gemini API
        """
        # Auto-detect from config if not explicitly specified
        if preserve_thinking is None:
            from .config import get_gemini_client_config
            config = get_gemini_client_config()
            preserve_thinking = config.model_settings.preserve_thinking_in_history
        from google.genai import types
        import base64
        
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
                        # Handle thinking content based on preserve_thinking flag
                        if item.get("type") == "thinking":
                            if preserve_thinking:
                                # Preserve thinking content for cross-turn reasoning
                                thinking_text = item.get("thinking", "")
                                if thinking_text:
                                    # Create thinking part with thought=True flag
                                    thinking_part = types.Part(text=thinking_text, thought=True)

                                    # Restore thought_signature if available (for tool calling chains)
                                    thought_sig_b64 = item.get("thought_signature")
                                    if thought_sig_b64:
                                        try:
                                            # Decode from base64 string back to bytes
                                            thought_sig_bytes = base64.b64decode(thought_sig_b64)
                                            thinking_part.thought_signature = thought_sig_bytes
                                        except Exception as e:
                                            print(f"[WARNING] Failed to decode thought_signature: {e}")

                                    parts.append(thinking_part)
                            # else: skip thinking (default behavior)
                            continue

                        # Skip redacted_thinking regardless of preserve_thinking
                        if item.get("type") == "redacted_thinking":
                            continue

                        if item.get("type") == "text" and item.get("text"):
                            parts.append(types.Part(text=item["text"]))

                        # Handle tool_use blocks (for assistant messages with tool calls)
                        elif item.get("type") == "tool_use":
                            function_call = types.FunctionCall(
                                name=item.get("name"),
                                args=item.get("input", {})
                            )
                            part = types.Part(function_call=function_call)

                            # Restore thought_signature if available (for tool calling chain validation)
                            # Only when preserve_thinking is enabled
                            if preserve_thinking:
                                thought_sig_b64 = item.get("thought_signature")
                                if thought_sig_b64:
                                    try:
                                        # Decode from base64 string back to bytes
                                        thought_sig_bytes = base64.b64decode(thought_sig_b64)
                                        part.thought_signature = thought_sig_bytes
                                    except Exception as e:
                                        print(f"[WARNING] Failed to decode thought_signature for tool_use: {e}")

                            parts.append(part)

                        # Handle tool_result blocks (for user messages with tool results)
                        elif item.get("type") == "tool_result":
                            tool_result_content = item.get("content", {})

                            # Extract text from tool result content (supports parts format)
                            response_text = ""
                            if isinstance(tool_result_content, dict) and "parts" in tool_result_content:
                                for part in tool_result_content["parts"]:
                                    if isinstance(part, dict) and part.get("type") == "text":
                                        response_text = part.get("text", "")
                                        break
                            else:
                                # Fallback to string representation
                                response_text = str(tool_result_content)

                            # Create FunctionResponse for Gemini API
                            function_response = types.FunctionResponse(
                                name=item.get("tool_name", "unknown"),
                                response={
                                    "status": "error" if item.get("is_error") else "success",
                                    "content": response_text
                                }
                            )
                            parts.append(types.Part(function_response=function_response))

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
                mapped_role = GeminiMessageFormatter._map_role(msg.role) # type: ignore
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
    def format_single_message(message: BaseMessage) -> Dict[str, Any]:
        """
        Format a single BaseMessage to Gemini API format.
        
        Args:
            message: Single BaseMessage to format
            
        Returns:
            Dict[str, Any]: Single message in Gemini API format
        """
        from google.genai import types
        
        if message is None:
            return {}
            
        parts = []
        
        # Handle message content based on format
        if isinstance(message.content, list):
            # Multi-part message (text + optional multimodal content)
            for item in message.content:
                if isinstance(item, dict):
                    # Skip thinking content - don't include in API calls
                    if item.get("type") in ["thinking", "redacted_thinking"]:
                        continue

                    if item.get("type") == "text" and item.get("text"):
                        parts.append(types.Part(text=item["text"]))

                    # Handle tool_use blocks (for assistant messages with tool calls)
                    elif item.get("type") == "tool_use":
                        function_call = types.FunctionCall(
                            name=item.get("name"),
                            args=item.get("input", {})
                        )
                        parts.append(types.Part(function_call=function_call))

                    # Handle tool_result blocks (for user messages with tool results)
                    elif item.get("type") == "tool_result":
                        tool_result_content = item.get("content", {})

                        # Extract text from tool result content (supports parts format)
                        response_text = ""
                        if isinstance(tool_result_content, dict) and "parts" in tool_result_content:
                            for part in tool_result_content["parts"]:
                                if isinstance(part, dict) and part.get("type") == "text":
                                    response_text = part.get("text", "")
                                    break
                        else:
                            # Fallback to string representation
                            response_text = str(tool_result_content)

                        # Create FunctionResponse for Gemini API
                        function_response = types.FunctionResponse(
                            name=item.get("tool_name", "unknown"),
                            response={
                                "status": "error" if item.get("is_error") else "success",
                                "content": response_text
                            }
                        )
                        parts.append(types.Part(function_response=function_response))

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
            parts.append(types.Part(text=str(message.content)))
        
        # Map role and return formatted message
        if parts:
            mapped_role = GeminiMessageFormatter._map_role(message.role) # type: ignore
            return {"role": mapped_role, "parts": parts}
        
        return {}

    @staticmethod
    def format_tool_result_for_context(tool_name: str, result: Any) -> Dict[str, Any]:
        """
        Format tool result for Gemini working context.

        Creates complete working context entry with proper multimodal handling
        and function response formatting for Gemini API.

        Args:
            tool_name: Name of the tool that was executed
            result: Tool execution result with standardized parts format:
                - llm_content.parts: List of content parts (text and/or inline_data)

        Returns:
            Dict[str, Any]: Complete working context entry for Gemini API
        """
        from google.genai import types

        parts = []
        # All tools use standardized parts format
        llm_content = result["llm_content"]
        content_parts = llm_content["parts"]
        response_data = {"status": result.get("status", "success")}

        for part in content_parts:
            part_type = part["type"]

            if part_type == "inline_data":
                # Process inline_data part for multimodal content
                blob = GeminiMessageFormatter._process_inline_data(part)
                if blob:
                    parts.append(types.Part(inline_data=blob))
            elif part_type == "text":
                # Collect text content for function response
                text_content = part.get("text", "")
                if text_content:
                    response_data["content"] = text_content

        # Create function response part
        function_response = types.FunctionResponse(
            name=tool_name,
            response=response_data
        )
        parts.append(types.Part(function_response=function_response))

        # Return complete working context entry
        return {
            "role": "user",
            "parts": parts
        }
