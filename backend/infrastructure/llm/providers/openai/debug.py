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
    def print_full_system_prompt(system_prompt: str) -> None:
        """
        Print the complete system prompt for debugging purposes.
        
        This method displays the full system prompt without truncation,
        allowing developers to verify the exact prompt being sent to OpenAI models.
        
        Args:
            system_prompt: Complete system prompt text
        """
        print("\n" + "=" * 80)
        print("🔍 OPENAI FULL SYSTEM PROMPT (DEBUG MODE)")
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
    def log_api_call_info(tools_count: int, model: str) -> None:
        """
        Log basic API call information with improved formatting
        
        Args:
            tools_count: Number of tools available
            model: Model being used
        """
        print("\n========== OpenAI API 请求信息 ==========")
        print(f"🤖 Model: {model}")
        print(f"🔧 Tools Available: {tools_count}")
        if tools_count > 0:
            print("⚡ Tool calling enabled")
    
    @staticmethod
    def print_debug_request_payload(kwargs: Dict[str, Any]) -> None:
        """
        Print formatted debug information for OpenAI API request payload
        
        Args:
            kwargs: API call parameters
        """
        print("\n📝 OpenAI API Request Payload (simplified):")
        
        # Create simplified payload for better debugging
        simplified_payload = OpenAIDebugger._create_simplified_payload(kwargs)
        
        try:
            import json
            json_output = json.dumps(simplified_payload, indent=2, ensure_ascii=False, default=str)
            print(json_output)
        except (TypeError, ValueError) as e:
            print(f"Debug payload (JSON serialization failed: {e}):")
            print(str(simplified_payload))
        
        print("========== END ==========")
    
    @staticmethod
    def _create_simplified_payload(kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create simplified payload for debug output
        
        Args:
            kwargs: Original API call parameters
            
        Returns:
            Simplified payload dictionary
        """
        simplified = {}
        
        # Basic API settings
        if 'model' in kwargs:
            simplified['model'] = kwargs['model']
        if 'temperature' in kwargs:
            simplified['temperature'] = kwargs['temperature']
        if 'max_tokens' in kwargs:
            simplified['max_tokens'] = kwargs['max_tokens']
        if 'top_p' in kwargs:
            simplified['top_p'] = kwargs['top_p']
        
        # Messages with content truncation
        if 'messages' in kwargs:
            simplified['messages'] = []
            for i, msg in enumerate(kwargs['messages']):
                simplified_msg = {
                    'role': msg.get('role', 'unknown')
                }
                
                content = msg.get('content', '')
                if isinstance(content, str):
                    # Truncate long text content
                    if len(content) > 200:
                        simplified_msg['content'] = content[:200] + "... [truncated]"
                    else:
                        simplified_msg['content'] = content
                elif isinstance(content, list):
                    # Handle multimodal content - show structure
                    content_summary = []
                    for block in content:
                        if isinstance(block, dict):
                            block_type = block.get('type', 'unknown')
                            if block_type == 'text':
                                text = block.get('text', '')
                                if len(text) > 50:
                                    content_summary.append(f"text: {text[:50]}...")
                                else:
                                    content_summary.append(f"text: {text}")
                            elif block_type == 'image_url':
                                url = block.get('image_url', {}).get('url', '')
                                if url.startswith('data:'):
                                    mime_type = url.split(';')[0].replace('data:', '')
                                    content_summary.append(f"image: {mime_type}")
                                else:
                                    content_summary.append("image: external_url")
                            else:
                                content_summary.append(f"{block_type}: [data]")
                        else:
                            content_summary.append(f"raw: {str(block)[:30]}...")
                    
                    simplified_msg['content'] = content_summary
                else:
                    simplified_msg['content'] = str(content)[:100] + "..." if len(str(content)) > 100 else str(content)
                
                # Add tool calls if present
                if 'tool_calls' in msg and msg['tool_calls']:
                    simplified_msg['tool_calls'] = []
                    for tool_call in msg['tool_calls']:
                        simplified_tool = {
                            'id': tool_call.get('id', 'unknown'),
                            'type': tool_call.get('type', 'unknown'),
                            'function': {
                                'name': tool_call.get('function', {}).get('name', 'unknown'),
                                'arguments': '... [truncated]'
                            }
                        }
                        simplified_msg['tool_calls'].append(simplified_tool)
                
                # Add tool_call_id for tool messages
                if 'tool_call_id' in msg:
                    simplified_msg['tool_call_id'] = msg['tool_call_id']
                
                simplified['messages'].append(simplified_msg)
        
        # Tools with truncated descriptions
        if 'tools' in kwargs and kwargs['tools']:
            simplified['tools'] = []
            for tool in kwargs['tools']:
                if isinstance(tool, dict) and 'function' in tool:
                    func = tool['function']
                    simplified_tool = {
                        'type': tool.get('type', 'function'),
                        'function': {
                            'name': func.get('name', 'unknown'),
                            'description': OpenAIDebugger._truncate_text(
                                func.get('description', ''), 100, 'tool description'
                            )
                        }
                    }
                    
                    # Add simplified parameters info
                    if 'parameters' in func:
                        params = func['parameters']
                        if isinstance(params, dict) and 'properties' in params:
                            prop_count = len(params['properties'])
                            simplified_tool['function']['parameters'] = f"[{prop_count} parameters]"
                        else:
                            simplified_tool['function']['parameters'] = str(params)[:50] + "..."
                    
                    simplified['tools'].append(simplified_tool)
        
        return simplified
    
    @staticmethod
    def _truncate_text(text: str, max_length: int = 100, field_name: str = "text") -> str:
        """
        Truncate text for debug output with informative message
        
        Args:
            text: Text to truncate
            max_length: Maximum length before truncation
            field_name: Descriptive name for the field
            
        Returns:
            Truncated text with informative suffix
        """
        if not isinstance(text, str):
            text = str(text)
        
        if len(text) <= max_length:
            return text
        
        return f"{text[:max_length]}... [truncated {field_name}]"
    
    @staticmethod
    def log_raw_response(response) -> None:
        """
        Log formatted OpenAI API response with improved formatting
        
        Args:
            response: OpenAI API response object
        """
        print("\n========== OpenAI API Response ==========")
        print(f"📤 Response type: {type(response).__name__}")
        
        # Check for choices and process them
        if hasattr(response, 'choices') and response.choices:
            print(f"📋 Choices: {len(response.choices)}")
            
            for i, choice in enumerate(response.choices):
                print(f"  Choice {i+1}:")
                
                # Finish reason
                finish_reason = getattr(choice, 'finish_reason', 'unknown')
                finish_emoji = "✅" if finish_reason == "stop" else "🔧" if finish_reason == "tool_calls" else "⚠️"
                print(f"    {finish_emoji} Finish Reason: {finish_reason}")
                
                # Message content
                if hasattr(choice, 'message'):
                    message = choice.message
                    
                    # Content
                    if hasattr(message, 'content') and message.content:
                        content = message.content
                        if len(content) > 300:
                            content_preview = content[:300] + "... [truncated response content]"
                        else:
                            content_preview = content
                        print(f"    💭 Content: {content_preview}")
                    
                    # Tool calls
                    if hasattr(message, 'tool_calls') and message.tool_calls:
                        print(f"    ⚡ Tool Calls: {len(message.tool_calls)}")
                        for j, tool_call in enumerate(message.tool_calls):
                            if hasattr(tool_call, 'function'):
                                func_name = tool_call.function.name
                                tool_id = getattr(tool_call, 'id', 'unknown')
                                print(f"      {j+1}. {func_name} (id: {tool_id[:8]}...)")
                            else:
                                print(f"      {j+1}. Unknown tool call")
        else:
            print("❌ No choices in response")
        
        # Usage statistics
        if hasattr(response, 'usage') and response.usage:
            usage = response.usage
            print(f"📊 Token Usage:")
            if hasattr(usage, 'prompt_tokens'):
                print(f"    📝 Prompt: {usage.prompt_tokens}")
            if hasattr(usage, 'completion_tokens'):
                print(f"    🤖 Completion: {usage.completion_tokens}")
            if hasattr(usage, 'total_tokens'):
                print(f"    📈 Total: {usage.total_tokens}")
        
        print("========== END ==========")
    
    @staticmethod
    def log_tool_execution(tool_name: str, tool_args: Dict[str, Any], execution_id: str) -> None:
        """
        Log tool execution details with improved formatting
        
        Args:
            tool_name: Name of the tool being executed
            tool_args: Tool arguments
            execution_id: Execution ID for tracking
        """
        print(f"\n🔧 Tool Execution [{execution_id[:8]}...] 🔧")
        print(f"⚡ Tool: {tool_name}")
        
        if tool_args:
            print("📋 Arguments:")
            for key, value in tool_args.items():
                if isinstance(value, str) and len(value) > 150:
                    value_preview = f"{value[:150]}... [truncated argument]"
                elif isinstance(value, (dict, list)):
                    value_preview = f"[{type(value).__name__} with {len(value)} items]"
                else:
                    value_preview = str(value)
                print(f"  • {key}: {value_preview}")
        else:
            print("📋 Arguments: None")
        print("─" * 50)
    
    @staticmethod
    def log_tool_result(tool_name: str, result: Any, execution_id: str) -> None:
        """
        Log tool execution result with improved formatting
        
        Args:
            tool_name: Name of the executed tool
            result: Tool execution result
            execution_id: Execution ID for tracking
        """
        print(f"\n✨ Tool Result [{execution_id[:8]}...] ✨")
        print(f"⚡ Tool: {tool_name}")
        
        if isinstance(result, dict):
            # Check for error status
            if 'is_error' in result and result['is_error']:
                print("❌ Status: ERROR")
                error_msg = result.get('content', result.get('error', 'Unknown error'))
                print(f"🚫 Error: {error_msg}")
            elif 'status' in result and result['status'] == 'error':
                print("❌ Status: ERROR")
                error_msg = result.get('message', result.get('error', 'Unknown error'))
                print(f"🚫 Error: {error_msg}")
            else:
                print("✅ Status: SUCCESS")
                
                # Show structured result preview
                if 'llm_content' in result:
                    content = result['llm_content']
                    if isinstance(content, str) and len(content) > 200:
                        content_preview = f"{content[:200]}... [truncated tool result]"
                    else:
                        content_preview = str(content)
                    print(f"📄 Content: {content_preview}")
                
                if 'message' in result:
                    message = result['message']
                    if isinstance(message, str) and len(message) > 150:
                        message_preview = f"{message[:150]}... [truncated message]"
                    else:
                        message_preview = str(message)
                    print(f"💬 Message: {message_preview}")
                
                # Show additional data if present
                if 'data' in result and result['data']:
                    data = result['data']
                    if isinstance(data, dict):
                        print(f"📊 Data: [{len(data)} fields]")
                    elif isinstance(data, list):
                        print(f"📊 Data: [{len(data)} items]")
                    else:
                        data_preview = str(data)[:100] + "..." if len(str(data)) > 100 else str(data)
                        print(f"📊 Data: {data_preview}")
        else:
            # Handle non-dict results
            if isinstance(result, str) and len(result) > 200:
                result_preview = f"{result[:200]}... [truncated result]"
            else:
                result_preview = str(result)
            print(f"📄 Result: {result_preview}")
        
        print("─" * 50)
    
    @staticmethod
    def log_context_state(context_manager) -> None:
        """
        Log current context manager state with improved formatting
        
        Args:
            context_manager: Context manager instance
        """
        print("\n🧠 Context Manager State 🧠")
        
        if hasattr(context_manager, 'get_context_summary'):
            summary = context_manager.get_context_summary()
            for key, value in summary.items():
                print(f"📋 {key}: {value}")
        elif hasattr(context_manager, 'get_working_contents'):
            # Fallback: show basic working contents info
            contents = context_manager.get_working_contents()
            if isinstance(contents, list):
                print(f"📋 Working Messages: {len(contents)}")
                for i, msg in enumerate(contents[-3:]):  # Show last 3 messages
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')
                    if isinstance(content, str):
                        preview = content[:50] + "..." if len(content) > 50 else content
                    else:
                        preview = f"[{type(content).__name__}]"
                    print(f"  {i+1}. {role}: {preview}")
            else:
                print(f"📋 Working Contents: {type(contents).__name__}")
        else:
            print("❓ Context State: Not available")
        
        print("─" * 40)
    
    @staticmethod
    def print_formatted_dict(data: Dict[str, Any], title: str = "Debug Data") -> None:
        """
        Pretty print a dictionary for debugging with improved formatting
        
        Args:
            data: Dictionary to print
            title: Title for the debug output
        """
        print(f"\n📊 {title} 📊")
        
        try:
            import json
            # Try JSON formatting first for better readability
            json_output = json.dumps(data, indent=2, ensure_ascii=False, default=str)
            print(json_output)
        except (TypeError, ValueError):
            # Fallback to pprint if JSON serialization fails
            pprint.pprint(data, indent=2, width=120)
        
        print("─" * 50)