"""
OpenRouter Debugger

Debugging utilities for OpenRouter Chat Completions API calls.
"""

import json
from typing import Dict, Any, List


class OpenRouterDebugger:
    """
    Debugging utilities for OpenRouter API calls.

    Provides detailed logging of request payloads, tool schemas, and responses.
    """

    @staticmethod
    def print_api_request(api_kwargs: Dict[str, Any], messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]):
        """
        Print detailed API request information.

        Args:
            api_kwargs: Full API call kwargs
            messages: Conversation messages
            tools: Tool schemas
        """
        print(f"\n{'='*80}")
        print(f"[OPENROUTER DEBUG] API Request Payload")
        print(f"{'='*80}")
        print(f"[OPENROUTER] Model: {api_kwargs.get('model')}")
        print(f"[OPENROUTER] Temperature: {api_kwargs.get('temperature')}")
        print(f"[OPENROUTER] Messages count: {len(messages)}")
        print(f"[OPENROUTER] Tools count: {len(tools)}")

        # Print tool schemas with full details
        if tools:
            print(f"\n[OPENROUTER] Tool Schemas:")
            for i, tool in enumerate(tools):
                function = tool.get('function', {})
                print(f"[OPENROUTER]   Tool {i+1}: {function.get('name', 'unknown')}")
                print(f"[OPENROUTER]     Description: {function.get('description', 'N/A')[:80]}")

                params = function.get('parameters', {})
                required = params.get('required', [])
                properties = params.get('properties', {})

                print(f"[OPENROUTER]     Required params: {required if required else 'none'}")
                print(f"[OPENROUTER]     Total params: {list(properties.keys())}")

                # Print full schema for tools with no parameters
                if not properties or not required:
                    print(f"[OPENROUTER]     Full schema: {json.dumps(params, indent=10)}")

        # Print recent messages
        print(f"\n[OPENROUTER] Recent Messages (last 2):")
        for msg in messages[-2:]:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')

            if isinstance(content, str):
                content_preview = content[:150] + '...' if len(content) > 150 else content
            else:
                content_preview = str(content)[:150]

            print(f"[OPENROUTER]   [{role}]: {content_preview}")

            if 'tool_calls' in msg:
                print(f"[OPENROUTER]     Tool calls: {len(msg['tool_calls'])}")
                for tc in msg['tool_calls']:
                    print(f"[OPENROUTER]       - {tc.get('function', {}).get('name', 'unknown')}")

        print(f"{'='*80}\n")

    @staticmethod
    def print_tool_call_received(tool_calls: List[Dict[str, Any]]):
        """
        Print tool calls received from API response.

        Args:
            tool_calls: List of tool calls from ChatCompletion
        """
        print(f"\n[OPENROUTER DEBUG] Tool Calls Received:")
        for i, tc in enumerate(tool_calls):
            print(f"[OPENROUTER]   Call {i+1}:")
            print(f"[OPENROUTER]     ID: {tc.get('id', 'N/A')}")
            print(f"[OPENROUTER]     Function: {tc.get('function', {}).get('name', 'unknown')}")

            args = tc.get('function', {}).get('arguments', '')
            if isinstance(args, str):
                try:
                    parsed = json.loads(args) if args else {}
                    print(f"[OPENROUTER]     Arguments: {json.dumps(parsed, indent=8)}")
                except json.JSONDecodeError:
                    print(f"[OPENROUTER]     Arguments (raw): {args}")
            else:
                print(f"[OPENROUTER]     Arguments: {args}")
        print()

    @staticmethod
    def print_extracted_tool_calls(tool_calls: List[Dict[str, Any]]):
        """
        Print extracted tool calls after processing.

        Args:
            tool_calls: Processed tool calls with name, arguments, id
        """
        print(f"\n[OPENROUTER DEBUG] Extracted Tool Calls:")
        for i, tc in enumerate(tool_calls):
            print(f"[OPENROUTER]   Call {i+1}:")
            print(f"[OPENROUTER]     Name: {tc.get('name', 'N/A')}")
            print(f"[OPENROUTER]     ID: {tc.get('id', 'N/A')}")
            print(f"[OPENROUTER]     Arguments type: {type(tc.get('arguments')).__name__}")
            print(f"[OPENROUTER]     Arguments: {json.dumps(tc.get('arguments', {}), indent=8)}")
        print()


__all__ = ['OpenRouterDebugger']
