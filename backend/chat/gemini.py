import os
import re
import httpx
import json
from typing import List, Tuple, Optional, Dict, Any
from google import genai
from google.genai import types
from backend.config import get_llm_specific_config
from backend.chat.base import LLMClientBase
from backend.chat.models import Message, ResponseType, LLMResponse, UserToolMessage, BaseMessage, UserMessage
from backend.chat.utils import parse_llm_output
from fastmcp import Client as MCPClient

class GeminiClient(LLMClientBase):
    """
    Google Gemini 客户端实现。
    继承自 LLMClientBase，实现具体的 API 调用逻辑。
    """
    
    def __init__(self, api_key: str, system_prompt: Optional[str] = None, mcp_client=None, **kwargs):
        """
        初始化 Gemini 客户端。
        Args:
            api_key: Google API key。
            system_prompt: 可选，覆盖初始化时的 system prompt。
            mcp_client: 可选，用于替换默认的 MCPClient。
        """
        super().__init__(system_prompt, **kwargs)
        self.api_key = api_key
        self.client = genai.Client(api_key=self.api_key)
        self.safety_settings = [
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=types.HarmBlockThreshold.BLOCK_NONE
            )
        ]
        
        # 初始化配置
        self.config = types.GenerateContentConfig(
            system_instruction=self.system_prompt,
            safety_settings=self.safety_settings,
            temperature=self.extra_config.get('temperature', 1.2),
            max_output_tokens=self.extra_config.get('max_output_tokens', 500)
        )
        
        print(f"Gemini Client initialized.")
        # 集成 MCPClient
        self.mcp_client = mcp_client if mcp_client is not None else MCPClient("nagisa_mcp/fast_mcp_server.py")


    def map_role(self, role: str) -> str:
        if role == "assistant":
            return "model"
        return "user"

    async def get_response(self, messages: List[BaseMessage], **kwargs) -> LLMResponse:
        # 1. 获取 MCP 工具 schema
        tool_schemas = await self.get_function_call_schemas()

        # 2. 构造 Gemini API payload，注册 tools
        contents = []
        for msg in messages:
            # Gemini function call标准：
            # - assistant function_call消息用model+function_call结构
            # - tool响应用user+function_response结构
            if msg.role == "assistant" and getattr(msg, "tool_calls", None):
                # function_call消息
                parts = []
                for tool_call in msg.tool_calls:
                    arguments = tool_call["function"].get("arguments", {})
                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except Exception:
                            arguments = {}
                    parts.append(types.Part(function_call=types.FunctionCall(
                        name=tool_call["function"]["name"],
                        args=arguments,
                        id=tool_call.get("id", tool_call["function"]["name"])  # 使用工具调用ID或函数名作为ID
                    )))
                contents.append({"role": "model", "parts": parts})
                continue
            # 修正：识别 UserToolMessage（工具响应，role 仍为 user，但有 tool_request 字段）
            if isinstance(msg, UserToolMessage) or hasattr(msg, "tool_request"):
                tool_name = getattr(msg, "tool_request", {}).get("name", "")
                if not tool_name and hasattr(msg, "name"):
                    tool_name = msg.name
                if not tool_name:
                    print(f"[WARNING] Tool response missing name: {msg}")
                    continue

                # 解析工具响应内容，确保是结构化数据
                try:
                    # 首先尝试直接获取内容
                    if isinstance(msg.content, str):
                        response_data = json.loads(msg.content)
                    else:
                        response_data = msg.content

                    # 处理 TextContent 对象
                    if hasattr(response_data, 'text'):
                        try:
                            # 如果 text 是 JSON 字符串，解析它
                            response_data = json.loads(response_data.text)
                        except:
                            # 如果不是 JSON，直接使用文本
                            response_data = {"result": response_data.text}
                    # 处理包含 TextContent 的列表
                    elif isinstance(response_data, list) and len(response_data) > 0:
                        if hasattr(response_data[0], 'text'):
                            try:
                                # 如果 text 是 JSON 字符串，解析它
                                response_data = json.loads(response_data[0].text)
                            except:
                                # 如果不是 JSON，直接使用文本
                                response_data = {"result": response_data[0].text}
                        else:
                            # 如果列表中的元素不是 TextContent，尝试直接使用
                            response_data = response_data[0]
                    # 如果响应是字典且包含 result 字段，且 result 是字符串
                    elif isinstance(response_data, dict) and 'result' in response_data and isinstance(response_data['result'], str):
                        try:
                            # 尝试解析 result 字段中的 JSON 字符串
                            response_data = json.loads(response_data['result'])
                        except:
                            # 如果解析失败，保持原样
                            pass

                except Exception as e:
                    print(f"[WARNING] Failed to parse tool response: {e}")
                    response_data = {"result": str(msg.content)}

                # 创建工具响应，直接使用结构化数据
                function_response = {
                    "functionResponse": {
                        "name": tool_name,
                        "response": response_data
                    }
                }
                
                # 检查是否已经有工具响应消息
                if contents and contents[-1]["role"] == "user" and any(
                    "functionResponse" in part for part in contents[-1]["parts"]
                ):
                    # 添加到现有的工具响应消息中
                    contents[-1]["parts"].append(function_response)
                else:
                    # 创建新的工具响应消息
                    contents.append({
                        "role": "user",
                        "parts": [function_response]
                    })
                continue
            # 普通消息
            parts = []
            if isinstance(msg.content, list):
                for item in msg.content:
                    if "text" in item:
                        parts.append({"text": item['text']})
                    elif "inline_data" in item:
                        parts.append({
                            "inline_data": {
                                "mime_type": item['inline_data'].get('mime_type', 'image/png'),
                                "data": item['inline_data']['data']
                            }
                        })
            else:
                parts.append({"text": msg.content})
            mapped_role = self.map_role(msg.role)
            contents.append({"role": mapped_role, "parts": parts})
        
        # 动态构造 config，把 tools 放进去
        config = types.GenerateContentConfig(
            system_instruction=self.system_prompt,
            safety_settings=self.safety_settings,
            temperature=self.extra_config.get('temperature', 1.2),
            max_output_tokens=self.extra_config.get('max_output_tokens', 1024),
            tools=tool_schemas
        )

        # 只保留一个调试信息块，由 config debug 控制
        if self.extra_config.get('debug', False):
            print("\n========== Gemini API 请求消息格式 ==========")
            print("Payload:")
            import pprint; pprint.pprint({
                "model": self.extra_config.get('model', "gemini-2.0-flash-lite"),
                "contents": contents,
                "config": {
                    "system_instruction": self.system_prompt,
                    "temperature": self.extra_config.get('temperature', 1.2),
                    "max_output_tokens": self.extra_config.get('max_output_tokens', 1024),
                    "tools": tool_schemas
                }
            })
            print("========== END ==========")

        try:
            response = self.client.models.generate_content(
                model=self.extra_config.get('model', "gemini-2.0-flash-lite"),
                contents=contents,
                config=config
            )
            
            if self.extra_config.get('debug', False):
                print("\n========== Gemini API 响应格式 ==========")
                if hasattr(response, 'candidates') and response.candidates:
                    print("Response parts:")
                    import pprint; pprint.pprint(response.candidates[0].content.parts)
                print("========== END ==========")

            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                # 遍历所有 parts，处理所有 function_call
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts') and candidate.content.parts:
                    natural_content = ""
                    tool_calls = []
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text:
                            natural_content = part.text  # 记录 function_call 前的自然语言内容
                        elif hasattr(part, 'function_call') and part.function_call:
                            tool_calls.append({
                                'name': part.function_call.name,
                                'arguments': part.function_call.args if hasattr(part.function_call, 'args') else part.function_call.arguments,
                                'id': part.function_call.id or part.function_call.name  # 使用工具调用ID或函数名
                            })
                    
                    if tool_calls:
                        return LLMResponse(
                            content=natural_content,  # 优先用自然语言内容
                            response_type=ResponseType.FUNCTION_CALL,
                            tool_calls=tool_calls
                        )
                    
                    # 如果没有 function_call，返回文本响应
                    if natural_content:
                        response_text, keyword = parse_llm_output(natural_content)
                        return LLMResponse(
                            content=response_text,
                            response_type=ResponseType.TEXT,
                            keyword=keyword
                        )
            return LLMResponse(
                content="",
                response_type=ResponseType.ERROR
            )
        except Exception as e:
            print(f"Gemini API error: {e}")
            return LLMResponse(
                content=str(e),
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
                            parts.append({"text": item['text']})
                        elif "inline_data" in item:
                            parts.append({
                                "inline_data": {
                                    "mime_type": item['inline_data'].get('mime_type', 'image/png'),
                                    "data": item['inline_data']['data']
                                }
                            })
                else:
                    parts.append({"text": msg.content})
                # 使用 map_role 函数转换角色名称
                mapped_role = self.map_role(msg.role)
                contents.append({"role": mapped_role, "parts": parts})
            
            response = self.client.models.generate_content(
                model=self.extra_config.get('model', "gemini-2.0-flash-lite"),
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

    async def get_function_call_schemas(self):
        """
        获取所有 MCP 工具的 schema，供 LLM function call 注册用，返回 Gemini Tool 对象列表
        """
        async with self.mcp_client as mcp_async_client:
            mcp_tools = await mcp_async_client.list_tools()
        function_declarations = [
            {
                "name": tool.name,
                "description": getattr(tool, "description", ""),
                "parameters": (lambda params: (params.update({"required": list(params["properties"].keys())}) if "properties" in params else None, params)[-1])(getattr(tool, "inputSchema", {"type": "object", "properties": {}}))
            }
            for tool in mcp_tools
        ]
        tools = types.Tool(function_declarations=function_declarations)
        return [tools]

    async def handle_function_call(self, function_call: dict):
        """
        处理 LLM 生成的 function_call 请求，自动分发到 MCP 工具
        function_call: 形如 {"name": "search_weather", "arguments": {"city": "北京"}}
        """
        tool_name = function_call["name"]
        params = function_call.get("arguments", {})
        async with self.mcp_client as mcp_async_client:
            return await mcp_async_client.call_tool(tool_name, params)