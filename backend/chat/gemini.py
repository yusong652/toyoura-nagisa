import os
import re
import httpx
from typing import List, Tuple, Optional, Dict, Any
from google import genai
from google.genai import types
from backend.config import get_llm_specific_config
from backend.chat.base import LLMClientBase
from backend.chat.models import Message, ResponseType, LLMResponse
from backend.chat.utils import parse_llm_output
from fastmcp import Client as MCPClient

class GeminiClient(LLMClientBase):
    """
    Google Gemini 客户端实现。
    继承自 LLMClientBase，实现具体的 API 调用逻辑。
    """
    
    def __init__(self, api_key: str, system_prompt: Optional[str] = None, **kwargs):
        """
        初始化 Gemini 客户端。
        Args:
            api_key: Google API key。
            system_prompt: 可选，覆盖初始化时的 system prompt。
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
            topP=self.extra_config.get('top_p', 0.95),
            topK=self.extra_config.get('top_k', 40),
            max_output_tokens=self.extra_config.get('max_output_tokens', 500)
        )
        
        print(f"Gemini Client initialized.")
        # 集成 MCPClient
        self.mcp_client = MCPClient("nagisa_mcp/fast_mcp_server.py")


    def map_role(self, role: str) -> str:
        if role == "assistant":
            return "model"
        return "user"

    async def get_response(self, messages: List[Message], **kwargs) -> LLMResponse:
        # 1. 获取 MCP 工具 schema
        tool_schemas = await self.get_function_call_schemas()
        print(f"[DEBUG] tool_schemas in get_response: {tool_schemas}")

        # 2. 构造 Gemini API payload，注册 tools
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

        try:
            response = self.client.models.generate_content(
                model=self.extra_config.get('model', "gemini-2.0-flash-lite"),
                contents=contents,
                config=config
            )
            print(f"[DEBUG] Gemini response: {response}")
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                # 遍历所有 parts，优先处理 function_call
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts') and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, 'function_call') and part.function_call:
                            tool_call = part.function_call
                            tool_result = await self.handle_function_call({
                                "name": tool_call.name,
                                "arguments": tool_call.args if hasattr(tool_call, 'args') else tool_call.arguments
                            })
                            return LLMResponse(
                                content=str(tool_result),
                                response_type=ResponseType.FUNCTION_CALL,
                                function_name=tool_call.name,
                                function_args=tool_call.args if hasattr(tool_call, 'args') else tool_call.arguments,
                                function_result=tool_result
                            )
                    # 如果没有 function_call，找第一个有 text 的 part
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text:
                            response_text = part.text
                            response_text, keyword = parse_llm_output(response_text)
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
        first_user_message: Message,
        first_assistant_message: Message,
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
                Message(role="user", content=[{"type": "text", "text": "请为上面对话生成标题"}])
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
                "parameters": getattr(tool, "inputSchema", {"type": "object", "properties": {}})
            }
            for tool in mcp_tools
        ]
        tools = types.Tool(function_declarations=function_declarations)
        print(f"[DEBUG] Gemini function_declarations: {function_declarations}")
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

    async def handle_function_call_closed_loop(
        self,
        messages: List[Message],
        tool_call: dict,
        tool_result: Any,
        **kwargs
    ) -> LLMResponse:
        """
        Gemini function call闭环：
        1. 将function_call和其结果作为新对话轮次加入contents
        2. 再次调用Gemini，获得最终自然语言回复
        """
        tool_schemas = await self.get_function_call_schemas()
        print(f"[DEBUG] tool_schemas in handle_function_call_closed_loop: {tool_schemas}")
        # 1. 先把原始messages转为contents
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
            mapped_role = self.map_role(msg.role)
            contents.append({"role": mapped_role, "parts": parts})

        # 2. 构造function_call和function_response part
        function_call_part = types.Part(function_call=types.FunctionCall(
            name=tool_call['name'],
            args=tool_call.get('arguments', {})
        ))
        function_response_part = types.Part.from_function_response(
            name=tool_call['name'],
            response={"result": tool_result}
        )
        # 3. 按Gemini推荐方式追加两轮
        contents.append(types.Content(role="model", parts=[function_call_part]))
        contents.append(types.Content(role="user", parts=[function_response_part]))

        config = types.GenerateContentConfig(
            system_instruction=self.system_prompt,
            safety_settings=self.safety_settings,
            temperature=self.extra_config.get('temperature', 1.2),
            max_output_tokens=self.extra_config.get('max_output_tokens', 500),
            tools=tool_schemas
        )
        # 4. 再次请求LLM
        try:
            response = self.client.models.generate_content(
                model=self.extra_config.get('model', "gemini-2.0-flash-lite"),
                contents=contents,
                config=config
            )
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts') and candidate.content.parts:
                    response_text = candidate.content.parts[0].text
                    response_text, keyword = parse_llm_output(response_text)
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
            print(f"Gemini闭环API error: {e}")
            return LLMResponse(
                content=str(e),
                response_type=ResponseType.ERROR
            )