"""
OpenAI Debug Utilities

Provides debugging and logging utilities for OpenAI client operations
including request/response logging and performance monitoring.
"""

import json
import pprint
from typing import Dict, Any, List
from openai.types.responses import (
    Response,
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseReasoningItem,
)
from openai.types.responses.response_output_text import ResponseOutputText


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
        print("\n========== OpenAI API Request Info ==========")
        print(f"🤖 Model: {model}")
        print(f"🔧 Tools Available: {tools_count}")
        if tools_count > 0:
            print("⚡ Tool calling enabled")
    
    @staticmethod
    def print_debug_request_payload(kwargs: Dict[str, Any]) -> None:
        """
        Print formatted debug information for OpenAI API request payload

        Similar to Zhipu debug output: displays request with simplified verbose fields
        (system prompt and tool schemas are truncated for readability)

        Args:
            kwargs: API call parameters
        """
        print("\n" + "=" * 80)
        print("[DEBUG] OpenAI API Request")
        print("=" * 80)

        # Basic parameters
        print(f"\nModel: {kwargs.get('model', 'N/A')}")
        print(f"Temperature: {kwargs.get('temperature', 'N/A')}")
        print(f"Top P: {kwargs.get('top_p', 'N/A')}")
        print(f"Max Output Tokens: {kwargs.get('max_output_tokens', 'N/A')}")

        # Modalities (if present)
        modalities = kwargs.get('modalities')
        if modalities:
            print(f"Modalities: {modalities}")

        # API Request (with simplified verbose fields)
        print("\n" + "=" * 80)
        print("--- API Request (Original Format, Simplified Verbose Fields) ---")
        print("=" * 80)

        # Create simplified payload for better debugging
        simplified_payload = OpenAIDebugger._create_simplified_payload(kwargs)

        print(json.dumps(simplified_payload, indent=2, ensure_ascii=False, default=str))

        print("=" * 80 + "\n")
    
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
        if 'max_output_tokens' in kwargs:
            simplified['max_output_tokens'] = kwargs['max_output_tokens']
        if 'top_p' in kwargs:
            simplified['top_p'] = kwargs['top_p']
        
        # Instructions (system prompt) - truncate like Zhipu
        if kwargs.get('instructions'):
            instructions = kwargs['instructions']
            if len(instructions) > 150:
                simplified['instructions'] = instructions[:150] + f"... (truncated, {len(instructions)} chars total)"
            else:
                simplified['instructions'] = instructions

        # Responses API input items
        if 'input' in kwargs:
            simplified['input'] = []
            for item in kwargs['input']:
                if not isinstance(item, dict):
                    simplified['input'].append(str(item))
                    continue

                # Only include type if it actually exists in the item
                item_type = item.get('type')
                if item_type:
                    summary = {'type': item_type}
                else:
                    summary = {}

                if item_type is None and 'role' in item:
                    # Regular message without type field
                    summary['role'] = item.get('role')
                    # Show actual content type and value, not misleading summary
                    content = item.get('content')
                    if isinstance(content, str):
                        summary['content'] = f"(string) {OpenAIDebugger._truncate_text(content, 80, 'text')}"
                    elif isinstance(content, list):
                        summary['content'] = f"(array[{len(content)}]) {content}"
                    else:
                        summary['content'] = f"({type(content).__name__}) {content}"
                elif item_type == 'reasoning':
                    # Show reasoning details
                    summary['id'] = item.get('id')
                    summary_content = item.get('summary', [])
                    if summary_content:
                        # Extract text from summary
                        summary_texts = []
                        for s in summary_content:
                            if isinstance(s, dict) and s.get('type') == 'summary_text':
                                summary_texts.append(s.get('text', ''))
                        if summary_texts:
                            combined = ' '.join(summary_texts)
                            summary['summary'] = OpenAIDebugger._truncate_text(combined, 100, 'reasoning')
                        else:
                            summary['summary'] = f"(array[{len(summary_content)}])"
                    else:
                        summary['summary'] = "[]"
                elif item_type == 'function_call':
                    summary['name'] = item.get('name')
                    # Show both id and call_id if present
                    if 'id' in item:
                        summary['id'] = item.get('id')
                    summary['call_id'] = item.get('call_id')
                    # Show arguments to verify it exists
                    if 'arguments' in item:
                        args_preview = str(item['arguments'])[:100]
                        summary['arguments'] = f"(present) {args_preview}..."
                    else:
                        summary['arguments'] = "❌ MISSING"
                elif item_type == 'function_call_output':
                    summary['call_id'] = item.get('call_id')
                    summary['output_preview'] = OpenAIDebugger._truncate_text(
                        item.get('output', ''), 120, 'tool output'
                    )
                else:
                    # Fallback for unknown types
                    summary['data'] = str(item)[:80] + ("..." if len(str(item)) > 80 else "")

                simplified['input'].append(summary)
        
        # Tools - simplified like Zhipu (keep structure but remove verbose details)
        if 'tools' in kwargs and kwargs['tools']:
            simplified['tools'] = []
            for tool in kwargs['tools']:
                if not isinstance(tool, dict):
                    continue

                tool_copy = {
                    'type': tool.get('type', 'function')
                }

                # Handle function-based tools
                if 'function' in tool:
                    func = tool['function']
                    tool_copy['function'] = {
                        'name': func.get('name', 'unknown')
                    }

                    # Add description if short, truncate if long
                    desc = func.get('description', '')
                    if desc and len(desc) <= 100:
                        tool_copy['function']['description'] = desc
                    elif desc:
                        tool_copy['function']['description'] = desc[:100] + "... (truncated)"

                    # Simplify parameters - show count and required fields only
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

                simplified['tools'].append(tool_copy)
        
        return simplified
    
    @staticmethod
    def _summarize_input_content(content: Any, is_assistant: bool = False) -> List[str]:
        """Summarize Responses API message content items for debugging."""
        if not content:
            return []

        summary: List[str] = []
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    part_type = part.get('type')
                    if part_type == 'input_text':
                        text = part.get('text', '')
                        summary.append(OpenAIDebugger._truncate_text(text, 80, 'text'))
                    elif part_type == 'input_image':
                        summary.append("image:input_image")
                    elif part_type == 'input_file':
                        summary.append("file:input_file")
                    elif part_type == 'output_text' and is_assistant:
                        text = part.get('text', '')
                        summary.append(OpenAIDebugger._truncate_text(text, 80, 'assistant'))
                    else:
                        summary.append(f"{part_type}:item")
                else:
                    summary.append(str(part))
        else:
            summary.append(OpenAIDebugger._truncate_text(str(content), 80, 'text'))
        return summary
    
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
        
        # Responses API structured output
        if isinstance(response, Response):
            output = response.output or []
            print(f"📦 Output items: {len(output)}")
            for item in output:
                item_type = getattr(item, 'type', item.__class__.__name__)
                print(f"  • {item_type}")
                if isinstance(item, ResponseOutputMessage):
                    text_preview = ""
                    for part in item.content:
                        if isinstance(part, ResponseOutputText):
                            text_preview += part.text
                    if text_preview:
                        print(f"      💬 {OpenAIDebugger._truncate_text(text_preview, 200, 'response text')}")
                elif isinstance(item, ResponseFunctionToolCall):
                    print(f"      ⚙️ Tool call: {item.name}")
                elif isinstance(item, ResponseReasoningItem):
                    summary_preview = " ".join(
                        OpenAIDebugger._truncate_text(getattr(summary, 'text', ''), 120, 'reasoning')
                        for summary in item.summary
                        if getattr(summary, 'text', '')
                    ).strip()
                    if summary_preview:
                        print(f"      🧠 Reasoning: {summary_preview}")

            usage = response.usage
            if usage:
                print("📊 Token Usage:")
                print(f"    📝 Input: {getattr(usage, 'input_tokens', 'n/a')}")
                print(f"    🤖 Output: {getattr(usage, 'output_tokens', 'n/a')}")
                print(f"    📈 Total: {getattr(usage, 'total_tokens', 'n/a')}")

            print("========== END ==========")
            return

        # Unexpected response format
        print(f"⚠️  Unexpected response type: {type(response).__name__}")
        print(f"Response: {response}")
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
