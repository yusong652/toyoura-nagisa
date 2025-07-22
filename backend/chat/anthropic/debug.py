"""
Debug utilities for Anthropic Claude API interactions.

Provides debugging and logging capabilities for Claude API calls,
response analysis, and performance monitoring.
"""

import json
import time
from typing import Any, Dict, List, Optional
from datetime import datetime


class AnthropicDebugger:
    """
    Debug utilities for Anthropic Claude API interactions.
    
    Provides structured debugging output, request/response logging,
    and performance monitoring for Claude API calls.
    """

    @staticmethod
    def log_api_request(
        model: str,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """
        Log details of an API request to Claude.
        
        Args:
            model: Model name being used
            messages: Messages being sent
            system_prompt: System prompt if any
            max_tokens: Maximum tokens setting
            temperature: Temperature setting
            tools: Tools available for the request
        """
        print(f"\n[ANTHROPIC DEBUG] API Request at {datetime.now().isoformat()}")
        print(f"[ANTHROPIC DEBUG] Model: {model}")
        print(f"[ANTHROPIC DEBUG] Max Tokens: {max_tokens}")
        print(f"[ANTHROPIC DEBUG] Temperature: {temperature}")
        
        if system_prompt:
            print(f"[ANTHROPIC DEBUG] System Prompt: {system_prompt[:100]}...")
        
        print(f"[ANTHROPIC DEBUG] Message Count: {len(messages)}")
        for i, msg in enumerate(messages):
            role = msg.get('role', 'unknown')
            content = msg.get('content', [])
            if isinstance(content, list):
                content_types = [item.get('type', 'unknown') for item in content]
                print(f"[ANTHROPIC DEBUG] Message {i+1}: {role} - {content_types}")
            else:
                print(f"[ANTHROPIC DEBUG] Message {i+1}: {role} - {type(content)}")
        
        if tools:
            print(f"[ANTHROPIC DEBUG] Tools Available: {len(tools)}")
            for tool in tools:
                tool_name = tool.get('name', 'unknown')
                print(f"[ANTHROPIC DEBUG]   - {tool_name}")

    @staticmethod
    def log_api_response(
        response: Any,
        duration_ms: Optional[float] = None
    ) -> None:
        """
        Log details of an API response from Claude.
        
        Args:
            response: Raw response from Claude API
            duration_ms: Request duration in milliseconds
        """
        print(f"\n[ANTHROPIC DEBUG] API Response at {datetime.now().isoformat()}")
        
        if duration_ms is not None:
            print(f"[ANTHROPIC DEBUG] Duration: {duration_ms:.2f}ms")
        
        if hasattr(response, 'usage'):
            usage = response.usage
            print(f"[ANTHROPIC DEBUG] Token Usage:")
            print(f"[ANTHROPIC DEBUG]   Input Tokens: {getattr(usage, 'input_tokens', 'N/A')}")
            print(f"[ANTHROPIC DEBUG]   Output Tokens: {getattr(usage, 'output_tokens', 'N/A')}")
        
        if hasattr(response, 'model'):
            print(f"[ANTHROPIC DEBUG] Model Used: {response.model}")
        
        if hasattr(response, 'content') and response.content:
            print(f"[ANTHROPIC DEBUG] Content Blocks: {len(response.content)}")
            for i, block in enumerate(response.content):
                block_type = getattr(block, 'type', 'unknown')
                if block_type == 'text':
                    text_length = len(getattr(block, 'text', ''))
                    print(f"[ANTHROPIC DEBUG]   Block {i+1}: text ({text_length} chars)")
                elif block_type == 'tool_use':
                    tool_name = getattr(block, 'name', 'unknown')
                    tool_id = getattr(block, 'id', 'unknown')
                    print(f"[ANTHROPIC DEBUG]   Block {i+1}: tool_use ({tool_name}, id: {tool_id})")
                else:
                    print(f"[ANTHROPIC DEBUG]   Block {i+1}: {block_type}")
        
        if hasattr(response, 'stop_reason'):
            print(f"[ANTHROPIC DEBUG] Stop Reason: {response.stop_reason}")

    @staticmethod
    def log_tool_execution(
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_result: Any,
        duration_ms: Optional[float] = None,
        is_error: bool = False
    ) -> None:
        """
        Log details of tool execution.
        
        Args:
            tool_name: Name of the executed tool
            tool_input: Input parameters passed to the tool
            tool_result: Result returned by the tool
            duration_ms: Execution duration in milliseconds
            is_error: Whether the execution resulted in an error
        """
        status = "ERROR" if is_error else "SUCCESS"
        print(f"\n[ANTHROPIC DEBUG] Tool Execution: {tool_name} - {status}")
        
        if duration_ms is not None:
            print(f"[ANTHROPIC DEBUG] Duration: {duration_ms:.2f}ms")
        
        print(f"[ANTHROPIC DEBUG] Input:")
        for key, value in tool_input.items():
            if isinstance(value, str) and len(value) > 100:
                print(f"[ANTHROPIC DEBUG]   {key}: {value[:100]}...")
            else:
                print(f"[ANTHROPIC DEBUG]   {key}: {value}")
        
        print(f"[ANTHROPIC DEBUG] Result Type: {type(tool_result)}")
        if isinstance(tool_result, str):
            if len(tool_result) > 200:
                print(f"[ANTHROPIC DEBUG] Result: {tool_result[:200]}...")
            else:
                print(f"[ANTHROPIC DEBUG] Result: {tool_result}")
        elif isinstance(tool_result, (dict, list)):
            try:
                result_str = json.dumps(tool_result, ensure_ascii=False, indent=2)
                if len(result_str) > 500:
                    print(f"[ANTHROPIC DEBUG] Result: {result_str[:500]}...")
                else:
                    print(f"[ANTHROPIC DEBUG] Result: {result_str}")
            except:
                print(f"[ANTHROPIC DEBUG] Result: {str(tool_result)[:200]}...")

    @staticmethod
    def log_message_formatting(
        original_messages: List[Any],
        formatted_messages: List[Dict[str, Any]]
    ) -> None:
        """
        Log message formatting process.
        
        Args:
            original_messages: Original internal message format
            formatted_messages: Formatted messages for Claude API
        """
        print(f"\n[ANTHROPIC DEBUG] Message Formatting")
        print(f"[ANTHROPIC DEBUG] Original Messages: {len(original_messages)}")
        print(f"[ANTHROPIC DEBUG] Formatted Messages: {len(formatted_messages)}")
        
        for i, (orig, formatted) in enumerate(zip(original_messages, formatted_messages)):
            orig_role = getattr(orig, 'role', 'unknown')
            formatted_role = formatted.get('role', 'unknown')
            content_count = len(formatted.get('content', []))
            
            print(f"[ANTHROPIC DEBUG] Message {i+1}: {orig_role} -> {formatted_role} ({content_count} content blocks)")

    @staticmethod
    def log_session_info(
        session_id: Optional[str],
        message_count: int,
        tools_enabled: bool,
        tool_cache_size: int = 0
    ) -> None:
        """
        Log session information.
        
        Args:
            session_id: Current session ID
            message_count: Number of messages in session
            tools_enabled: Whether tools are enabled
            tool_cache_size: Size of tool cache
        """
        print(f"\n[ANTHROPIC DEBUG] Session Info")
        print(f"[ANTHROPIC DEBUG] Session ID: {session_id or 'None'}")
        print(f"[ANTHROPIC DEBUG] Messages: {message_count}")
        print(f"[ANTHROPIC DEBUG] Tools Enabled: {tools_enabled}")
        if tool_cache_size > 0:
            print(f"[ANTHROPIC DEBUG] Tool Cache Size: {tool_cache_size}")

    @staticmethod
    def measure_time(func_name: str):
        """
        Context manager for measuring execution time.
        
        Args:
            func_name: Name of the function being measured
            
        Usage:
            with AnthropicDebugger.measure_time("api_call"):
                # ... code to measure
        """
        class TimeContext:
            def __init__(self, name):
                self.name = name
                self.start_time = None
            
            def __enter__(self):
                self.start_time = time.time()
                print(f"[ANTHROPIC DEBUG] Starting {self.name}")
                return self
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                duration_ms = (time.time() - self.start_time) * 1000
                print(f"[ANTHROPIC DEBUG] Completed {self.name} in {duration_ms:.2f}ms")
        
        return TimeContext(func_name)

    @staticmethod
    def format_exception(e: Exception) -> str:
        """
        Format exception for debug output.
        
        Args:
            e: Exception to format
            
        Returns:
            Formatted exception string
        """
        import traceback
        
        return f"""
[ANTHROPIC DEBUG] Exception: {type(e).__name__}: {str(e)}
[ANTHROPIC DEBUG] Traceback:
{traceback.format_exc()}
"""