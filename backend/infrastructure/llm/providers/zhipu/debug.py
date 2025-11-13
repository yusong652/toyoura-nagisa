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

        # Tool choice
        tool_choice = api_kwargs.get('tool_choice')
        if tool_choice:
            print(f"Tool Choice: {tool_choice}")

        # Messages
        print(f"\nMessages count: {len(messages)}")
        for i, msg in enumerate(messages):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            content_preview = str(content)[:100] + "..." if len(str(content)) > 100 else str(content)
            print(f"  [{i}] {role}: {content_preview}")

        # Tools
        print(f"\nTools count: {len(tools)}")
        for i, tool in enumerate(tools):
            tool_name = tool.get('function', {}).get('name', 'unknown')
            print(f"  [{i}] {tool_name}")

        # Complete API kwargs (for detailed inspection)
        print("\n--- Complete API Configuration ---")
        print(json.dumps(api_kwargs, indent=2, ensure_ascii=False, default=str))

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
