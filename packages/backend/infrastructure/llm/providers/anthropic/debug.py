"""
Debug utilities for Anthropic Claude API interactions.

Provides debugging and logging capabilities for Claude API calls,
response analysis, and performance monitoring.
"""

import json
from typing import Any, Dict, List, Optional


class AnthropicDebugger:
    """
    Debug utilities for Anthropic Claude API interactions.
    
    Provides structured debugging output, request/response logging,
    and performance monitoring for Claude API calls.
    """

    @staticmethod
    def print_full_system_prompt(system_prompt: str) -> None:
        """
        Print the complete system prompt for debugging purposes.
        
        This method displays the full system prompt without truncation,
        allowing developers to verify the exact prompt being sent to Claude.
        
        Args:
            system_prompt: Complete system prompt text
        """
        print("\n" + "=" * 80)
        print("🔍 ANTHROPIC FULL SYSTEM PROMPT (DEBUG MODE)")
        print("=" * 80)
        
        if system_prompt:
            # Display basic statistics
            print(f"📊 System Prompt Statistics:")
            print(f"   - Total Length: {len(system_prompt)} characters")
            print(f"   - Lines Count: {system_prompt.count(chr(10)) + 1} lines")
            print(f"   - Words Count: {len(system_prompt.split())} words")
            print()
            print("📜 Complete System Prompt:")
            print("-" * 80)
            print(system_prompt)
            print("-" * 80)
        else:
            print("⚠️ No system prompt provided")
        
        print("=" * 80)
        print("END OF SYSTEM PROMPT")
        print("=" * 80 + "\n")
    
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
        
        # Add message format validation
        AnthropicDebugger._validate_message_format(messages, component)
        
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
        print(f"\n========== {component} API Request Message Format ==========")
        
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
    def log_raw_response(response: Any, component: str = "ANTHROPIC") -> None:
        """
        Log the complete raw API response from Claude.
        
        Args:
            response: Raw response from Claude API
            component: Component name for log prefix
        """
        print(f"\n========== {component} RAW RESPONSE ==========")
        
        # Convert response to dictionary format for better readability
        try:
            if hasattr(response, 'model_dump'):
                # Pydantic object with model_dump method
                response_dict = response.model_dump()
            elif hasattr(response, '__dict__'):
                # Regular object with attributes
                response_dict = AnthropicDebugger._convert_object_to_dict(response)
            else:
                response_dict = str(response)
            
            # Print the raw response in JSON format
            print("📄 Complete Raw Response:")
            if isinstance(response_dict, dict):
                json_output = json.dumps(response_dict, indent=2, ensure_ascii=False, default=str)
                print(json_output)
            else:
                print(response_dict)
                
        except Exception as e:
            print(f"Failed to serialize raw response: {e}")
            print(f"Raw response object: {response}")
            
        print("========== END RAW RESPONSE ==========\n")


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

    @staticmethod
    def _validate_message_format(messages: List[Dict[str, Any]], component: str = "ANTHROPIC") -> None:
        """
        Validate message format for Anthropic API compatibility.
        
        Args:
            messages: List of message dictionaries
            component: Component name for log prefix
        """
        print(f"[{component}] === Message Format Validation ===")
        
        tool_use_ids = set()
        tool_result_ids = set()
        
        for i, msg in enumerate(messages):
            role = msg.get('role', 'unknown')
            content = msg.get('content', [])
            
            if not isinstance(content, list):
                print(f"[{component}] WARNING: Message {i+1} content is not a list: {type(content)}")
                continue
            
            for j, content_block in enumerate(content):
                if not isinstance(content_block, dict):
                    print(f"[{component}] WARNING: Message {i+1} content block {j+1} is not a dict: {type(content_block)}")
                    continue
                
                content_type = content_block.get('type', 'unknown')
                
                if content_type == 'tool_use':
                    tool_id = content_block.get('id', 'unknown')
                    tool_name = content_block.get('name', 'unknown')
                    tool_use_ids.add(tool_id)
                    print(f"[{component}] Found tool_use: {tool_name} (id: {tool_id})")
                    
                elif content_type == 'tool_result':
                    tool_id = content_block.get('tool_use_id', 'unknown')
                    tool_result_ids.add(tool_id)
                    is_error = content_block.get('is_error', False)
                    print(f"[{component}] Found tool_result: id={tool_id}, error={is_error}")
        
        # Check for matching tool calls and results
        missing_results = tool_use_ids - tool_result_ids
        extra_results = tool_result_ids - tool_use_ids
        
        if missing_results:
            print(f"[{component}] ERROR: Missing tool_result for tool_use IDs: {missing_results}")
        
        if extra_results:
            print(f"[{component}] WARNING: Extra tool_result for non-existent tool_use IDs: {extra_results}")
        
        if not missing_results and not extra_results:
            print(f"[{component}] ✓ Message format validation passed")
        
        print(f"[{component}] === End Validation ===")
