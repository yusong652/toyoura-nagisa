import os
import re
import json 
from typing import List, Tuple, Optional, Dict, Any
import httpx
from backend.chat.base import LLMClientBase
from backend.chat.models import Message, LLMResponse, ResponseType, UserToolMessage, BaseMessage, UserMessage
from backend.chat.utils import parse_llm_output
from fastmcp import Client as MCPClient
from openai import OpenAI

class GPTClient(LLMClientBase):
    """
    GPT 客户端实现。
    继承自 LLMClientBase，实现具体的 API 调用逻辑。
    """
    
    def __init__(self, api_key: str, system_prompt: Optional[str] = None, mcp_client=None, **kwargs):
        """
        初始化 GPT 客户端。
        Args:
            api_key: OpenAI API key。
            system_prompt: 可选，覆盖初始化时的 system prompt。
            mcp_client: 可选，MCPClient实例，用于直接调用MCP工具。
        """
        super().__init__(system_prompt, **kwargs)
        self.api_key = api_key
        self.base_url = "https://api.openai.com/v1"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        print(f"ChatGPTClient initialized.")
        from fastmcp import Client as MCPClient
        self.mcp_client = mcp_client if mcp_client is not None else MCPClient("nagisa_mcp/fast_mcp_server.py")
        self.openai_client = OpenAI(api_key=self.api_key)

    def _format_messages_for_openai(self, messages: List[BaseMessage], system_prompt: Optional[str] = None) -> Tuple[List[Dict[str, Any]], bool]:
        """
        将内部消息格式转换为OpenAI API所需的格式。
        Args:
            messages: 内部消息列表
            system_prompt: 可选，覆盖默认的 system prompt
        Returns:
            Tuple[List[Dict], bool]: 格式化后的消息列表和是否包含图片的标志
        """
        messages_for_llm = [
            {"role": "system", "content": system_prompt if system_prompt is not None else self.system_prompt}
        ]
        has_image = False
        for msg in messages:
            if msg.role == "assistant" and getattr(msg, "tool_calls", None):
                messages_for_llm.append({
                    "role": msg.role,
                    "content": msg.content,
                    "tool_calls": msg.tool_calls
                })
                continue
            if isinstance(msg, UserToolMessage) or hasattr(msg, "tool_request"):
                messages_for_llm.append({
                    "role": "tool",
                    "content": msg.content,
                    "tool_call_id": getattr(msg, "id", None)
                })
                continue
            if isinstance(msg.content, list):
                openai_content = []
                for c in msg.content:
                    if isinstance(c, dict):
                        if "text" in c and "type" not in c:
                            openai_content.append({"type": "text", "text": c["text"]})
                        elif "inline_data" in c:
                            mime = c["inline_data"].get("mime_type", "image/png")
                            data = c["inline_data"]["data"]
                            openai_content.append({
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime};base64,{data}"}
                            })
                            has_image = True
                        elif c.get("type") == "image_url":
                            openai_content.append(c)
                            has_image = True
                        elif c.get("type") == "text":
                            openai_content.append(c)
                        else:
                            openai_content.append(c)
                    else:
                        openai_content.append(c)
                messages_for_llm.append({"role": msg.role, "content": openai_content})
            else:
                if isinstance(msg.content, list):
                    text = "".join(str(c.get("text", "")) if isinstance(c, dict) else str(c) for c in msg.content)
                else:
                    text = str(msg.content)
                messages_for_llm.append({"role": msg.role, "content": text})
        return messages_for_llm, has_image

    async def get_response(
        self,
        messages: List[BaseMessage],
        **kwargs
    ) -> 'LLMResponse':
        messages_for_llm, has_image = self._format_messages_for_openai(messages)
        # print("\n========== OpenAI API 请求消息格式 ==========")
        # import pprint; pprint.pprint(messages_for_llm)
        # print("========== END ==========")
        model = "gpt-4.1" if has_image else self.extra_config.get("model", "gpt-4.1-mini")
        payload = {
            "model": model,
            "messages": messages_for_llm,
            "temperature": self.extra_config.get("temperature", 1.2)
        }
        # 自动获取 tools
        tools = await self.get_function_call_schemas()
        if tools:
            payload["tools"] = tools
        try:
            response = self.openai_client.chat.completions.create(
                model=payload["model"],
                messages=payload["messages"],
                temperature=payload["temperature"],
                tools=payload.get("tools")
            )
            if not response.choices:
                raise ValueError("No choices in OpenAI response")
            choice = response.choices[0].message
            if hasattr(choice, "tool_calls") and choice.tool_calls:
                tool_call = choice.tool_calls[0]
                function_name = tool_call.function.name
                arguments = tool_call.function.arguments
                tool_call_id = tool_call.id
                try:
                    function_args = json.loads(arguments) if isinstance(arguments, str) else arguments
                except Exception:
                    function_args = arguments
                return LLMResponse(
                    content=choice.content,
                    response_type=ResponseType.FUNCTION_CALL,
                    function_name=function_name,
                    function_args=function_args,
                    function_result=None,
                    function_call_id=tool_call_id
                )
            llm_reply = choice.content
            response_text, keyword = parse_llm_output(llm_reply)
            return LLMResponse(
                content=response_text,
                response_type=ResponseType.TEXT,
                keyword=keyword
            )
        except Exception as e:
            print("OpenAI SDK error:", e)
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
        try:
            # 构造消息序列，最后一条为user
            messages = [
                first_user_message,
                first_assistant_message,
                UserMessage(role="user", content=[{"type": "text", "text": "请为上面对话生成标题"}])
            ]
            
            messages_for_llm, has_image = self._format_messages_for_openai(
                messages,
                system_prompt=title_generation_system_prompt
            )
            model = 'gpt-4.1' if has_image else self.extra_config.get("model", "gpt-4.1-mini")
            payload = {
                "model": model,
                "messages": messages_for_llm,
                "temperature": 2.0
            }
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                response_data = response.json()
                if not response_data.get("choices"):
                    return None
                title_response_text = response_data["choices"][0]["message"]["content"]
                title_match = re.search(r'<title>(.*?)</title>', title_response_text, re.DOTALL)
                if title_match:
                    title = title_match.group(1).strip()
                    if not title:
                        return None
                    if len(title) > 30:
                        title = title[:30]
                    return title
                cleaned_title = title_response_text.strip().strip('"\'').strip()
                if cleaned_title and len(cleaned_title) <= 30:
                    return cleaned_title
                return None
        except Exception as e:
            print(f"GPT生成标题时出错: {str(e)}")
            return None

    async def get_function_call_schemas(self):
        """
        获取所有 MCP 工具的 schema，供 LLM function call 注册用，返回 OpenAI tools 格式列表
        """
        async with self.mcp_client as mcp_async_client:
            mcp_tools = await mcp_async_client.list_tools()
        tools = []
        for tool in mcp_tools:
            params = getattr(tool, "inputSchema", {"type": "object", "properties": {}})
            # 自动补全 required 字段
            if "properties" in params:
                params["required"] = list(params["properties"].keys())
            if "additionalProperties" not in params:
                params["additionalProperties"] = False
            tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": getattr(tool, "description", ""),
                    "parameters": params,
                    "strict": True
                }
            })
        return tools

    async def handle_function_call(self, function_call: dict):
        """
        处理 LLM 生成的 function_call 请求，自动分发到 MCP 工具
        function_call: 形如 {"name": "search_weather", "arguments": {"city": "北京"}}
        """
        tool_name = function_call["name"]
        params = function_call.get("arguments", {})
        async with self.mcp_client as mcp_async_client:
            return await mcp_async_client.call_tool(tool_name, params)