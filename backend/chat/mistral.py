import os
from typing import List, Tuple, Optional, Dict, Any
import httpx
import json
from backend.chat.base import LLMClientBase
from backend.chat.models import Message, LLMResponse, ResponseType, UserToolMessage, BaseMessage, UserMessage
from backend.chat.utils import parse_llm_output
import re
import mistralai
from fastmcp import Client as MCPClient
import random
import string

class MistralClient(LLMClientBase):
    """
    Mistral 客户端实现。
    继承自 LLMClientBase，实现具体的 API 调用逻辑。
    """
    
    def __init__(self, api_key: str, system_prompt: Optional[str] = None, mcp_client=None, **kwargs):
        """
        初始化 Mistral 客户端。
        Args:
            api_key: Mistral API key。
            system_prompt: 可选，覆盖初始化时的 system prompt。
            mcp_client: 可选，用于 in-process tool calls via app.state.mcp
        """
        super().__init__(system_prompt, **kwargs)
        self.api_key = api_key
        self.base_url = "https://api.mistral.ai/v1"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        self.mistral_client = mistralai.Mistral(api_key=self.api_key)
        self.mcp_client = mcp_client if mcp_client is not None else MCPClient("nagisa_mcp/fast_mcp_server.py")
        print(f"MistralClient initialized.")

    def _format_messages_for_mistral(self, messages: List[BaseMessage], system_prompt: Optional[str] = None) -> Tuple[List[Dict[str, Any]], bool]:
        messages_for_llm = [
            {"role": "system", "content": [{
                "type": "text",
                "text": system_prompt if system_prompt is not None else self.system_prompt
            }]}
        ]
        has_image = False
        for msg in messages:
            if msg.role == "assistant" and getattr(msg, "tool_calls", None):
                messages_for_llm.append({
                    "role": "assistant",
                    "content": "",  # 必须为空字符串
                    "tool_calls": msg.tool_calls
                })
                continue
            # 修正：识别 UserToolMessage（工具响应，role 仍为 user，但有 tool_request 字段）
            if isinstance(msg, UserToolMessage) or hasattr(msg, "tool_request"):
                messages_for_llm.append({
                    "role": "tool",
                    "tool_call_id": getattr(msg, "id", None),
                    "name": getattr(msg, "tool_request", {}).get("name", None),
                    "content": msg.content
                })
                continue
            if isinstance(msg.content, list):
                mistral_content = []
                has_text = False
                for c in msg.content:
                    if isinstance(c, dict):
                        if "type" in c and c["type"] == "text" and "text" in c:
                            mistral_content.append({
                                "type": "text",
                                "text": c["text"]
                            })
                            has_text = True
                        elif "text" in c and "type" not in c:
                            mistral_content.append({
                                "type": "text",
                                "text": c["text"]
                            })
                            has_text = True
                        elif "inline_data" in c:
                            mime = c["inline_data"].get("mime_type", "image/png")
                            data = c["inline_data"]["data"]
                            mistral_content.append({
                                "type": "image_url",
                                "image_url": f"data:{mime};base64,{data}"
                            })
                            has_image = True
                        elif "type" in c and c["type"] == "image_url" and "image_url" in c:
                            mistral_content.append({
                                "type": "image_url",
                                "image_url": c["image_url"]
                            })
                            has_image = True
                        else:
                            text = str(c.get("text", ""))
                            mistral_content.append({
                                "type": "text",
                                "text": text
                            })
                            has_text = True
                    else:
                        mistral_content.append({
                            "type": "text",
                            "text": str(c)
                        })
                        has_text = True
                if has_image and not has_text:
                    mistral_content.insert(0, {
                        "type": "text",
                        "text": ""
                    })
                messages_for_llm.append({
                    "role": msg.role,
                    "content": mistral_content
                })
            else:
                messages_for_llm.append({
                    "role": msg.role, 
                    "content": str(msg.content)
                })
        return messages_for_llm, has_image

    async def get_response(
        self,
        messages: List[BaseMessage],
        **kwargs
    ) -> 'LLMResponse':
        """
        调用 Mistral API，返回 LLMResponse。
        """
        messages_for_llm, has_image = self._format_messages_for_mistral(messages)
        print("\n========== Mistral API 请求消息格式 ==========")
        import pprint; pprint.pprint(messages_for_llm)
        print("========== END ==========")
        model = self.extra_config.get("model", "mistral-large-latest")
        # 自动获取 tools
        tools = await self.get_function_call_schemas()
        try:
            response = await self.mistral_client.chat.complete_async(
                model=model,
                messages=messages_for_llm,
                temperature=self.extra_config.get("temperature", 0.7),
                max_tokens=self.extra_config.get("max_tokens", 1024),
                tools=tools if tools else None,
                tool_choice="auto",
                parallel_tool_calls=False
            )
            if response.choices and hasattr(response.choices[0].message, "tool_calls") and response.choices[0].message.tool_calls:
                tool_call = response.choices[0].message.tool_calls[0]
                function_name = tool_call.function.name
                import json as _json
                arguments = tool_call.function.arguments
                tool_call_id = tool_call.id
                try:
                    function_args = _json.loads(arguments) if isinstance(arguments, str) else arguments
                except Exception:
                    function_args = arguments
                natural_content = response.choices[0].message.content if hasattr(response.choices[0].message, "content") else ""
                return LLMResponse(
                    content=natural_content or "",
                    response_type=ResponseType.FUNCTION_CALL,
                    function_name=function_name,
                    function_args=function_args,
                    function_result=None,
                    function_call_id=tool_call_id
                )
            llm_reply = response.choices[0].message.content
            response_text, keyword = parse_llm_output(llm_reply)
            return LLMResponse(
                content=response_text,
                response_type=ResponseType.TEXT,
                keyword=keyword
            )
        except Exception as e:
            return LLMResponse(
                content=f"Mistral SDK error: {str(e)}",
                response_type=ResponseType.ERROR
            )

    async def generate_title_from_messages(
        self,
        first_user_message: BaseMessage,
        first_assistant_message: BaseMessage,
        title_generation_system_prompt: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate a concise conversation title using the Mistral API.
        支持多模态 content。
        
        Args:
            first_user_message: Message object containing the first user message
            first_assistant_message: Message object containing the first assistant message
            title_generation_system_prompt: Optional custom system prompt for title generation
        """
        try:
            # 优先用title_generation_system_prompt，否则用self.system_prompt
            system_prompt = title_generation_system_prompt if title_generation_system_prompt is not None else self.system_prompt
            # 构造消息序列，最后一条为user
            messages = [
                first_user_message,
                first_assistant_message,
                UserMessage(role="user", content=[{"type": "text", "text": "请为上面对话生成标题"}])
            ]
            messages_for_llm, has_image = self._format_messages_for_mistral(
                messages,
                system_prompt=system_prompt
            )
            model = self.extra_config.get("model", "pixtral-large-2411")
            payload = {
                "model": model,
                "messages": messages_for_llm,
                "temperature": self.extra_config.get("temperature", 1.0),
                "max_tokens": 100,
                "stream": False
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
            print(f"Mistral生成标题时出错: {str(e)}")
            return None 

    async def get_function_call_schemas(self):
        """
        获取所有 MCP 工具的 schema，供 LLM function call 注册用，返回 Mistral tools 格式列表
        """
        async with self.mcp_client as mcp_async_client:
            mcp_tools = await mcp_async_client.list_tools()
        tools = []
        for tool in mcp_tools:
            params = getattr(tool, "inputSchema", {"type": "object", "properties": {}})
            # 自动补全 required 字段
            if "properties" in params:
                params["required"] = list(params["properties"].keys())
                # 确保每个参数有 description
                for k, v in params["properties"].items():
                    if "description" not in v or not v["description"]:
                        v["description"] = f"{k} parameter"
            if "type" not in params:
                params["type"] = "object"
            if "additionalProperties" not in params:
                params["additionalProperties"] = False
            tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": getattr(tool, "description", tool.name),
                    "parameters": params
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