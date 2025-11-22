"""
Zhipu debug utilities for API request/response logging.
"""

import json
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
        simplified_request = api_kwargs.copy()

        # Simplify messages (only truncate system prompt, keep others full)
        if 'messages' in simplified_request:
            simplified_messages = []
            for msg in simplified_request['messages']:
                msg_copy = msg.copy()
                role = msg_copy.get('role', '')
                content = msg_copy.get('content', '')

                # Only simplify system prompt
                if role == 'system' and isinstance(content, str) and len(content) > 150:
                    msg_copy['content'] = content[:150] + f"... (truncated, {len(content)} chars total)"

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
