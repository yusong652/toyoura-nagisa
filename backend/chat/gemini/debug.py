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
        GeminiDebugger._print_simplified_payload(payload_to_print, max_desc_length=50)
        print("========== END ==========")

    @staticmethod
    def print_debug_response(response) -> None:
        """
        Print comprehensive debug information for Gemini API responses.
        
        Args:
            response: Raw response object from Gemini API
        """
        print("\n========== Gemini API 响应格式 ==========")
        print("🔍 Full LLM Response Structure:")
        
        # 打印response基本信息
        print(f"Response type: {type(response).__name__}")
        
        # 检查并打印error信息（如果有）
        if hasattr(response, 'error') and response.error:
            print(f"❌ Error: {response.error}")
            
        # 检查并打印candidates
        if hasattr(response, 'candidates') and response.candidates:
            print(f"📋 Candidates count: {len(response.candidates)}")
            
            for i, candidate in enumerate(response.candidates):
                print(f"\n--- Candidate {i+1} ---")
                
                # 打印candidate基本信息
                if hasattr(candidate, 'index'):
                    print(f"  Index: {candidate.index}")
                if hasattr(candidate, 'finish_reason'):
                    print(f"  Finish reason: {candidate.finish_reason}")
                
                # 打印top-level thought（如果有）
                if hasattr(candidate, 'thought') and candidate.thought:
                    thought_preview = candidate.thought[:100] + "..." if len(candidate.thought) > 100 else candidate.thought
                    print(f"  💭 Top-level thought: {repr(thought_preview)}")
                
                # 打印content和parts
                if hasattr(candidate, 'content') and candidate.content:
                    content = candidate.content
                    print(f"  📝 Content type: {type(content).__name__}")
                    
                    if hasattr(content, 'parts') and content.parts:
                        print(f"  🧩 Parts count: {len(content.parts)}")
                        
                        for j, part in enumerate(content.parts):
                            print(f"    Part {j+1}: {type(part).__name__}")
                            
                            # 🔍 打印part的完整属性信息
                            part_attributes = {}
                            special_fields = ['text', 'function_call', 'function_response', 'thought_signature', 'thought', 'inline_data']
                            
                            for attr in dir(part):
                                if not attr.startswith('_') and not attr.startswith('model_'):
                                    try:
                                        value = getattr(part, attr)
                                        if not callable(value) and value is not None:
                                            part_attributes[attr] = value
                                    except:
                                        pass
                            
                            # 详细打印已知的特殊字段
                            if hasattr(part, 'text') and part.text:
                                text_preview = part.text[:150] + "..." if len(part.text) > 150 else part.text
                                print(f"      📄 Text: {repr(text_preview)}")
                            
                            if hasattr(part, 'thought_signature') and part.thought_signature:
                                print(f"      🧠 Thought Signature: {repr(part.thought_signature)}")
                            
                            if hasattr(part, 'thought') and part.thought:
                                print(f"      💭 Is Thought Content: {part.thought}")
                                # 注意：思维内容实际在 part.text 中，part.thought 只是布尔标识符
                            
                            if hasattr(part, 'function_call') and part.function_call:
                                func_call = part.function_call
                                print(f"      🔧 Function call:")
                                print(f"        Name: {func_call.name}")
                                if hasattr(func_call, 'id'):
                                    print(f"        ID: {func_call.id}")
                                if hasattr(func_call, 'args') and func_call.args:
                                    print(f"        Args: {func_call.args}")
                                elif hasattr(func_call, 'arguments') and func_call.arguments:
                                    print(f"        Arguments: {func_call.arguments}")
                            
                            if hasattr(part, 'function_response') and part.function_response:
                                func_resp = part.function_response
                                print(f"      🔄 Function response:")
                                print(f"        Name: {func_resp.name}")
                                if hasattr(func_resp, 'response'):
                                    print(f"        Response: {func_resp.response}")
                            
                            if hasattr(part, 'inline_data') and part.inline_data:
                                print(f"      📎 Inline data: {type(part.inline_data).__name__}")
                            
                            # 打印所有属性的完整JSON（用于调试）
                            try:
                                serializable_attrs = {}
                                for key, value in part_attributes.items():
                                    try:
                                        # 尝试序列化，如果失败则转为字符串
                                        json.dumps(value)
                                        serializable_attrs[key] = value
                                    except:
                                        serializable_attrs[key] = str(value) if value is not None else None
                                
                                if serializable_attrs:
                                    part_json = json.dumps(serializable_attrs, indent=8, ensure_ascii=False, default=str)
                                    print(f"      🔍 完整Part属性: {part_json}")
                            except Exception as e:
                                print(f"      ❌ Part属性序列化失败: {e}")
                                print(f"      🔍 Part原始信息: {part}")
                else:
                    print(f"  ❌ No content found in candidate")
        else:
            print("❌ No candidates found in response")
        
        # 打印response的其他属性
        print(f"\n🔍 Response attributes:")
        try:
            response_attrs = {}
            # 需要跳过的Pydantic内部属性和其他已处理的属性
            skip_attrs = {
                'candidates', 'error', 'model_computed_fields', 'model_fields', 
                'model_config', 'model_fields_set', 'model_extra', 'model_dump',
                'model_dump_json', 'model_copy', 'model_validate', 'model_validate_json'
            }
            
            for attr in dir(response):
                if (not attr.startswith('_') and 
                    attr not in skip_attrs and 
                    not attr.startswith('model_')):
                    try:
                        value = getattr(response, attr)
                        if not callable(value):
                            response_attrs[attr] = str(value) if value is not None else None
                    except Exception:
                        # 跳过无法访问的属性
                        pass
                        
            if response_attrs:
                attrs_json = json.dumps(response_attrs, indent=2, ensure_ascii=False, default=str)
                print(attrs_json)
            else:
                print("No additional attributes found")
        except Exception as e:
            print(f"Failed to extract response attributes: {e}")
        
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
        将对象转换为字典格式，解决混合格式序列化问题
        
        Args:
            obj: 需要转换的对象
            
        Returns:
            转换后的字典或原始值
        """
        # 如果是基本类型，直接返回
        if obj is None or isinstance(obj, (str, int, float, bool, list, dict)):
            return obj
        
        # 尝试转换为字典格式
        try:
            result = {}
            
            # 提取对象的有效属性
            for attr in dir(obj):
                if (not attr.startswith('_') and 
                    not attr.startswith('model_') and
                    not callable(getattr(obj, attr))):
                    try:
                        value = getattr(obj, attr)
                        if value is not None:
                            # 递归处理嵌套对象
                            if isinstance(value, list):
                                result[attr] = [GeminiDebugger._convert_object_to_dict(item) for item in value]
                            elif hasattr(value, '__dict__') or hasattr(value, '__slots__'):
                                result[attr] = GeminiDebugger._convert_object_to_dict(value)
                            else:
                                result[attr] = value
                    except Exception:
                        # 如果无法访问属性，跳过
                        pass
            
            return result if result else str(obj)
            
        except Exception:
            # 如果转换失败，返回字符串表示
            return str(obj)

    @staticmethod
    def _print_simplified_payload(payload: Dict[str, Any], max_desc_length: int = 60) -> None:
        """
        Print simplified payload using JSON format for better readability.
        
        Args:
            payload: Payload dictionary to print
            max_desc_length: Maximum length for description fields (unused, handled upstream)
        """
        # 由于payload已经在_create_debug_config中被预处理，
        # 这里只需要处理一些可能遗漏的递归结构
        def final_cleanup(obj):
            """最终清理，确保没有遗漏的长字段，并统一对象格式"""
            if isinstance(obj, dict):
                result = {}
                for key, value in obj.items():
                    if isinstance(value, str) and len(value) > 300:
                        # 对任何仍然过长的字符串进行最终截断
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
                # 🚀 修复：将对象转换为字典格式，避免混合序列化问题
                return GeminiDebugger._convert_object_to_dict(obj)
        
        cleaned_payload = final_cleanup(payload)
        
        # 使用JSON dumps代替pprint，确保description等字段单行显示
        try:
            # 使用indent=2进行美观格式化，但避免pprint的自动文本换行
            json_output = json.dumps(cleaned_payload, indent=2, ensure_ascii=False, default=str)
            print(json_output)
        except (TypeError, ValueError) as e:
            # 如果JSON序列化失败，回退到基本字符串表示
            print(f"Debug payload (JSON serialization failed: {e}):")
            print(str(cleaned_payload)) 