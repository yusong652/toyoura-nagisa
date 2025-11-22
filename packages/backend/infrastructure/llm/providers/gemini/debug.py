"""
Gemini API debugging utilities.

Separates debugging concerns from the main GeminiClient to improve code organization
and maintainability. Provides comprehensive debugging capabilities for request/response
inspection and payload logging.
"""

import json
import copy
from typing import Dict, Any, List
from google.genai import types


class GeminiDebugger:
    """
    Handles all debugging functionality for Gemini API interactions.
    
    This class provides methods for:
    - Request/response debugging output
    - Payload censoring and formatting
    - Configuration processing for debug display
    - Tool information truncation for readability
    """

    @staticmethod
    def print_debug_request(contents: List[Dict[str, Any]], config) -> None:
        """
        Print formatted debug information for Gemini API requests.
        
        Args:
            contents: Formatted message contents for Gemini API
            config: GenerateContentConfig object
        """
        print("\n========== Gemini API 请求消息格式 ==========")
        
        # 使用model_dump()获取config的字典表示
        config_dict = config.model_dump()
        
        # 创建简化的config用于调试
        debug_config = GeminiDebugger._create_debug_config(config_dict)
        
        payload = {
            "contents": contents,
            "config": debug_config
        }
        
        payload_to_print = GeminiDebugger._censor_payload_for_logging(payload)
        
        # 使用简化的payload打印，避免过长的description影响调试
        print("\n📝 Simplified Payload (truncated descriptions):")
        GeminiDebugger._print_simplified_payload(payload_to_print)
        print("========== END ==========")
    
    @staticmethod
    def print_full_system_prompt(system_prompt: str) -> None:
        """
        Print the complete system prompt for debugging purposes.
        
        This method displays the full system instruction/prompt without truncation,
        allowing developers to verify the exact prompt being sent to the model.
        
        Args:
            system_prompt: Complete system prompt/instruction text
        """
        print("\n" + "=" * 80)
        print("🔍 GEMINI FULL SYSTEM PROMPT (DEBUG MODE)")
        print("=" * 80)
        
        if system_prompt:
            # Display basic statistics
            print(f"📊 System Prompt Statistics:")
            print(f"   - Total Length: {len(system_prompt)} characters")
            print(f"   - Lines Count: {system_prompt.count(chr(10)) + 1} lines")
            print(f"   - Words Count: {len(system_prompt.split())} words")
            print()
            print("📜 Complete System Instruction:")
            print("-" * 80)
            print(system_prompt)
            print("-" * 80)
        else:
            print("⚠️ No system prompt provided")
        
        print("=" * 80)
        print("END OF SYSTEM PROMPT")
        print("=" * 80 + "\n")

    @staticmethod
    def print_debug_response(response) -> None:
        """
        Print simplified debug information for Gemini API responses.
        
        Args:
            response: Raw response object from Gemini API
        """
        print("\n========== Gemini API Response ==========")
        print(f"Response type: {type(response).__name__}")
        
        # Check for errors
        if hasattr(response, 'error') and response.error:
            print(f"❌ Error: {response.error}")
            return
            
        # Check candidates
        if hasattr(response, 'candidates') and response.candidates:
            print(f"📋 Candidates: {len(response.candidates)}")
            
            for i, candidate in enumerate(response.candidates):
                if hasattr(candidate, 'finish_reason'):
                    print(f"  Candidate {i+1}: {candidate.finish_reason}")
                
                if hasattr(candidate, 'content') and candidate.content:
                    if hasattr(candidate.content, 'parts') and candidate.content.parts:
                        for j, part in enumerate(candidate.content.parts):
                            if hasattr(part, 'text') and part.text:
                                text_preview = part.text[:100] + "..." if len(part.text) > 100 else part.text
                                print(f"    Text part {j+1}: {repr(text_preview)}")
                            elif hasattr(part, 'function_call') and part.function_call:
                                print(f"    Function call: {part.function_call.name}")
        else:
            print("❌ No candidates found")
        
        print("========== END RESPONSE ==========")

    @staticmethod
    def _create_debug_config(config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a debug-friendly version of the config by truncating long fields.
        
        Args:
            config_dict: Dictionary representation of GenerateContentConfig
            
        Returns:
            Debug-friendly config dictionary with truncated long fields
        """
        debug_config = {}
        
        for key, value in config_dict.items():
            if key == "system_instruction":
                # Truncate system instruction
                if isinstance(value, str):
                    debug_config[key] = GeminiDebugger._truncate_text_for_debug(
                        value, max_length=200, field_name="system_instruction"
                    )
                else:
                    debug_config[key] = value
            elif key == "tools":
                # Process tools array to truncate descriptions
                if isinstance(value, list):
                    debug_config[key] = GeminiDebugger._process_tools_for_debug(value)
                else:
                    debug_config[key] = value
            else:
                # Keep other fields as-is
                debug_config[key] = value
        
        return debug_config

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
                
                # Process function_declarations if present
                if 'function_declarations' in processed_tool and isinstance(processed_tool['function_declarations'], list):
                    processed_declarations = []
                    
                    for func_decl in processed_tool['function_declarations']:
                        if isinstance(func_decl, dict):
                            processed_decl = func_decl.copy()
                            
                            # Truncate description
                            if 'description' in processed_decl and isinstance(processed_decl['description'], str):
                                original_desc = processed_decl['description']
                                processed_decl['description'] = GeminiDebugger._truncate_text_for_debug(
                                    original_desc, 
                                    max_length=100, 
                                    field_name=f"function '{func_decl.get('name', 'unknown')}' description"
                                )
                            
                            # Process parameters if they contain descriptions
                            if 'parameters' in processed_decl and isinstance(processed_decl['parameters'], dict):
                                processed_decl['parameters'] = GeminiDebugger._process_parameters_for_debug(
                                    processed_decl['parameters']
                                )
                            
                            processed_declarations.append(processed_decl)
                        else:
                            processed_declarations.append(func_decl)
                    
                    processed_tool['function_declarations'] = processed_declarations
                
                processed_tools.append(processed_tool)
            else:
                # If tool is not a dict (might be a Pydantic model), convert to string representation
                processed_tools.append(f"<{type(tool).__name__} object>")
        
        return processed_tools

    @staticmethod
    def _process_parameters_for_debug(parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process parameters dict to only keep properties field for debug output.
        
        Args:
            parameters: Parameters dictionary from tool schema
            
        Returns:
            Processed parameters with only properties field containing descriptions
        """
        # Only keep properties field from parameters
        if 'properties' in parameters and isinstance(parameters['properties'], dict):
            processed_properties = {}
            
            for prop_name, prop_value in parameters['properties'].items():
                if isinstance(prop_value, dict):
                    # Only keep description field for debug output
                    if 'description' in prop_value and isinstance(prop_value['description'], str):
                        original_desc = prop_value['description']
                        processed_properties[prop_name] = {
                            'description': GeminiDebugger._truncate_text_for_debug(
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
        censored_payload = copy.deepcopy(payload)
        
        if "contents" in censored_payload:
            for content in censored_payload.get("contents", []):
                if isinstance(content, dict) and "parts" in content:
                    for part in content.get("parts", []):
                        # Case 1: Part is a dictionary (typically from user messages)
                        if isinstance(part, dict) and 'inline_data' in part:
                            inline_data = part.get('inline_data', {})
                            if isinstance(inline_data, dict) and 'data' in inline_data:
                                data = inline_data.get('data')
                                if isinstance(data, str) and len(data) > 200:
                                    inline_data['data'] = f"{data[:100]}... [truncated {len(data)} chars]"
                        
                        # Case 2: Part is a Part object (typically from tool responses)
                        elif hasattr(part, 'inline_data') and part.inline_data:
                            inline_data_obj = part.inline_data
                            if hasattr(inline_data_obj, 'data'):
                                data = inline_data_obj.data
                                if isinstance(data, bytes) and len(data) > 200:
                                    inline_data_obj.data = data[:100] + b"... [truncated]"
                                elif isinstance(data, str) and len(data) > 200:
                                    inline_data_obj.data = f"{data[:100]}... [truncated {len(data)} chars]"
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
        if obj is None or isinstance(obj, (str, int, float, bool, list, dict)):
            return obj
        
        try:
            result = {}
            
            for attr in dir(obj):
                if (not attr.startswith('_') and 
                    not attr.startswith('model_') and
                    not callable(getattr(obj, attr))):
                    try:
                        value = getattr(obj, attr)
                        if value is not None:
                            if isinstance(value, list):
                                result[attr] = [GeminiDebugger._convert_object_to_dict(item) for item in value]
                            elif hasattr(value, '__dict__') or hasattr(value, '__slots__'):
                                result[attr] = GeminiDebugger._convert_object_to_dict(value)
                            else:
                                result[attr] = value
                    except Exception:
                        pass
            
            return result if result else str(obj)
            
        except Exception:
            return str(obj)

    @staticmethod
    def _print_simplified_payload(payload: Dict[str, Any]) -> None:
        """
        Print simplified payload using JSON format for better readability.
        
        Args:
            payload: Payload dictionary to print
        """
        def final_cleanup(obj):
            """Final cleanup to ensure no long fields are missed and unified object format"""
            if isinstance(obj, dict):
                result = {}
                for key, value in obj.items():
                    if isinstance(value, str) and len(value) > 300:
                        result[key] = GeminiDebugger._truncate_text_for_debug(
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
                return GeminiDebugger._convert_object_to_dict(obj)
        
        cleaned_payload = final_cleanup(payload)
        
        try:
            json_output = json.dumps(cleaned_payload, indent=2, ensure_ascii=False, default=str)
            print(json_output)
        except (TypeError, ValueError) as e:
            print(f"Debug payload (JSON serialization failed: {e}):")
            print(str(cleaned_payload)) 