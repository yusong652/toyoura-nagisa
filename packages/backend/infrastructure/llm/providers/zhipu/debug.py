"""
Zhipu debug utilities for API request/response logging.
"""

import json
import copy
from typing import Dict, Any, List


class ZhipuDebugger:
    """Debug utilities for Zhipu API interactions"""

    @staticmethod
    def print_api_request(
        api_kwargs: Dict[str, Any],
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]]
    ):
        """Print formatted API request information"""
        print("\n" + "=" * 80)
        print("[DEBUG] Zhipu API Request")
        print("=" * 80)

        # Basic parameters
        print(f"\nModel: {api_kwargs.get('model', 'N/A')}")
        print(f"Temperature: {api_kwargs.get('temperature', 'N/A')}")
        print(f"Top P: {api_kwargs.get('top_p', 'N/A')}")
        print(f"Max Tokens: {api_kwargs.get('max_tokens', 'N/A')}")
        print(f"Stream: {api_kwargs.get('stream', False)}")

        # Thinking mode configuration
        thinking_config = api_kwargs.get('thinking')
        if thinking_config:
            print(f"Thinking Mode: {thinking_config.get('type', 'N/A')}")
        else:
            print("Thinking Mode: disabled")

        # Original API Request (with simplified system prompt and tool schemas)
        print("\n" + "=" * 80)
        print("--- API Request (Original Format, Simplified Verbose Fields) ---")
        print("=" * 80)

        # Create a copy of api_kwargs with simplified verbose fields
        simplified_request = copy.deepcopy(api_kwargs)

        # Simplify messages (truncate system prompt and multimodal content)
        if 'messages' in simplified_request:
            simplified_messages = []
            for msg in simplified_request['messages']:
                msg_copy = msg.copy()
                role = msg_copy.get('role', '')
                content = msg_copy.get('content', '')

                # Simplify system prompt
                if role == 'system' and isinstance(content, str) and len(content) > 150:
                    msg_copy['content'] = content[:150] + f"... (truncated, {len(content)} chars total)"

                # Truncate multimodal content (image_url with base64 data)
                if isinstance(content, list):
                    msg_copy['content'] = ZhipuDebugger._truncate_multimodal_content(content)

                simplified_messages.append(msg_copy)
            simplified_request['messages'] = simplified_messages

        # Simplify tools (keep structure but remove verbose descriptions/parameters)
        if 'tools' in simplified_request:
            simplified_tools = []
            for tool in simplified_request['tools']:
                tool_copy = {}
                tool_copy['type'] = tool.get('type', 'function')

                if 'function' in tool:
                    func = tool['function']
                    tool_copy['function'] = {
                        'name': func.get('name', 'unknown')
                    }

                    # Add description if short
                    desc = func.get('description', '')
                    if desc and len(desc) <= 100:
                        tool_copy['function']['description'] = desc
                    elif desc:
                        tool_copy['function']['description'] = desc[:100] + "... (truncated)"

                    # Simplify parameters
                    if 'parameters' in func:
                        params = func['parameters']
                        if isinstance(params, dict):
                            props = params.get('properties', {})
                            required = params.get('required', [])
                            tool_copy['function']['parameters'] = {
                                'type': params.get('type', 'object'),
                                'properties': f"<{len(props)} properties>",
                                'required': required
                            }

                # Handle web_search type
                if 'web_search' in tool:
                    tool_copy['web_search'] = tool['web_search']

                simplified_tools.append(tool_copy)
            simplified_request['tools'] = simplified_tools

        print(json.dumps(simplified_request, indent=2, ensure_ascii=False, default=str))

        print("=" * 80 + "\n")

    @staticmethod
    def log_raw_response(response: Any):
        """Log raw API response"""
        print("\n" + "=" * 80)
        print("[DEBUG] Zhipu API Response")
        print("=" * 80)
        print(json.dumps(response, indent=2, ensure_ascii=False))
        print("=" * 80 + "\n")

    @staticmethod
    def log_streaming_chunk(chunk: Any):
        """Log streaming chunk"""
        print(f"[DEBUG] Stream chunk: {chunk}")

    @staticmethod
    def _truncate_multimodal_content(content: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Truncate multimodal content (image_url with base64 data) for debug output.

        Args:
            content: List of content parts (text, image_url, etc.)

        Returns:
            Truncated content list with base64 data replaced by summary
        """
        truncated = []
        for part in content:
            if not isinstance(part, dict):
                truncated.append(part)
                continue

            part_copy = copy.deepcopy(part)
            part_type = part_copy.get('type', '')

            # Handle image_url with base64 data
            if part_type == 'image_url' and 'image_url' in part_copy:
                image_url = part_copy['image_url']
                url = image_url.get('url', '')

                # Check if URL is base64 data
                if isinstance(url, str) and url.startswith('data:') and len(url) > 200:
                    # Extract mime type and base64 data from data URL
                    if ';base64,' in url:
                        mime_type = url.split(';base64,')[0].replace('data:', '')
                        base64_data = url.split(';base64,')[1]
                        data_len = len(base64_data)
                        # Replace with truncated summary
                        image_url['url'] = f"data:{mime_type};base64,{base64_data[:50]}... [truncated {data_len} chars]"
                    else:
                        # Non-base64 data URL, just truncate
                        image_url['url'] = f"{url[:100]}... [truncated {len(url)} chars]"

            # Handle inline_data format (Gemini style, for compatibility)
            if 'inline_data' in part_copy:
                inline_data = part_copy['inline_data']
                data = inline_data.get('data', '')
                if isinstance(data, str) and len(data) > 200:
                    mime_type = inline_data.get('mime_type', 'unknown')
                    inline_data['data'] = f"{data[:50]}... [truncated {len(data)} chars]"

            truncated.append(part_copy)

        return truncated
