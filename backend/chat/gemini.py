import os
import re
import json
import copy
from typing import List, Optional, Dict, Any

from google import genai
from google.genai import types

from backend.config import get_llm_specific_config, get_system_prompt, get_text_to_image_config
from backend.chat.base import LLMClientBase
from backend.chat.models import BaseMessage, UserMessage, UserToolMessage, LLMResponse, ResponseType
from backend.chat.utils import parse_llm_output, get_latest_n_messages
from fastmcp import Client as MCPClient
from backend.nagisa_mcp.smart_mcp_server import mcp as GLOBAL_MCP
from mcp.types import Implementation, CallToolRequestParams, CallToolRequest, ClientRequest, CallToolResult
from backend.nagisa_mcp.utils import extract_text_from_mcp_result

class GeminiClient(LLMClientBase):
    """
    Google Gemini client implementation using the new google-genai SDK.
    """
    
    def __init__(self, api_key: str, **kwargs):
        """
        初始化 Gemini 客户端。
        Args:
            api_key: Google API key。
        """
        super().__init__(**kwargs)
        self.client = genai.Client(api_key=api_key)
        self.safety_settings = [
            {
                "category": types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                "threshold": types.HarmBlockThreshold.BLOCK_NONE
            },
            {
                "category": types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                "threshold": types.HarmBlockThreshold.BLOCK_NONE
            },
            {
                "category": types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                "threshold": types.HarmBlockThreshold.BLOCK_NONE
            },
            {
                "category": types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                "threshold": types.HarmBlockThreshold.BLOCK_NONE
            }
        ]
        
        print(f"Gemini Client initialized with model: {self.extra_config.get('model', 'gemini-1.5-flash-latest')}")

        self._mcp_client_source = GLOBAL_MCP

        # 按 chat_session_id 缓存已创建的 MCPClient；None 代表默认/无会话
        self._mcp_clients: dict[str | None, MCPClient] = {}

        # -------------------------------------------------------------
        # 工具缓存机制（之前版本已有）
        # -------------------------------------------------------------
        # 全局工具缓存，避免重复查询
        self.tool_cache: Dict[str, Any] = {}
        # meta tool 名称集合，用于快速判定
        self.meta_tools: set[str] = set()
        # 按会话维度的工具缓存：{session_id: List[tool_schema]}
        self.session_tool_cache: Dict[str, List[Dict[str, Any]]] = {}


    def _get_mcp_client(self, session_id: Optional[str] = None) -> MCPClient:
        """Return (and cache) an MCPClient bound to *session_id*.

        A unique client per chat-session ensures the underlying FastMCP
        Session stays isolated.  If *self._mcp_client_source* is already an
        MCPClient, we always reuse that single instance.
        """

        # If caller injected a ready-made MCPClient, we cannot (and need not)
        # create more – just return it regardless of session_id.
        key = session_id or "__default__"
        client = self._mcp_clients.get(key)
        if client is None:
            client = MCPClient(self._mcp_client_source, client_info=Implementation(name=session_id, version="0.1.0"))
            self._mcp_clients[key] = client
        return client

    def _is_meta_tool(self, tool_name: str) -> bool:
        """判断是否为meta tool"""
        return tool_name in {
            "search_tools_by_keywords",
            "get_available_tool_categories"
        }

    def _extract_tools_from_meta_result(self, meta_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从meta tool结果中提取工具信息"""
        tools = []
        if isinstance(meta_result, dict):
            # 处理search_tools_by_keywords的结果
            if "tools" in meta_result and isinstance(meta_result["tools"], list):
                for tool_info in meta_result["tools"]:
                    if isinstance(tool_info, dict) and "name" in tool_info:
                        
                        # 解析 parameters
                        params = tool_info.get("parameters", {})
                        if isinstance(params, str):
                            try:
                                params = json.loads(params)
                            except (json.JSONDecodeError, TypeError):
                                params = {} # 解析失败则视为空
                        
                        # 解析 tags
                        tags = tool_info.get("tags", [])
                        if isinstance(tags, str):
                            try:
                                tags = json.loads(tags)
                            except (json.JSONDecodeError, TypeError):
                                tags = [] # 解析失败则视为空

                        tools.append({
                            "name": tool_info["name"],
                            "description": tool_info.get("description", ""),
                            "category": tool_info.get("category", "general"),
                            "docstring": tool_info.get("docstring", ""),
                            "parameters": params,
                            "tags": tags
                        })
        return tools

    def _cache_tools_for_session(self, session_id: str, tools: List[Dict[str, Any]]):
        """为会话缓存工具"""
        if session_id not in self.session_tool_cache:
            self.session_tool_cache[session_id] = []
        
        # 添加新工具，避免重复
        existing_names = {tool["name"] for tool in self.session_tool_cache[session_id]}
        for tool in tools:
            if tool["name"] not in existing_names:
                self.session_tool_cache[session_id].append(tool)
                existing_names.add(tool["name"])

    def _get_cached_tools_for_session(self, session_id: str) -> List[Dict[str, Any]]:
        """获取会话缓存的工具"""
        return self.session_tool_cache.get(session_id, [])

    def _clear_session_tool_cache(self, session_id: str):
        """清除会话的工具缓存"""
        if session_id in self.session_tool_cache:
            del self.session_tool_cache[session_id]

    def map_role(self, role: str) -> str:
        if role == "assistant":
            return "model"
        return "user"

    def _process_inline_data(self, inline_data: Dict[str, Any]) -> Optional[types.Blob]:
        """
        处理 inline_data，将 base64 字符串转换为 Gemini API 需要的 Blob 格式。
        
        Args:
            inline_data: 包含 mime_type 和 data 的字典
            
        Returns:
            types.Blob 对象，如果处理失败则返回 None
        """
        try:
            data_field = inline_data['data']
            mime_type = inline_data.get('mime_type', 'image/png')
            
            # 如果数据是字符串（base64），解码为字节
            if isinstance(data_field, str):
                import base64 as _b64
                data_field = _b64.b64decode(data_field)
            
            # 确保数据是字节格式
            if not isinstance(data_field, bytes):
                print(f"[WARNING] Invalid data format: expected bytes, got {type(data_field)}")
                return None
            
            return types.Blob(mime_type=mime_type, data=data_field)
            
        except Exception as e:
            print(f"[WARNING] Failed to process inline_data: {e}")
            return None

    def _format_messages_for_gemini(self, messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """
        Format messages into Gemini API compatible format with enhanced multimodal support.
        
        Handles:
        - Text messages with thinking blocks
        - Function calls and tool responses  
        - Multimodal content (images, documents) from tool outputs
        - Standard inline_data format and structured tool results
        
        For tool responses containing multimodal content, creates separate Parts:
        1. Image/document Part with decoded binary data
        2. Function response Part with status information
        
        Args:
            messages: List of BaseMessage objects to format
            
        Returns:
            List of formatted message dictionaries for Gemini API
        """
        contents = []
        for msg in messages:
            # Gemini function call标准：
            # - assistant function_call消息用model+function_call结构
            # - tool响应用user+function_response结构
            if msg.role == "assistant" and getattr(msg, "tool_calls", None):
                # function_call消息，可以包含思考过程和工具调用
                parts = []
                
                # 1. 提取思考过程 (thinking)
                # 这部分作为上下文提供给模型，了解它为何调用工具
                if isinstance(msg.content, list):
                    for item in msg.content:
                        if item.get("type") == "thinking" and item.get("thinking"):
                            # For thinking parts, we create a Part object where the text is the thought.
                            # The Gemini API doesn't have a 'thought=True' flag on request Parts.
                            # The model's own output format (thoughts as text) is the expected input format.
                            parts.append(types.Part(text=item["thinking"], thought=True))
                        elif item.get("type") == "text" and item.get("text"):
                            parts.append(types.Part(text=item["text"]))
                
                # 3. 添加工具调用 (tool_calls)
                for tool_call in msg.tool_calls:
                    arguments = tool_call["function"].get("arguments", {})
                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except (json.JSONDecodeError, TypeError):
                            # 如果无法解析，则保留为字符串或空字典
                            arguments = {"error": "invalid JSON arguments", "raw": arguments}
                    parts.append(types.Part(function_call=types.FunctionCall(
                        name=tool_call["function"]["name"],
                        args=arguments,
                        id=tool_call.get("id", tool_call["function"]["name"])
                    )))
                
                if parts:
                    contents.append({"role": "model", "parts": parts})
                continue
            # 处理工具响应消息
            if isinstance(msg, UserToolMessage):
                tool_name = msg.name
                if not tool_name:
                    print(f"[WARNING] Tool response missing name: {msg}")
                    continue
                
                # 优化的多模态内容检测逻辑
                is_image = False
                inline_data = None
                
                if isinstance(msg.content, dict):
                    # 检查标准化格式: content.data.inline_data
                    if (msg.content.get("content", {}).get("format") == "inline_data" and 
                        isinstance(msg.content.get("content", {}).get("data"), dict) and
                        "inline_data" in msg.content["content"]["data"]):
                        is_image = True
                        inline_data = msg.content["content"]["data"]["inline_data"]
                    # 检查直接格式: content.inline_data (兼容性)
                    elif 'inline_data' in msg.content:
                        is_image = True
                        inline_data = msg.content['inline_data']
                
                if is_image and inline_data:
                    data_field = inline_data['data']
                    mime_type = inline_data.get('mime_type', 'image/png')
                    try:
                        import base64
                        image_bytes = base64.b64decode(data_field)
                        parts = [
                            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                            types.Part(function_response=types.FunctionResponse(
                                name=tool_name,
                                response={'status': 'success', 'content': 'Image file read successfully.'}
                            ))
                        ]
                    except Exception as e:
                        print(f"[WARNING] Failed to decode inline_data in tool response: {e}")
                        parts = [types.Part(function_response=types.FunctionResponse(
                            name=tool_name,
                            response={'status': 'error', 'content': 'Failed to decode image data'}
                        ))]
                    contents.append({"role": "user", "parts": parts})
                    continue
                else:
                    response_dict = msg.content if isinstance(msg.content, dict) else {"result": str(msg.content)}
                    parts = [types.Part(function_response=types.FunctionResponse(
                        name=tool_name,
                        response=response_dict
                    ))]
                contents.append({"role": "user", "parts": parts})
                continue
            # 普通消息
            parts = []
            if isinstance(msg.content, list):
                for item in msg.content:
                    # 1. 先处理图片内容
                    if "inline_data" in item:
                        inline_data = item["inline_data"]
                        data_field = inline_data["data"]
                        mime_type = inline_data.get("mime_type", "image/png")
                        try:
                            import base64
                            image_bytes = base64.b64decode(data_field)
                            parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
                        except Exception as e:
                            print(f"[WARNING] Failed to decode inline_data: {e}")
                            continue
                    # 2. 再处理文本内容
                    if "text" in item:
                        parts.append(types.Part(text=item["text"]))
            else:
                parts.append(types.Part(text=str(msg.content)))
            mapped_role = self.map_role(msg.role)
            contents.append({"role": mapped_role, "parts": parts})
        return contents

    def _format_llm_response(self, response) -> LLMResponse:
        """
        Format Gemini API response into LLMResponse object.
        
        Args:
            response: Raw response from Gemini API
        Returns:
            LLMResponse object containing the formatted response
        """
        if not (hasattr(response, 'candidates') and response.candidates):
            return LLMResponse(content=[{"type": "text", "text": ""}], response_type=ResponseType.ERROR)

        candidate = response.candidates[0]
        
        content_list = []
        tool_calls = []
        thinking_parts = []
        text_parts = []
        
        # 1. Extract top-level thought (high-level summary)
        if hasattr(candidate, 'thought') and candidate.thought:
            thinking_parts.append(candidate.thought)
            
        # 2. Iterate through parts, distinguishing between thought and text
        if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
            for part in candidate.content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    tool_calls.append({
                        'name': part.function_call.name,
                        'arguments': part.function_call.args if hasattr(part.function_call, 'args') else part.function_call.arguments,
                        'id': part.function_call.id or part.function_call.name
                    })
                elif hasattr(part, 'text') and part.text:
                    # Check if the part is a thought via `getattr(part, 'thought', False)`
                    if getattr(part, 'thought', False):
                        thinking_parts.append(part.text)
                    else:
                        text_parts.append(part.text)

        # 3. Combine thinking content
        if thinking_parts:
            full_thinking_content = "\n".join(thinking_parts).strip()
            if full_thinking_content:
                content_list.append({
                    "type": "thinking",
                    "thinking": full_thinking_content,
                })
        
        # 4. Combine text content
        full_text_content = "".join(text_parts).strip()
        if full_text_content:
            response_text, _ = parse_llm_output(full_text_content)
            content_list.append({
                "type": "text",
                "text": response_text
            })

        # 5. Return LLMResponse based on content
        if tool_calls:
            return LLMResponse(
                content=content_list,
                response_type=ResponseType.FUNCTION_CALL,
                tool_calls=tool_calls
            )
        
        if content_list:
            _, keyword = parse_llm_output(full_text_content)
            return LLMResponse(
                content=content_list,
                response_type=ResponseType.TEXT,
                keyword=keyword
            )
            
        return LLMResponse(
            content=[{"type": "text", "text": "Empty response from model."}],
            response_type=ResponseType.ERROR
        )

    def _censor_payload_for_logging(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates a deep copy of the payload and censors large data fields for logging.
        Handles both dicts (from user messages) and Part objects (from tool responses).
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

    def _print_debug_request(self, contents, config):
        print("\n========== Gemini API 请求消息格式 ==========")
        
        # 使用model_dump()获取config的字典表示
        config_dict = config.model_dump()
        
        # 创建简化的config用于调试
        debug_config = self._create_debug_config(config_dict)
        
        payload = {
            "contents": contents,
            "config": debug_config
        }
        
        payload_to_print = self._censor_payload_for_logging(payload)
        
        # 使用简化的payload打印，避免过长的description影响调试
        print("\n📝 Simplified Payload (truncated descriptions):")
        self._print_simplified_payload(payload_to_print, max_desc_length=50)
        print("========== END ==========")

    def _print_debug_response(self, response):
        """
        打印完整的LLM response用于调试，包括所有candidates和详细内容。
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
                            
                            # 检查text content
                            if hasattr(part, 'text') and part.text:
                                text_preview = part.text[:150] + "..." if len(part.text) > 150 else part.text
                                is_thought = getattr(part, 'thought', False)
                                thought_indicator = " (THOUGHT)" if is_thought else ""
                                print(f"      📄 Text{thought_indicator}: {repr(text_preview)}")
                            
                            # 检查function call
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
                            
                            # 检查其他part类型
                            if not (hasattr(part, 'text') or hasattr(part, 'function_call')):
                                # 使用JSON格式显示part的所有属性
                                try:
                                    import json
                                    part_dict = {}
                                    for attr in dir(part):
                                        if not attr.startswith('_'):
                                            try:
                                                value = getattr(part, attr)
                                                if not callable(value):
                                                    part_dict[attr] = str(value) if value is not None else None
                                            except:
                                                pass
                                    part_json = json.dumps(part_dict, indent=6, ensure_ascii=False, default=str)
                                    print(f"      🔍 Part attributes: {part_json}")
                                except:
                                    print(f"      🔍 Part attributes: {part}")
                else:
                    print(f"  ❌ No content found in candidate")
        else:
            print("❌ No candidates found in response")
        
        # 打印response的其他属性
        print(f"\n🔍 Response attributes:")
        try:
            import json
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

    def _create_debug_config(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a debug-friendly version of the config by truncating long fields.
        """
        debug_config = {}
        
        for key, value in config_dict.items():
            if key == "system_instruction":
                # Truncate system instruction
                if isinstance(value, str):
                    debug_config[key] = self._truncate_text_for_debug(value, max_length=200, field_name="system_instruction")
                else:
                    debug_config[key] = value
            elif key == "tools":
                # Process tools array to truncate descriptions
                if isinstance(value, list):
                    debug_config[key] = self._process_tools_for_debug(value)
                else:
                    debug_config[key] = value
            else:
                # Keep other fields as-is
                debug_config[key] = value
        
        return debug_config

    def _process_tools_for_debug(self, tools: list) -> list:
        """
        Process tools array to truncate long descriptions for debug output.
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
                                processed_decl['description'] = self._truncate_text_for_debug(
                                    original_desc, 
                                    max_length=100, 
                                    field_name=f"function '{func_decl.get('name', 'unknown')}' description"
                                )
                            
                            # Process parameters if they contain descriptions
                            if 'parameters' in processed_decl and isinstance(processed_decl['parameters'], dict):
                                processed_decl['parameters'] = self._process_parameters_for_debug(processed_decl['parameters'])
                            
                            processed_declarations.append(processed_decl)
                        else:
                            processed_declarations.append(func_decl)
                    
                    processed_tool['function_declarations'] = processed_declarations
                
                processed_tools.append(processed_tool)
            else:
                # If tool is not a dict (might be a Pydantic model), convert to string representation
                processed_tools.append(f"<{type(tool).__name__} object>")
        
        return processed_tools

    def _process_parameters_for_debug(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process parameters dict to truncate descriptions in properties.
        """
        processed_params = parameters.copy()
        
        if 'properties' in processed_params and isinstance(processed_params['properties'], dict):
            processed_properties = {}
            
            for prop_name, prop_value in processed_params['properties'].items():
                if isinstance(prop_value, dict):
                    processed_prop = prop_value.copy()
                    
                    # Truncate description in property
                    if 'description' in processed_prop and isinstance(processed_prop['description'], str):
                        original_desc = processed_prop['description']
                        processed_prop['description'] = self._truncate_text_for_debug(
                            original_desc,
                            max_length=80,
                            field_name=f"parameter '{prop_name}' description"
                        )
                    
                    processed_properties[prop_name] = processed_prop
                else:
                    processed_properties[prop_name] = prop_value
            
            processed_params['properties'] = processed_properties
        
        return processed_params

    def _truncate_text_for_debug(self, text: str, max_length: int = 100, field_name: str = "text") -> str:
        """
        Truncate text for debug output with informative truncation message.
        Converts multiline text to single line for better readability.
        """
        if len(text) <= max_length:
            # Still convert to single line even if no truncation needed
            return ' '.join(text.split())
        
        # Convert multiline to single line by replacing newlines with spaces
        single_line_text = ' '.join(text.split())
        
        # Extract key information from the beginning
        truncated = single_line_text[:max_length-20] + f"... [truncated {field_name}: {len(text)} chars total]"
        return truncated

    def _print_simplified_payload(self, payload: Dict[str, Any], max_desc_length: int = 60):
        """
        打印简化的payload，使用JSON格式确保单行显示，避免pprint的自动换行。
        现在payload已经在_create_debug_config中被预处理过，这里主要做最终的格式化输出。
        """
        # 由于payload已经在_create_debug_config中被预处理，
        # 这里只需要处理一些可能遗漏的递归结构
        def final_cleanup(obj):
            """最终清理，确保没有遗漏的长字段"""
            if isinstance(obj, dict):
                result = {}
                for key, value in obj.items():
                    if isinstance(value, str) and len(value) > 300:
                        # 对任何仍然过长的字符串进行最终截断
                        result[key] = self._truncate_text_for_debug(value, max_length=100, field_name=f"field '{key}'")
                    elif isinstance(value, (dict, list)):
                        result[key] = final_cleanup(value)
                    else:
                        result[key] = value
                return result
            elif isinstance(obj, list):
                return [final_cleanup(item) for item in obj]
            else:
                return obj
        
        cleaned_payload = final_cleanup(payload)
        
        # 使用JSON dumps代替pprint，确保description等字段单行显示
        import json
        try:
            # 使用indent=2进行美观格式化，但避免pprint的自动文本换行
            json_output = json.dumps(cleaned_payload, indent=2, ensure_ascii=False, default=str)
            print(json_output)
        except (TypeError, ValueError) as e:
            # 如果JSON序列化失败，回退到基本字符串表示
            print(f"Debug payload (JSON serialization failed: {e}):")
            print(str(cleaned_payload))

    async def get_function_call_schemas(self, session_id: Optional[str] = None):
        """
        获取所有 MCP 工具的 schema，供 LLM function call 注册用，返回 Gemini tools 格式列表
        只返回 meta tools + cached tools，不返回所有 regular tools。
        """
        if not self.tools_enabled:
            return []
            
        debug = self.extra_config.get('debug', False)
        
        # 获取会话缓存的工具
        cached_tools = []
        if session_id:
            cached_tools = self._get_cached_tools_for_session(session_id)
            if debug:
                print(f"[DEBUG] Found {len(cached_tools)} cached tools for session {session_id}")
        
        # 获取所有MCP工具
        mcp_client = self._get_mcp_client(session_id)
        async with mcp_client as mcp_async_client:
            mcp_tools = await mcp_async_client.list_tools()
        
        # 构建工具映射
        tools_map = {}
        meta_tools = []
        
        for tool in mcp_tools:
            tool_name = tool.name
            
            # 简化参数处理
            input_schema = getattr(tool, "inputSchema", {"type": "object", "properties": {}})
            if "properties" in input_schema:
                for prop in input_schema["properties"].values():
                    if "description" not in prop:
                        prop["description"] = f"Parameter value"
                input_schema["required"] = list(input_schema["properties"].keys())
            if "type" not in input_schema:
                input_schema["type"] = "object"
            # Gemini 不允许 additionalProperties 字段
            input_schema.pop("additionalProperties", None)
            
            # 移除 Gemini 不支持的 JSON Schema 关键字（如 exclusiveMinimum）
            input_schema = self._sanitize_jsonschema(input_schema)
            
            tool_schema = {
                "name": tool_name,
                "description": getattr(tool, "description", tool_name),
                "parameters": input_schema
            }
            
            tools_map[tool_name] = tool_schema
            if self._is_meta_tool(tool_name):
                meta_tools.append(tool_schema)
        
        # 构建最终工具列表：meta tools + cached tools（避免重复）
        final_tools = meta_tools.copy()
        added_tool_names = {tool["name"] for tool in meta_tools}  # 追踪已添加的工具名
        
        for cached_tool in cached_tools:
            tool_name = cached_tool["name"]
            if tool_name in added_tool_names:
                if debug:
                    print(f"[DEBUG] Skipped duplicate cached tool: {tool_name}")
                continue  # 跳过已经添加的工具
                
            # 复制参数，避免污染原 dict
            cached_params = dict(cached_tool.get("parameters", {}))
            cached_params.pop("additionalProperties", None)
            cached_params = self._sanitize_jsonschema(cached_params)
            if tool_name in tools_map:
                final_tools.append(tools_map[tool_name])
                added_tool_names.add(tool_name)
                if debug:
                    print(f"[DEBUG] Added cached tool: {tool_name}")
            else:
                final_tools.append({
                    "name": tool_name,
                    "description": cached_tool.get("description", tool_name),
                    "parameters": {
                        "type": "object",
                        "properties": cached_params,
                        "required": list(cached_params.keys())
                    }
                })
                added_tool_names.add(tool_name)
                if debug:
                    print(f"[DEBUG] Added cached tool with basic schema: {tool_name}")
        
        if debug:
            print(f"[DEBUG] Final tools count: {len(final_tools)} (meta: {len(meta_tools)}, cached: {len(cached_tools)})")
        
        # 转换为 Gemini 格式
        function_declarations = [
            {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": self._sanitize_jsonschema(tool.get("parameters", {"type": "object", "properties": {}})),
            }
            for tool in final_tools
        ]
        
        tools = []
        if function_declarations:
            tools.append(types.Tool(function_declarations=function_declarations))
        
        return tools

    async def get_response(
        self,
        messages: List[BaseMessage],
        session_id: Optional[str] = None,
        **kwargs
    ) -> 'LLMResponse':
        # 1. 获取所有工具 schemas（包括 MCP 工具和代码执行工具）
        tool_schemas = await self.get_function_call_schemas(session_id)
        
        tools_enabled = bool(tool_schemas)
        system_prompt = get_system_prompt(tools_enabled=tools_enabled)
        
        debug = self.extra_config.get('debug', False)

        # 2. 构造 Gemini API payload，注册 tools
        contents = self._format_messages_for_gemini(messages)
        config_kwargs = dict(
            system_instruction=system_prompt,
            safety_settings=self.safety_settings,
            temperature=self.extra_config.get('temperature', 2.0),
            max_output_tokens=self.extra_config.get('max_output_tokens', 4096),
            tools=tool_schemas,
        )
        if self.extra_config.get('model', "").startswith("gemini-2.5"):
            config_kwargs["thinking_config"] = types.ThinkingConfig(include_thoughts=True)
        config = types.GenerateContentConfig(**config_kwargs)

        if self.extra_config.get('debug', False):
            self._print_debug_request(contents, config)

        try:
            # For GenerativeModel, we call generate_content directly on the model instance
            response = self.client.models.generate_content(
                model=self.extra_config.get('model', "gemini-2.0-flash-lite"),
                contents=contents,
                config=config,
            )
            
            # 检查响应中是否有错误
            if hasattr(response, 'error'):
                error_message = f"Gemini API error: {response.error.message if hasattr(response.error, 'message') else str(response.error)}"
                print(f"[DEBUG] llm_response type: error")
                print(f"[DEBUG] {error_message}")
                return LLMResponse(
                    content=error_message,
                    response_type=ResponseType.ERROR
                )
            
            # 检查响应是否为空
            if not hasattr(response, 'candidates') or not response.candidates:
                error_message = "Gemini API returned empty response"
                print(f"[DEBUG] llm_response type: error")
                print(f"[DEBUG] {error_message}")
                return LLMResponse(
                    content=error_message,
                    response_type=ResponseType.ERROR
                )
            
            # Debug输出完整的LLM response
            if debug:
                self._print_debug_response(response)
            
            return self._format_llm_response(response)
                
        except Exception as e:
            error_message = f"Gemini API error: {str(e)}"
            print(f"[DEBUG] llm_response type: error")
            print(f"[DEBUG] {error_message}")
            if hasattr(e, 'status_code'):
                error_message += f" (Status code: {e.status_code})"
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                try:
                    error_details = json.loads(e.response.text)
                    if 'error' in error_details:
                        error_message += f"\nDetails: {error_details['error'].get('message', str(error_details))}"
                except:
                    error_message += f"\nRaw error: {e.response.text}"
            
            return LLMResponse(
                content=error_message,
                response_type=ResponseType.ERROR
            )

    async def generate_title_from_messages(
        self,
        first_user_message: BaseMessage,
        first_assistant_message: BaseMessage,
        title_generation_system_prompt: Optional[str] = None
    ) -> Optional[str]:
        """
        根据对话的第一轮消息生成一个简洁的对话标题。
        为Gemini API定制的实现，支持多模态 content。
        
        Args:
            first_user_message: Message object containing the first user message
            first_assistant_message: Message object containing the first assistant message
            title_generation_system_prompt: Optional custom system prompt for title generation
        """
        try:
            system_prompt = title_generation_system_prompt or "你是一个专业的对话标题生成助手。请根据提供的对话内容，生成一个简洁的标题（5-15个字）。标题应准确概括对话的主要主题或意图。你必须将标题放在<title></title>标签中，并且除了这些标签和标题本身外，不要输出任何其他内容。"
            
            # 配置生成标题的参数
            title_config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=2.0,
                max_output_tokens=1024
            )
            
            # 构造消息序列，最后一条为user
            messages = [
                first_user_message,
                first_assistant_message,
                UserMessage(role="user", content=[{"type": "text", "text": "请为上面对话生成标题"}])
            ]
            
            # 处理消息内容
            contents = []
            for msg in messages:
                parts = []
                if isinstance(msg.content, list):
                    for item in msg.content:
                        if "text" in item:
                            parts.append(types.Part(text=item['text']))
                        elif "inline_data" in item:
                            # 使用统一的 inline_data 处理方法
                            blob = self._process_inline_data(item['inline_data'])
                            if blob:
                                parts.append(types.Part(inline_data=blob))
                else:
                    # 处理字符串内容
                    parts.append(types.Part(text=str(msg.content)))
                # 使用 map_role 函数转换角色名称
                mapped_role = self.map_role(msg.role)
                contents.append({"role": mapped_role, "parts": parts})
            
            response = self.client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=contents,
                config=title_config
            )
            
            if hasattr(response, 'candidates') and response.candidates and response.candidates[0].content.parts:
                title_response_text = response.candidates[0].content.parts[0].text
                
                # 处理标题格式
                title_match = re.search(r'<title>(.*?)</title>', title_response_text, re.DOTALL)
                if title_match:
                    title = title_match.group(1).strip()
                    if not title:
                        return None
                    if len(title) > 30:
                        title = title[:30]
                    return title
                
                # 兜底处理
                cleaned_title = title_response_text.strip().strip('"\'').strip()
                if cleaned_title and len(cleaned_title) <= 30:
                    return cleaned_title
            return None
            
        except Exception as e:
            print(f"Gemini生成标题时出错: {str(e)}")
            return None

    def convert_mcp_schema_to_gemini(self, schema: dict) -> dict:
        """
        Convert a fastMCP tool schema to Gemini-compatible function call schema.
        """
        return {
            "name": schema["name"],
            "description": schema.get("description", ""),
            "parameters": schema.get("inputSchema", {"type": "object", "properties": {}})
        }

    async def handle_function_call(self, function_call: dict, session_id: Optional[str] = None):
        """
        处理 LLM 生成的 function_call 请求，自动分发到 MCP 工具
        function_call: 形如 {"name": "search_weather", "arguments": {"city": "北京"}}
        session_id: 可选的会话ID，用于需要会话上下文的工具（如文生图）
        """
        tool_name = function_call["name"]
        tool_args = function_call.get("arguments", {})
        tool_id = function_call.get("id", "")
        debug = self.extra_config.get('debug', False)

        # 1. Meta tool handling (remains the same)
        if self._is_meta_tool(tool_name):
            if debug:
                print(f"[DEBUG] Handling meta tool: {tool_name}")
            
            try:
                mcp_client = self._get_mcp_client(session_id)
                async with mcp_client as mcp_async_client:
                    # (Existing meta tool logic...)
                    if session_id:
                        try:
                            params = CallToolRequestParams(
                                name=tool_name,
                                arguments=tool_args,
                                **{"_meta": {"client_id": session_id}},
                            )
                            call_req = ClientRequest(CallToolRequest(method="tools/call", params=params))
                            result: CallToolResult = await mcp_async_client.session.send_request(
                                call_req,
                                CallToolResult,
                            )
                        except Exception:
                            result = await mcp_async_client.call_tool(tool_name, tool_args)
                    
                    text_result = extract_text_from_mcp_result(result)
                    
                    # Check for error
                    if isinstance(result, dict) and result.get("error"):
                        return {
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "name": tool_name,
                            "content": text_result,
                            "is_error": True
                        }
                    
                    # Extract llm_content for meta tools (same as normal tools)
                    content_for_llm = text_result
                    if isinstance(text_result, dict):
                        # If it's our standard ToolResult, extract the specific llm_content part
                        if 'llm_content' in text_result:
                            content_for_llm = text_result['llm_content']
                        
                        # Check for error status in the standard ToolResult
                        if text_result.get("status") == "error":
                            return {
                                "type": "tool_result",
                                "tool_use_id": tool_id,
                                "name": tool_name,
                                "content": text_result.get("message", "Tool execution failed."),
                                "is_error": True
                            }
                    
                    # Cache meta results
                    if tool_name == "search_tools_by_keywords" and session_id:
                        try:
                            meta_result = {}
                            if isinstance(text_result, dict):
                                meta_result = text_result
                            elif isinstance(text_result, str):
                                try:
                                    meta_result = json.loads(text_result)
                                except (json.JSONDecodeError, TypeError):
                                    meta_result = {}
                            
                            extracted_tools = self._extract_tools_from_meta_result(meta_result)
                            if extracted_tools:
                                self._cache_tools_for_session(session_id, extracted_tools)

                        except Exception as e:
                            if debug:
                                print(f"[DEBUG] Failed to cache tools from meta result: {e}")
                    
                    return content_for_llm
                    
            except Exception as e:
                if debug:
                    print(f"Error calling meta tool {tool_name}: {str(e)}")
                return {
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "name": tool_name,
                    "content": f"Error: Meta tool execution failed - {str(e)}",
                    "is_error": True
                }

        # 2. Refactored normal tool handling
        try:
            mcp_client = self._get_mcp_client(session_id)
            async with mcp_client as mcp_async_client:
                # Inject session_id if present
                if session_id:
                    try:
                        params = CallToolRequestParams(
                            name=tool_name,
                            arguments=tool_args,
                            **{"_meta": {"client_id": session_id}},
                        )
                        call_req = ClientRequest(CallToolRequest(method="tools/call", params=params))
                        result_obj = await mcp_async_client.session.send_request(
                            call_req,
                            CallToolResult,
                        )
                    except Exception:
                        result_obj = await mcp_async_client.call_tool(tool_name, tool_args)
                else:
                    result_obj = await mcp_async_client.call_tool(tool_name, tool_args)

            # Extract the dict from ToolResult.model_dump()
            tool_output = extract_text_from_mcp_result(result_obj)

            # Default content for LLM is the whole output, for backward compatibility
            content_for_llm = tool_output

            if isinstance(tool_output, dict):
                # If it's our standard ToolResult, extract the specific llm_content part
                if 'llm_content' in tool_output:
                    content_for_llm = tool_output['llm_content']
                
                # Check for error status in the standard ToolResult
                if tool_output.get("status") == "error":
                    return {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "name": tool_name,
                        "content": tool_output.get("message", "Tool execution failed."),
                        "is_error": True
                    }
            
            return content_for_llm

        except Exception as e:
            if debug:
                print(f"Error calling tool {tool_name}: {str(e)}")
            return {
                "type": "tool_result",
                "tool_use_id": tool_id,
                "name": tool_name,
                "content": f"Error: Tool execution failed - {str(e)}",
                "is_error": True
            }

    async def generate_text_to_image_prompt(self, session_id: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Generate a high-quality text-to-image prompt using the Gemini API.
        This method uses a specialized system prompt to create detailed and effective prompts for image generation
        based on the recent conversation context.
        Args:
            session_id: Optional session ID to get the latest conversation context
        Returns:
            Optional[Dict[str, str]]: A dictionary containing the text prompt and negative prompt, or None if generation fails
        """
        debug = self.extra_config.get('debug', False)
        try:
            system_prompt = get_text_to_image_config().get("text_to_image_system_prompt", "You are a professional prompt engineer. Please generate a detailed and creative text-to-image prompt based on the following conversation. The prompt should be suitable for high-quality image generation.")
            
            # 获取n的配置
            n = get_text_to_image_config().get("context_message_count", 4)
            # 获取最新的对话消息
            latest_messages = get_latest_n_messages(session_id, n) if session_id else tuple([None]*n)
            if not any(latest_messages):
                error_msg = f"Missing conversation context for session {session_id}"
                if debug:
                    print(f"[text_to_image] Error: {error_msg}")
                return None
            
            # 构造消息序列
            messages = []
            # 拼接n条消息内容
            conversation_text = "Please generate text to image prompt based on the following conversation:\n\n"
            for msg in latest_messages:
                if msg is not None:
                    conversation_text += f"{msg.role}: {msg.content}\n"
            messages.append(UserMessage(role="user", content=conversation_text))
            
            # 使用相同的消息格式转换逻辑
            contents = self._format_messages_for_gemini(messages)
            if debug:
                print("\n[text_to_image] Messages for prompt generation:")
                import pprint; pprint.pprint(messages)
                print("[text_to_image] Formatted contents:")
                pprint.pprint(contents)
            
            safety_settings = self.safety_settings
            prompt_config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                safety_settings=safety_settings,
                temperature=1.0,
                max_output_tokens=self.extra_config.get('max_output_tokens', 1024)
            )
            if debug:
                print("\n[Gemini][text_to_image] System prompt:")
                print(system_prompt)
                print("[Gemini][text_to_image] Prompt config:")
                pprint.pprint(prompt_config)
            
            response = self.client.models.generate_content(
                model=self.extra_config.get("model_for_text_to_image", "gemini-1.5-pro-latest"),
                contents=contents,
                config=prompt_config
            )

            if hasattr(response, 'candidates') and response.candidates and response.candidates[0].content.parts:
                prompt_text = response.candidates[0].content.parts[0].text
                text_prompt_match = re.search(r'<text_to_image_prompt>(.*?)</text_to_image_prompt>', prompt_text, re.DOTALL)
                negative_prompt_match = re.search(r'<negative_prompt>(.*?)</negative_prompt>', prompt_text, re.DOTALL)
                if not text_prompt_match:
                    if debug:
                        print(f"[text_to_image] Error: Failed to extract text prompt from response\nFull prompt text: {prompt_text}")
                    return None
                text_prompt = text_prompt_match.group(1).strip()
                negative_prompt = negative_prompt_match.group(1).strip() if negative_prompt_match else "blurry, low quality, distorted, extra limbs, bad anatomy, text, watermark, ugly"
                if not text_prompt:
                    if debug:
                        print(f"[text_to_image] Error: Extracted text prompt is empty")
                    return None

                # 获取默认关键词
                text_to_image_config = get_text_to_image_config()
                default_positive_prompt = text_to_image_config.get("default_positive_prompt", "")
                default_negative_prompt = text_to_image_config.get("default_negative_prompt", "")

                # 检查并补充默认关键词
                if default_positive_prompt:
                    # 用逗号分隔关键词
                    default_keywords = default_positive_prompt.split(",")
                    existing_keywords = text_prompt.split(",")
                    # 找出缺失的关键词
                    missing_keywords = [kw for kw in default_keywords if kw.strip() and kw.strip() not in [ek.strip() for ek in existing_keywords]]
                    if missing_keywords:
                        # 清理原始提示词
                        text_prompt = text_prompt.strip().lstrip(",").strip()
                        # 用逗号连接所有关键词
                        text_prompt = ", ".join(missing_keywords) + (", " + text_prompt if text_prompt else "")

                if default_negative_prompt:
                    # 用逗号分隔关键词
                    default_keywords = default_negative_prompt.split(",")
                    existing_keywords = negative_prompt.split(",")
                    # 找出缺失的关键词
                    missing_keywords = [kw for kw in default_keywords if kw.strip() and kw.strip() not in [ek.strip() for ek in existing_keywords]]
                    if missing_keywords:
                        # 清理原始提示词
                        negative_prompt = negative_prompt.strip().lstrip(",").strip()
                        # 用逗号连接所有关键词，确保没有前导空格
                        negative_prompt = ", ".join(missing_keywords) + (", " + negative_prompt.lstrip() if negative_prompt else "")

                if debug:
                    print(f"[Gemini][text_to_image] Final text_prompt: {text_prompt}")
                    print(f"[Gemini][text_to_image] Final negative_prompt: {negative_prompt}")
                return {
                    "text_prompt": text_prompt,
                    "negative_prompt": negative_prompt
                }
            return None
        except Exception as e:
            if debug:
                print(f"[text_to_image] Error during prompt generation: {str(e)}")
            return None

    def _sanitize_jsonschema(self, schema: dict) -> dict:  # pylint: disable=dangerous-default-value
        """Recursively strip unsupported keys from a JSON schema for Gemini.

        Gemini function-call schema currently supports only a subset of draft-7
        JSON Schema keywords (type / properties / required / description / enum /
        items / default / title).  Any additional keys like *exclusiveMinimum* will
        lead to strict validation errors when instantiating
        :class:`google.ai.generativeai.types.Tool`.

        This helper keeps only the allowed keys and removes everything else.
        """

        ALLOWED_KEYS = {
            "type",
            "properties",
            "required",
            "description",
            "enum",
            "items",
            "default",
            "title",
        }

        if not isinstance(schema, dict):
            return schema

        cleaned: dict = {}
        for key, value in schema.items():
            if key not in ALLOWED_KEYS:
                # Skip unsupported keyword (e.g. exclusiveMinimum, pattern, etc.)
                continue

            if key == "properties":
                cleaned["properties"] = {
                    prop_name: self._sanitize_jsonschema(prop_schema)
                    for prop_name, prop_schema in value.items()
                    if isinstance(prop_schema, dict)
                }
            elif key == "items":
                cleaned["items"] = self._sanitize_jsonschema(value)
            else:
                cleaned[key] = value

        # If this node represents an *object* and required is missing, infer it
        if cleaned.get("type") == "object" and "required" not in cleaned and "properties" in cleaned:
            cleaned["required"] = list(cleaned["properties"].keys())

        return cleaned





