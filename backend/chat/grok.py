import os
import re
import json
from typing import List, Tuple, Optional, Dict, Any
from openai import OpenAI
from backend.chat.base import LLMClientBase
from backend.chat.models import Message, LLMResponse, ResponseType, UserToolMessage, BaseMessage, UserMessage
from backend.chat.utils import parse_llm_output
from fastmcp import Client as MCPClient

class GrokClient(LLMClientBase):
    """
    Grok 客户端实现（基于 OpenAI SDK）。
    """
    def __init__(self, api_key: str, system_prompt: Optional[str] = None, mcp_client=None, **kwargs):
        super().__init__(system_prompt, **kwargs)
        self.api_key = api_key
        self.client = OpenAI(api_key=self.api_key, base_url="https://api.x.ai/v1")
        print(f"GrokClient (OpenAI SDK) initialized.")
        self.mcp_client = mcp_client if mcp_client is not None else MCPClient("nagisa_mcp/fast_mcp_server.py")

    def _format_messages_for_grok(self, messages: List[BaseMessage], system_prompt: Optional[str] = None) -> Tuple[list, bool]:
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
                    "tool_call_id": getattr(msg, "tool_call_id", None)
                })
                continue
            if isinstance(msg.content, list):
                grok_content = []
                for c in msg.content:
                    if isinstance(c, dict):
                        if "text" in c and "type" not in c:
                            grok_content.append({"type": "text", "text": c["text"]})
                        elif "inline_data" in c:
                            mime = c["inline_data"].get("mime_type", "image/png")
                            data = c["inline_data"]["data"]
                            grok_content.append({
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime};base64,{data}"}
                            })
                            has_image = True
                        elif c.get("type") == "image_url":
                            grok_content.append(c)
                            has_image = True
                        elif c.get("type") == "text":
                            grok_content.append(c)
                        else:
                            grok_content.append(c)
                    else:
                        grok_content.append(c)
                messages_for_llm.append({"role": msg.role, "content": grok_content})
            else:
                if isinstance(msg.content, list):
                    text = "".join(str(c.get("text", "")) if isinstance(c, dict) else str(c) for c in msg.content)
                else:
                    text = str(msg.content)
                messages_for_llm.append({"role": msg.role, "content": text})
        return messages_for_llm, has_image

    async def get_response(self, messages: List[BaseMessage], **kwargs) -> 'LLMResponse':
        messages_for_llm, has_image = self._format_messages_for_grok(messages)
        print("\n========== Grok API 请求消息格式 ==========")
        import pprint; pprint.pprint(messages_for_llm)
        print("========== END ==========")
        model = self.extra_config.get("model", "grok-3")
        tools = await self.get_function_call_schemas()
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages_for_llm,
                temperature=self.extra_config.get("temperature", 0.7),
                max_tokens=self.extra_config.get("max_tokens", 1024),
                tools=tools if tools else None
            )

            if response.choices and hasattr(response.choices[0].message, "tool_calls") and response.choices[0].message.tool_calls:
                tool_calls = []
                for tool_call in response.choices[0].message.tool_calls:
                    function_name = tool_call.function.name
                    arguments = tool_call.function.arguments
                    tool_call_id = tool_call.id
                    try:
                        function_args = json.loads(arguments) if isinstance(arguments, str) else arguments
                    except Exception:
                        function_args = arguments
                    tool_calls.append({
                        'name': function_name,
                        'arguments': function_args,
                        'id': tool_call_id
                    })
                return LLMResponse(
                    content="",
                    response_type=ResponseType.FUNCTION_CALL,
                    tool_calls=tool_calls
                )
            if response.choices:
                llm_reply = response.choices[0].message.content
                response_text, keyword = parse_llm_output(llm_reply)
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
            return LLMResponse(
                content=f"Grok (OpenAI SDK) error: {str(e)}",
                response_type=ResponseType.ERROR
            )

    async def generate_title_from_messages(
        self,
        first_user_message: BaseMessage,
        first_assistant_message: BaseMessage,
        title_generation_system_prompt: Optional[str] = None
    ) -> Optional[str]:
        try:
            system_prompt = title_generation_system_prompt or "你是一个专业的对话标题生成助手。请根据提供的对话内容，生成一个简洁的标题（5-15个字）。标题应准确概括对话的主要主题或意图。你必须将标题放在<title></title>标签中，并且除了这些标签和标题本身外，不要输出任何其他内容。"
            messages = [
                first_user_message,
                first_assistant_message,
                UserMessage(role="user", content=[{"type": "text", "text": "请为上面对话生成标题"}])
            ]
            messages_for_llm, has_image = self._format_messages_for_grok(messages, system_prompt=system_prompt)
            response = self.client.chat.completions.create(
                model=self.extra_config.get("model", "grok-3"),
                messages=messages_for_llm,
                temperature=1.0,
                max_tokens=100
            )
            if response.choices:
                title_response_text = response.choices[0].message.content
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
            print(f"Grok生成标题时出错: {str(e)}")
            return None

    async def get_function_call_schemas(self):
        async with self.mcp_client as mcp_async_client:
            mcp_tools = await mcp_async_client.list_tools()
        tools = []
        for tool in mcp_tools:
            params = getattr(tool, "inputSchema", {"type": "object", "properties": {}})
            if "properties" in params:
                params["required"] = list(params["properties"].keys())
            if "additionalProperties" not in params:
                params["additionalProperties"] = False
            tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": getattr(tool, "description", ""),
                    "parameters": params
                }
            })
        return tools

    async def handle_function_call(self, function_call: dict):
        tool_name = function_call["name"]
        params = function_call.get("arguments", {})
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except Exception:
                params = {}
        async with self.mcp_client as mcp_async_client:
            return await mcp_async_client.call_tool(tool_name, params)

    async def handle_function_call_closed_loop(
        self,
        messages: List[Message],
        tool_call: dict,
        tool_result: Any,
        **kwargs
    ) -> 'LLMResponse':
        import json as _json
        function_name = tool_call.get("name")
        arguments = tool_call.get("arguments")
        tool_call_id = tool_call.get("id", "tool_call_id")
        if not isinstance(arguments, str):
            arguments = _json.dumps(arguments, ensure_ascii=False)
        messages_for_llm, _ = self._format_messages_for_grok(messages)
        messages_for_llm.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": tool_call_id,
                    "type": "function",
                    "function": {
                        "name": function_name,
                        "arguments": arguments
                    }
                }
            ]
        })
        messages_for_llm.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": getattr(tool_result, 'text', str(tool_result))
        })
        model = self.extra_config.get("model", "grok-3")
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages_for_llm,
                temperature=self.extra_config.get("temperature", 0.7),
                max_tokens=self.extra_config.get("max_tokens", 1024)
            )
            if response.choices:
                llm_reply = response.choices[0].message.content
                response_text, keyword = parse_llm_output(llm_reply)
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
            return LLMResponse(
                content=f"Grok (OpenAI SDK) error: {str(e)}",
                response_type=ResponseType.ERROR
            ) 