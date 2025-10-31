"""
Kimi (Moonshot) Debugger

Debugging utilities for Kimi Chat Completions API calls.
"""

import json
from typing import Dict, Any, List


class KimiDebugger:
    """
    Debugging utilities for Kimi API calls.

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
        print(f"[KIMI DEBUG] API Request Payload")
        print(f"{'='*80}")
        print(f"[KIMI] Model: {api_kwargs.get('model')}")
        print(f"[KIMI] Temperature: {api_kwargs.get('temperature')}")
        print(f"[KIMI] Messages count: {len(messages)}")
        print(f"[KIMI] Tools count: {len(tools)}")

        # Print tool schemas with full details
        if tools:
            print(f"\n[KIMI] Tool Schemas:")
            for i, tool in enumerate(tools):
                function = tool.get('function', {})
                print(f"[KIMI]   Tool {i+1}: {function.get('name', 'unknown')}")
                print(f"[KIMI]     Description: {function.get('description', 'N/A')[:80]}")

                params = function.get('parameters', {})
                required = params.get('required', [])
                properties = params.get('properties', {})

                print(f"[KIMI]     Required params: {required if required else 'none'}")
                print(f"[KIMI]     Total params: {list(properties.keys())}")

                # Print full schema for tools with no parameters
                if not properties or not required:
                    print(f"[KIMI]     Full schema: {json.dumps(params, indent=10)}")

        # Print recent messages
        print(f"\n[KIMI] Recent Messages (last 2):")
        for msg in messages[-2:]:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')

            if isinstance(content, str):
                content_preview = content[:150] + '...' if len(content) > 150 else content
            else:
                content_preview = str(content)[:150]

            print(f"[KIMI]   [{role}]: {content_preview}")

            if 'tool_calls' in msg:
                print(f"[KIMI]     Tool calls: {len(msg['tool_calls'])}")
                for tc in msg['tool_calls']:
                    print(f"[KIMI]       - {tc.get('function', {}).get('name', 'unknown')}")

        print(f"{'='*80}\n")

    @staticmethod
    def print_tool_call_received(tool_calls: List[Dict[str, Any]]):
        """
        Print tool calls received from API response.

        Args:
            tool_calls: List of tool calls from ChatCompletion
        """
        print(f"\n[KIMI DEBUG] Tool Calls Received:")
        for i, tc in enumerate(tool_calls):
            print(f"[KIMI]   Call {i+1}:")
            print(f"[KIMI]     ID: {tc.get('id', 'N/A')}")
            print(f"[KIMI]     Function: {tc.get('function', {}).get('name', 'unknown')}")

            args = tc.get('function', {}).get('arguments', '')
            if isinstance(args, str):
                try:
                    parsed = json.loads(args) if args else {}
                    print(f"[KIMI]     Arguments: {json.dumps(parsed, indent=8)}")
                except json.JSONDecodeError:
                    print(f"[KIMI]     Arguments (raw): {args}")
            else:
                print(f"[KIMI]     Arguments: {args}")
        print()

    @staticmethod
    def print_extracted_tool_calls(tool_calls: List[Dict[str, Any]]):
        """
        Print extracted tool calls after processing.

        Args:
            tool_calls: Processed tool calls with name, arguments, id
        """
        print(f"\n[KIMI DEBUG] Extracted Tool Calls:")
        for i, tc in enumerate(tool_calls):
            print(f"[KIMI]   Call {i+1}:")
            print(f"[KIMI]     Name: {tc.get('name', 'N/A')}")
            print(f"[KIMI]     ID: {tc.get('id', 'N/A')}")
            print(f"[KIMI]     Arguments type: {type(tc.get('arguments')).__name__}")
            print(f"[KIMI]     Arguments: {json.dumps(tc.get('arguments', {}), indent=8)}")
        print()


__all__ = ['KimiDebugger']
