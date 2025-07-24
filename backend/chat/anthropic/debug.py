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
    def log_api_payload(
        api_kwargs: Dict[str, Any],
        component: str = "ANTHROPIC",
        detailed: bool = True
    ) -> None:
        """
        Log detailed API call payload information.
        
        Args:
            api_kwargs: Complete API call parameters dictionary
            component: Component name for log prefix
            detailed: Whether to show detailed content information
        """
        print(f"\n[{component}] === API Request Payload ===")
        print(f"[{component}] Model: {api_kwargs.get('model', 'N/A')}")
        print(f"[{component}] Max Tokens: {api_kwargs.get('max_tokens', 'N/A')}")
        print(f"[{component}] Temperature: {api_kwargs.get('temperature', 'N/A')}")
        
        # System prompt
        system_prompt = api_kwargs.get('system', 'N/A')
        if isinstance(system_prompt, str) and len(system_prompt) > 200:
            print(f"[{component}] System: {system_prompt[:200]}...")
        else:
            print(f"[{component}] System: {system_prompt}")
        
        # Messages
        messages = api_kwargs.get('messages', [])
        print(f"[{component}] Messages count: {len(messages)}")
        
        if detailed:
            for i, msg in enumerate(messages):
                print(f"[{component}] Message {i+1}: role={msg.get('role', 'N/A')}")
                content = msg.get('content', [])
                
                if isinstance(content, list):
                    for j, content_block in enumerate(content):
                        if isinstance(content_block, dict):
                            content_type = content_block.get('type', 'unknown')
                            print(f"[{component}]   Content {j+1}: type={content_type}")
                            
                            if content_type == 'text':
                                text_content = content_block.get('text', '')
                                display_text = text_content[:150] + "..." if len(text_content) > 150 else text_content
                                print(f"[{component}]   Text: {display_text}")
                            elif content_type == 'tool_use':
                                tool_name = content_block.get('name', 'unknown')
                                tool_id = content_block.get('id', 'unknown')
                                print(f"[{component}]   Tool: {tool_name} (id: {tool_id})")
                            elif content_type == 'tool_result':
                                tool_id = content_block.get('tool_use_id', 'unknown')
                                is_error = content_block.get('is_error', False)
                                print(f"[{component}]   Tool Result: id={tool_id}, error={is_error}")
                elif isinstance(content, str):
                    display_text = content[:150] + "..." if len(content) > 150 else content
                    print(f"[{component}]   Content (string): {display_text}")
                else:
                    print(f"[{component}]   Content: {str(content)[:150]}...")
        
        # Tools
        if 'tools' in api_kwargs:
            tools = api_kwargs['tools']
            print(f"[{component}] Tools count: {len(tools)}")
            for i, tool in enumerate(tools):
                tool_name = tool.get('name', 'N/A')
                tool_type = tool.get('type', 'N/A')
                print(f"[{component}] Tool {i+1}: {tool_name} ({tool_type})")
                if 'max_uses' in tool:
                    print(f"[{component}]   Max uses: {tool['max_uses']}")
        
        # Thinking configuration
        if 'thinking' in api_kwargs:
            thinking_config = api_kwargs['thinking']
            print(f"[{component}] Thinking: {thinking_config}")
            if isinstance(thinking_config, dict):
                print(f"[{component}]   Type: {thinking_config.get('type', 'N/A')}")
                print(f"[{component}]   Budget tokens: {thinking_config.get('budget_tokens', 'N/A')}")
        
        print(f"[{component}] === End API Payload ===")

    @staticmethod
    def log_api_call_info(
        tools_count: int,
        model: str,
        thinking_enabled: bool = False,
        component: str = "AnthropicClient"
    ) -> None:
        """
        Log basic API call information before payload details.
        
        Args:
            tools_count: Number of tools available
            model: Model being used
            thinking_enabled: Whether thinking is enabled
            component: Component name for log prefix
        """
        print(f"[{component}] API call with {tools_count} tools")
        print(f"[{component}] Using model: {model}")
        if thinking_enabled:
            print(f"[{component}] Thinking enabled: {thinking_enabled}")

    @staticmethod
    def print_debug_request_payload(
        api_kwargs: Dict[str, Any],
        component: str = "ANTHROPIC"
    ) -> None:
        """
        Print simplified debug information for Anthropic API requests.
        
        Similar to Gemini's print_debug_request but adapted for Anthropic API format.
        
        Args:
            api_kwargs: Complete API call parameters dictionary
            component: Component name for log prefix
        """
        print(f"\n========== {component} API 请求消息格式 ==========")
        
        # Create debug-friendly version of the payload
        debug_payload = AnthropicDebugger._create_debug_payload(api_kwargs)
        
        # Censor large data fields for logging
        payload_to_print = AnthropicDebugger._censor_payload_for_logging(debug_payload)
        
        # Print simplified payload with truncated descriptions
        print("\n📝 Simplified Payload (truncated descriptions):")
        AnthropicDebugger._print_simplified_payload(payload_to_print)
        print("========== END ==========")

    @staticmethod
    def _create_debug_payload(api_kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a debug-friendly version of the API payload by truncating long fields.
        
        Args:
            api_kwargs: Complete API call parameters dictionary
            
        Returns:
            Debug-friendly payload dictionary with truncated long fields
        """
        debug_payload = {}
        
        for key, value in api_kwargs.items():
            if key == "system":
                # Truncate system prompt
                if isinstance(value, str):
                    debug_payload[key] = AnthropicDebugger._truncate_text_for_debug(
                        value, max_length=200, field_name="system_prompt"
                    )
                else:
                    debug_payload[key] = value
            elif key == "tools":
                # Process tools array to truncate descriptions  
                if isinstance(value, list):
                    debug_payload[key] = AnthropicDebugger._process_tools_for_debug(value)
                else:
                    debug_payload[key] = value
            elif key == "messages":
                # Process messages to truncate long content
                if isinstance(value, list):
                    debug_payload[key] = AnthropicDebugger._process_messages_for_debug(value)
                else:
                    debug_payload[key] = value
            else:
                # Keep other fields as-is
                debug_payload[key] = value
        
        return debug_payload

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

    @staticmethod
    def _process_tools_for_debug(tools: list) -> list:
        """
        Process tools array to truncate long descriptions for debug output.
        
        Args:
            tools: List of tool definitions
            
        Returns:
            Processed tools with truncated descriptions
        """
        processed_tools = []
        
        for tool in tools:
            if isinstance(tool, dict):
                processed_tool = tool.copy()
                
                # Truncate tool description
                if 'description' in processed_tool and isinstance(processed_tool['description'], str):
                    original_desc = processed_tool['description']
                    processed_tool['description'] = AnthropicDebugger._truncate_text_for_debug(
                        original_desc,
                        max_length=100,
                        field_name=f"tool '{tool.get('name', 'unknown')}' description"
                    )
                
                # Process input_schema if present
                if 'input_schema' in processed_tool and isinstance(processed_tool['input_schema'], dict):
                    processed_tool['input_schema'] = AnthropicDebugger._process_input_schema_for_debug(
                        processed_tool['input_schema']
                    )
                
                processed_tools.append(processed_tool)
            else:
                # If tool is not a dict, convert to string representation
                processed_tools.append(f"<{type(tool).__name__} object>")
        
        return processed_tools

    @staticmethod
    def _process_input_schema_for_debug(input_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process input_schema dict to truncate descriptions for debug output.
        
        Args:
            input_schema: Input schema dictionary from tool definition
            
        Returns:
            Processed input schema with truncated descriptions
        """
        # Only keep properties field from input_schema
        if 'properties' in input_schema and isinstance(input_schema['properties'], dict):
            processed_properties = {}
            
            for prop_name, prop_value in input_schema['properties'].items():
                if isinstance(prop_value, dict):
                    # Only keep description field for debug output
                    if 'description' in prop_value and isinstance(prop_value['description'], str):
                        original_desc = prop_value['description']
                        processed_properties[prop_name] = {
                            'description': AnthropicDebugger._truncate_text_for_debug(
                                original_desc,
                                max_length=80,
                                field_name=f"parameter '{prop_name}' description"
                            )
                        }
                    else:
                        # If no description, still create entry but with placeholder
                        processed_properties[prop_name] = {
                            'description': '<no description>'
                        }
                else:
                    # If property value is not a dict, keep as-is
                    processed_properties[prop_name] = prop_value
            
            return {'properties': processed_properties}
        else:
            # If no properties found, return empty properties
            return {'properties': {}}

    @staticmethod
    def _process_messages_for_debug(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process messages array to truncate long content for debug output.
        
        Args:
            messages: List of message dictionaries
            
        Returns:
            Processed messages with truncated content
        """
        processed_messages = []
        
        for msg in messages:
            if isinstance(msg, dict):
                processed_msg = msg.copy()
                
                # Process content field
                if 'content' in processed_msg:
                    content = processed_msg['content']
                    
                    if isinstance(content, list):
                        processed_content = []
                        for content_block in content:
                            if isinstance(content_block, dict):
                                processed_block = content_block.copy()
                                
                                # Truncate text content
                                if content_block.get('type') == 'text' and 'text' in content_block:
                                    text_content = content_block['text']
                                    if isinstance(text_content, str) and len(text_content) > 150:
                                        processed_block['text'] = AnthropicDebugger._truncate_text_for_debug(
                                            text_content,
                                            max_length=150,
                                            field_name="message text"
                                        )
                                
                                processed_content.append(processed_block)
                            else:
                                processed_content.append(content_block)
                        
                        processed_msg['content'] = processed_content
                    elif isinstance(content, str) and len(content) > 150:
                        processed_msg['content'] = AnthropicDebugger._truncate_text_for_debug(
                            content,
                            max_length=150,
                            field_name="message content"
                        )
                
                processed_messages.append(processed_msg)
            else:
                processed_messages.append(msg)
        
        return processed_messages

    @staticmethod
    def _truncate_text_for_debug(text: str, max_length: int = 100, field_name: str = "text") -> str:
        """
        Truncate text for debug output with informative truncation message.
        
        Args:
            text: Text to truncate
            max_length: Maximum length before truncation
            field_name: Descriptive name for the field being truncated
            
        Returns:
            Truncated text with truncation information
        """
        if len(text) <= max_length:
            # Still convert to single line even if no truncation needed
            return ' '.join(text.split())
        
        # Convert multiline to single line by replacing newlines with spaces
        single_line_text = ' '.join(text.split())
        
        # Extract key information from the beginning
        truncated = single_line_text[:max_length-20] + f"... [truncated {field_name}: {len(text)} chars total]"
        return truncated

    @staticmethod
    def _censor_payload_for_logging(payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a deep copy of the payload and censor large data fields for logging.
        
        Args:
            payload: Original payload dictionary
            
        Returns:
            Censored payload safe for logging
        """
        import copy
        censored_payload = copy.deepcopy(payload)
        
        if "messages" in censored_payload:
            for message in censored_payload.get("messages", []):
                if isinstance(message, dict) and "content" in message:
                    content = message.get("content", [])
                    if isinstance(content, list):
                        for content_block in content:
                            # Censor large inline data
                            if isinstance(content_block, dict) and 'data' in content_block:
                                data = content_block.get('data')
                                if isinstance(data, str) and len(data) > 200:
                                    content_block['data'] = f"{data[:100]}... [truncated {len(data)} chars]"
                            elif isinstance(content_block, dict) and 'source' in content_block:
                                source = content_block.get('source', {})
                                if isinstance(source, dict) and 'data' in source:
                                    data = source.get('data')
                                    if isinstance(data, str) and len(data) > 200:
                                        source['data'] = f"{data[:100]}... [truncated {len(data)} chars]"
        
        return censored_payload

    @staticmethod
    def _convert_object_to_dict(obj) -> Any:
        """
        Convert object to dictionary format for serialization.
        
        Args:
            obj: Object to convert
            
        Returns:
            Converted dictionary or original value
        """
        # If it's a basic type, return directly
        if obj is None or isinstance(obj, (str, int, float, bool, list, dict)):
            return obj
        
        # Try to convert to dictionary format
        try:
            result = {}
            
            # Extract valid attributes from the object
            for attr in dir(obj):
                if (not attr.startswith('_') and 
                    not attr.startswith('model_') and
                    not callable(getattr(obj, attr))):
                    try:
                        value = getattr(obj, attr)
                        if value is not None:
                            # Recursively process nested objects
                            if isinstance(value, list):
                                result[attr] = [AnthropicDebugger._convert_object_to_dict(item) for item in value]
                            elif hasattr(value, '__dict__') or hasattr(value, '__slots__'):
                                result[attr] = AnthropicDebugger._convert_object_to_dict(value)
                            else:
                                result[attr] = value
                    except Exception:
                        # Skip attributes that can't be accessed
                        pass
            
            return result if result else str(obj)
            
        except Exception:
            # If conversion fails, return string representation
            return str(obj)

    @staticmethod
    def _print_simplified_payload(payload: Dict[str, Any]) -> None:
        """
        Print simplified payload using JSON format for better readability.
        
        Args:
            payload: Payload dictionary to print
        """
        # Final cleanup to ensure no long fields are missed
        def final_cleanup(obj):
            """Final cleanup to ensure no long fields are missed and unified object format"""
            if isinstance(obj, dict):
                result = {}
                for key, value in obj.items():
                    if isinstance(value, str) and len(value) > 300:
                        # Final truncation for any remaining long strings
                        result[key] = AnthropicDebugger._truncate_text_for_debug(
                            value, max_length=100, field_name=f"field '{key}'"
                        )
                    elif isinstance(value, (dict, list)):
                        result[key] = final_cleanup(value)
                    else:
                        result[key] = value
                return result
            elif isinstance(obj, list):
                return [final_cleanup(item) for item in obj]
            else:
                # Convert object to dictionary format to avoid mixed serialization issues
                return AnthropicDebugger._convert_object_to_dict(obj)
        
        cleaned_payload = final_cleanup(payload)
        
        # Use JSON dumps instead of pprint to ensure single-line display for description fields
        try:
            # Use indent=2 for beautiful formatting but avoid pprint's automatic text wrapping
            json_output = json.dumps(cleaned_payload, indent=2, ensure_ascii=False, default=str)
            print(json_output)
        except (TypeError, ValueError) as e:
            # If JSON serialization fails, fall back to basic string representation
            print(f"Debug payload (JSON serialization failed: {e}):")
            print(str(cleaned_payload))