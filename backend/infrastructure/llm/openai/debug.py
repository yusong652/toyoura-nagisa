"""
OpenAI Debug Utilities

Provides debugging and logging utilities for OpenAI client operations
including request/response logging and performance monitoring.
"""

import json
import pprint
from typing import Dict, Any, List


class OpenAIDebugger:
    """
    Debug utilities for OpenAI client operations
    
    Provides consistent debugging output for API calls, responses,
    and tool operations with proper formatting and truncation.
    """
    
    @staticmethod
    def log_api_call_info(tools_count: int, model: str) -> None:
        """
        Log basic API call information
        
        Args:
            tools_count: Number of tools available
            model: Model being used
        """
        print(f"[DEBUG] OpenAI API Call:")
        print(f"[DEBUG]   Model: {model}")
        print(f"[DEBUG]   Tools: {tools_count} available")
    
    @staticmethod
    def print_debug_request_payload(kwargs: Dict[str, Any]) -> None:
        """
        Print debug information for API request payload
        
        Args:
            kwargs: API call parameters
        """
        print("[DEBUG] OpenAI Request Payload:")
        
        # Print model and basic settings
        if 'model' in kwargs:
            print(f"[DEBUG]   Model: {kwargs['model']}")
        if 'temperature' in kwargs:
            print(f"[DEBUG]   Temperature: {kwargs['temperature']}")
        if 'max_tokens' in kwargs:
            print(f"[DEBUG]   Max Tokens: {kwargs['max_tokens']}")
        
        # Print message count
        if 'messages' in kwargs:
            print(f"[DEBUG]   Messages: {len(kwargs['messages'])}")
            
            # Show first few messages (truncated)
            for i, msg in enumerate(kwargs['messages'][:3]):
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                
                if isinstance(content, list):
                    content_preview = f"[{len(content)} content blocks]"
                else:
                    content_preview = str(content)[:100] + "..." if len(str(content)) > 100 else str(content)
                
                print(f"[DEBUG]     {i}: {role}: {content_preview}")
            
            if len(kwargs['messages']) > 3:
                print(f"[DEBUG]     ... and {len(kwargs['messages']) - 3} more messages")
        
        # Print tools info
        if 'tools' in kwargs and kwargs['tools']:
            print(f"[DEBUG]   Tools: {len(kwargs['tools'])}")
            for i, tool in enumerate(kwargs['tools'][:3]):
                if isinstance(tool, dict) and 'function' in tool:
                    name = tool['function'].get('name', 'unknown')
                    print(f"[DEBUG]     {i}: {name}")
            
            if len(kwargs['tools']) > 3:
                print(f"[DEBUG]     ... and {len(kwargs['tools']) - 3} more tools")
    
    @staticmethod
    def log_raw_response(response) -> None:
        """
        Log raw OpenAI API response (truncated for readability)
        
        Args:
            response: OpenAI API response object
        """
        print("[DEBUG] OpenAI Raw Response:")
        
        if hasattr(response, 'choices') and response.choices:
            choice = response.choices[0]
            print(f"[DEBUG]   Finish Reason: {getattr(choice, 'finish_reason', 'unknown')}")
            
            if hasattr(choice, 'message'):
                message = choice.message
                
                # Log content
                if hasattr(message, 'content') and message.content:
                    content_preview = message.content[:200] + "..." if len(message.content) > 200 else message.content
                    print(f"[DEBUG]   Content: {content_preview}")
                
                # Log tool calls
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    print(f"[DEBUG]   Tool Calls: {len(message.tool_calls)}")
                    for i, tool_call in enumerate(message.tool_calls):
                        name = tool_call.function.name if hasattr(tool_call, 'function') else 'unknown'
                        print(f"[DEBUG]     {i}: {name}")
        
        # Log usage if available
        if hasattr(response, 'usage'):
            usage = response.usage
            print(f"[DEBUG]   Usage:")
            if hasattr(usage, 'prompt_tokens'):
                print(f"[DEBUG]     Prompt tokens: {usage.prompt_tokens}")
            if hasattr(usage, 'completion_tokens'):
                print(f"[DEBUG]     Completion tokens: {usage.completion_tokens}")
            if hasattr(usage, 'total_tokens'):
                print(f"[DEBUG]     Total tokens: {usage.total_tokens}")
    
    @staticmethod
    def log_tool_execution(tool_name: str, tool_args: Dict[str, Any], execution_id: str) -> None:
        """
        Log tool execution details
        
        Args:
            tool_name: Name of the tool being executed
            tool_args: Tool arguments
            execution_id: Execution ID for tracking
        """
        print(f"[DEBUG] Tool Execution [{execution_id}]:")
        print(f"[DEBUG]   Tool: {tool_name}")
        
        if tool_args:
            print(f"[DEBUG]   Arguments:")
            for key, value in tool_args.items():
                value_preview = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                print(f"[DEBUG]     {key}: {value_preview}")
        else:
            print(f"[DEBUG]   Arguments: None")
    
    @staticmethod
    def log_tool_result(tool_name: str, result: Any, execution_id: str) -> None:
        """
        Log tool execution result
        
        Args:
            tool_name: Name of the executed tool
            result: Tool execution result
            execution_id: Execution ID for tracking
        """
        print(f"[DEBUG] Tool Result [{execution_id}]:")
        print(f"[DEBUG]   Tool: {tool_name}")
        
        if isinstance(result, dict):
            if 'is_error' in result and result['is_error']:
                print(f"[DEBUG]   Status: ERROR")
                print(f"[DEBUG]   Error: {result.get('content', 'Unknown error')}")
            else:
                print(f"[DEBUG]   Status: SUCCESS")
                # Show structured result preview
                if 'llm_content' in result:
                    content_preview = str(result['llm_content'])[:150] + "..." if len(str(result['llm_content'])) > 150 else str(result['llm_content'])
                    print(f"[DEBUG]   Content: {content_preview}")
                else:
                    result_preview = str(result)[:150] + "..." if len(str(result)) > 150 else str(result)
                    print(f"[DEBUG]   Result: {result_preview}")
        else:
            result_preview = str(result)[:150] + "..." if len(str(result)) > 150 else str(result)
            print(f"[DEBUG]   Result: {result_preview}")
    
    @staticmethod
    def log_context_state(context_manager) -> None:
        """
        Log current context manager state
        
        Args:
            context_manager: Context manager instance
        """
        if hasattr(context_manager, 'get_context_summary'):
            summary = context_manager.get_context_summary()
            print("[DEBUG] Context State:")
            for key, value in summary.items():
                print(f"[DEBUG]   {key}: {value}")
        else:
            print("[DEBUG] Context State: Not available")
    
    @staticmethod
    def print_formatted_dict(data: Dict[str, Any], title: str = "Debug Data") -> None:
        """
        Pretty print a dictionary for debugging
        
        Args:
            data: Dictionary to print
            title: Title for the debug output
        """
        print(f"[DEBUG] {title}:")
        pprint.pprint(data, indent=2, width=120)