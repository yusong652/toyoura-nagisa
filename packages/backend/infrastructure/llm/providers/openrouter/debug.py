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
        print(f"[OPENROUTER DEBUG] API Request")
        print(f"{'='*80}")

        # Basic parameters
        print(f"\nModel: {api_kwargs.get('model', 'N/A')}")
        print(f"Temperature: {api_kwargs.get('temperature', 'N/A')}")
        print(f"Max Tokens: {api_kwargs.get('max_tokens', 'N/A')}")
        print(f"Top P: {api_kwargs.get('top_p', 'N/A')}")
        print(f"Stream: {api_kwargs.get('stream', False)}")

        # Tool choice
        tool_choice = api_kwargs.get('tool_choice')
        if tool_choice:
            print(f"Tool Choice: {tool_choice}")

        # API Request (with simplified system prompt and tool schemas)
        print(f"\n{'='*80}")
        print("--- API Request (Original Format, Simplified Verbose Fields) ---")
        print(f"{'='*80}")

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

                simplified_tools.append(tool_copy)
            simplified_request['tools'] = simplified_tools

        print(json.dumps(simplified_request, indent=2, ensure_ascii=False, default=str))

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
