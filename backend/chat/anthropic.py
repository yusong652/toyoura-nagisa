import os
import re
from typing import List, Tuple, Optional, Dict, Any
import httpx
import json
from backend.chat.base import LLMClientBase
from backend.chat.models import BaseMessage, LLMResponse, ResponseType, UserToolMessage, UserMessage
from backend.chat.utils import parse_llm_output, get_latest_two_messages
import anthropic
from fastmcp import Client as MCPClient
from backend.nagisa_mcp.tools.text_to_image import generate_image_from_description
from backend.nagisa_mcp.utils import extract_text_from_mcp_result
from backend.config import get_models_lab_config

class AnthropicClient(LLMClientBase):
    """
    Anthropic 客户端实现。
    继承自 LLMClientBase，实现具体的 API 调用逻辑。
    """
    
    def __init__(self, api_key: str, system_prompt: Optional[str] = None, mcp_client=None, **kwargs):
        """
        初始化 Anthropic 客户端。
        Args:
            api_key: Anthropic API key。
            system_prompt: 可选，覆盖初始化时的 system prompt。
            mcp_client: 可选，用于 in-process tool calls via app.state.mcp
        """
        super().__init__(system_prompt, **kwargs)
        self.api_key = api_key
        self.base_url = "https://api.anthropic.com/v1"
        self.headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }
        self.anthropic_client = anthropic.Anthropic(api_key=self.api_key)
        self.mcp_client = mcp_client if mcp_client is not None else MCPClient("nagisa_mcp/fast_mcp_server.py")

    def _format_messages_for_anthropic(self, messages: List[BaseMessage]) -> Tuple[List[Dict[str, Any]], bool]:
        """
        将内部消息格式转换为Anthropic API所需的格式。
        Args:
            messages: 内部消息列表
        Returns:
            Tuple[List[Dict], bool]: 格式化后的消息列表和是否包含图片的标志
        """
        anthropic_messages = []
        has_image = False
        
        for msg in messages:
            # 不再跳过 system 消息，因为我们已经不再有 system message
            # if msg.role == "system":
            #     continue  # Anthropic 使用单独的 system 参数

            # 处理 assistant function_call 消息（带 tool_calls 字段，转为 Anthropic 官方格式）
            if msg.role == "assistant" and getattr(msg, "tool_calls", None):
                # 取自然语言内容
                text_block = {"type": "text", "text": msg.content or "正在调用工具..."}
                tool_blocks = []
                for call in msg.tool_calls:
                    # 兼容 arguments 为 str 或 dict
                    arguments = call["function"].get("arguments", {})
                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except Exception:
                            arguments = {}
                    tool_blocks.append({
                        "type": "tool_use",
                        "id": call["id"],
                        "name": call["function"]["name"],
                        "input": arguments
                    })
                anthropic_messages.append({
                    "role": "assistant",
                    "content": [text_block] + tool_blocks
                })
                continue

            # 修正：识别 UserToolMessage（工具响应，role 仍为 user，但有 tool_request 字段）
            if isinstance(msg, UserToolMessage) or getattr(msg, "role", None) == "tool":
                import json
                json_str = json.dumps(msg.content, ensure_ascii=False)
                tool_result_block = {
                    "type": "tool_result",
                    "tool_use_id": getattr(msg, "tool_call_id", ""),
                    "content": [{"type": "text", "text": json_str}]
                }
                anthropic_messages.append({
                    "role": "user",
                    "content": [tool_result_block]
                })
                continue

            # 2. 处理 user/assistant 角色
            if isinstance(msg.content, list):
                # 检查是否是 tool_result 块（已是 user+tool_result）
                if (
                    msg.role == "user"
                    and len(msg.content) == 1
                    and isinstance(msg.content[0], dict)
                    and msg.content[0].get("type") == "tool_result"
                ):
                    tool_result_block = msg.content[0]
                    # --- 修正：如果 content 是字符串，自动包装为 content block 数组 ---
                    content_val = tool_result_block.get("content", [])
                    if isinstance(content_val, str):
                        tool_result_block["content"] = [{"type": "text", "text": content_val}]
                    elif isinstance(content_val, list):
                        filtered = []
                        for c in content_val:
                            if isinstance(c, dict) and c.get("type") == "text":
                                text_val = str(c.get("text", "")).strip()
                                if text_val:
                                    filtered.append({"type": "text", "text": c["text"]})
                            elif isinstance(c, dict):
                                filtered.append(c)
                            elif isinstance(c, str):
                                filtered.append({"type": "text", "text": c})
                        tool_result_block["content"] = filtered
                    anthropic_messages.append({
                        "role": "user",
                        "content": [tool_result_block]
                    })
                    continue
                # 处理多模态内容
                content = []
                for c in msg.content:
                    if isinstance(c, dict):
                        if "type" in c and c["type"] == "text" and "text" in c:
                            content.append({
                                "type": "text",
                                "text": c["text"] or " "
                            })
                        elif "text" in c and "type" not in c:
                            content.append({
                                "type": "text",
                                "text": c["text"] or " "
                            })
                        elif "inline_data" in c:
                            mime = c["inline_data"].get("mime_type", "image/png")
                            data = c["inline_data"]["data"]
                            content.append({
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": mime,
                                    "data": data
                                }
                            })
                            has_image = True
                        elif "type" in c and c["type"] == "image_url" and "image_url" in c:
                            url = c["image_url"]
                            if url.startswith("data:"):
                                parts = url.split(",", 1)
                                if len(parts) == 2:
                                    mime = parts[0].split(":")[1].split(";")[0]
                                    data = parts[1]
                                    content.append({
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": mime,
                                            "data": data
                                        }
                                    })
                                    has_image = True
                            else:
                                content.append({
                                    "type": "image",
                                    "source": {
                                        "type": "url",
                                        "url": url
                                    }
                                })
                                has_image = True
                        else:
                            text = str(c.get("text", "")) or " "
                            content.append({
                                "type": "text",
                                "text": text
                            })
                    else:
                        content.append({
                            "type": "text",
                            "text": str(c) or " "
                        })
                if not content:
                    content = [{"type": "text", "text": " "}]
                anthropic_messages.append({
                    "role": "user" if msg.role == "user" else "assistant",
                    "content": content
                })
            else:
                text = str(msg.content) if msg.content else " "
                anthropic_messages.append({
                    "role": "user" if msg.role == "user" else "assistant",
                    "content": [{
                        "type": "text",
                        "text": text or " "
                    }]
                })
        return anthropic_messages, has_image

    def _format_llm_response(self, response) -> LLMResponse:
        """
        Format Anthropic API response into LLMResponse object.
        
        Args:
            response: Raw response from Anthropic API
            
        Returns:
            LLMResponse object containing the formatted response
        """
        # 检查是否有function call
        if hasattr(response, "content") and response.content:
            tool_calls = []
            text_content = ""
            for item in response.content:
                if hasattr(item, "type") and item.type == "text":
                    text_content = getattr(item, "text", "")
                elif hasattr(item, "type") and item.type == "tool_use":
                    function_name = getattr(item, "name", None)
                    arguments = getattr(item, "input", None)
                    tool_call_id = getattr(item, "id", None)
                    tool_calls.append({
                        'name': function_name,
                        'arguments': arguments,
                        'id': tool_call_id
                    })
            if tool_calls:
                return LLMResponse(
                    content=text_content,  # 用真实自然语言内容
                    response_type=ResponseType.FUNCTION_CALL,
                    tool_calls=tool_calls
                )
                
        # 普通文本回复
        llm_reply = ""
        for content_item in response.content:
            if hasattr(content_item, "type") and content_item.type == "text":
                llm_reply += getattr(content_item, "text", "")
        response_text, keyword = parse_llm_output(llm_reply)
        return LLMResponse(
            content=response_text,
            response_type=ResponseType.TEXT,
            keyword=keyword
        )

    async def get_response(
        self,
        messages: List[BaseMessage],
        **kwargs
    ) -> 'LLMResponse':
        """
        调用 Anthropic API，返回 LLMResponse。
        """
        anthropic_messages, has_image = self._format_messages_for_anthropic(messages)
        # 根据配置决定是否打印调试信息
        if self.extra_config.get('debug', False):
            print("\n========== Anthropic API 请求消息格式 ==========")
            import pprint; pprint.pprint(anthropic_messages)
            print("========== END ==========")
        model = self.extra_config.get("model", "claude-3-5-sonnet-20241022")
        # 自动获取 tools
        tools = await self.get_function_call_schemas()
        try:
            kwargs_api = dict(
                model=model,
                max_tokens=self.extra_config.get("max_tokens", 1024),
                messages=anthropic_messages,
                system=self.system_prompt,
                temperature=self.extra_config.get("temperature", 0.7),
            )
            if tools and len(tools) > 0:
                kwargs_api["tools"] = tools
            response = self.anthropic_client.messages.create(**kwargs_api)
            return self._format_llm_response(response)
        except Exception as e:
            print(f"Anthropic API error: {e}")
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
        Generate a concise conversation title using the Anthropic API.
        支持多模态 content。
        
        Args:
            first_user_message: Message object containing the first user message
            first_assistant_message: Message object containing the first assistant message
            title_generation_system_prompt: Optional custom system prompt for title generation
        """
        try:
            system_prompt = title_generation_system_prompt or "你是一个专业的对话标题生成助手。请根据提供的对话内容，生成一个简洁的标题（5-15个字）。标题应准确概括对话的主要主题或意图。你必须将标题放在<title></title>标签中，并且除了这些标签和标题本身外，不要输出任何其他内容。"
            
            # 构造消息序列，最后一条为user
            messages = [
                first_user_message,
                first_assistant_message,
                UserMessage(role="user", content=[{"type": "text", "text": "请为上面对话生成标题"}])
            ]
            
            # 使用相同的消息格式转换逻辑
            messages_for_llm, has_image = self._format_messages_for_anthropic(messages)
            
            payload = {
                "model": self.extra_config.get("model", "claude-3-5-sonnet-20241022"),
                "messages": messages_for_llm,
                "system": system_prompt,
                "max_tokens": 100,
                "temperature": 1  # A higher temperature for more creative titles
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers=self.headers,
                    json=payload,
                    timeout=60.0
                )
                response.raise_for_status()
                response_data = response.json()
                
                if "content" not in response_data or not response_data["content"]:
                    return None
                    
                title_response_text = ""
                for content_item in response_data["content"]:
                    if content_item["type"] == "text":
                        title_response_text += content_item["text"]
                
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
                
        except httpx.TimeoutException:
            raise RuntimeError("Request to LLM timed out")
        except httpx.HTTPStatusError as e:
            print("Anthropic API error response:", e.response.text)
            raise RuntimeError(f"LLM API error: {str(e)}")
        except Exception as e:
            print(f"Anthropic生成标题时出错: {str(e)}")
            return None 

    async def generate_text_to_image_prompt(self, session_id: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Generate a high-quality text-to-image prompt using the Anthropic API.
        This method uses a specialized system prompt to create detailed and effective prompts for image generation
        based on the recent conversation context.
        
        Args:
            session_id: Optional session ID to get the latest conversation context
            
        Returns:
            Optional[Dict[str, str]]: A dictionary containing the text prompt and negative prompt, or None if generation fails
        """
        debug = self.extra_config.get('debug', False)
        try:
            system_prompt = get_models_lab_config().get("text_to_image_system_prompt", "")
            if not system_prompt:
                error_msg = "Empty system prompt for text-to-image generation"
                if debug:
                    print(f"[text_to_image] Error: {error_msg}")
                return None

            # 获取最新的对话消息
            latest_messages = get_latest_two_messages(session_id) if session_id else (None, None)
            if not latest_messages[0] or not latest_messages[1]:
                error_msg = f"Missing conversation context for session {session_id}"
                if debug:
                    print(f"[text_to_image] Error: {error_msg}")
                return None
            
            # 构造消息序列
            messages = []
            if latest_messages[0] and latest_messages[1]:
                # 将对话内容组合成一个专门用于生成提示词的用户消息
                conversation_text = f"Please generate text to image prompt based on the following conversation:\n\n{latest_messages[0].role}: {latest_messages[0].content}\n{latest_messages[1].role}: {latest_messages[1].content}"
                messages.append(UserMessage(role="user", content=conversation_text))
            
            # 使用相同的消息格式转换逻辑
            messages_for_llm, _ = self._format_messages_for_anthropic(messages)
            if debug:
                print("\n[text_to_image] Messages for prompt generation:")
                import pprint; pprint.pprint(messages_for_llm)
            
            # 添加请求前的日志
            if debug:
                print("\n[text_to_image] Sending request to Anthropic API with:")
                print(f"Model: {self.extra_config.get('model', 'claude-3-5-sonnet-20241022')}")
                print(f"System prompt length: {len(system_prompt)}")
                print(f"Messages count: {len(messages_for_llm)}")
            
            response = self.anthropic_client.messages.create(
                model=self.extra_config.get("model", "claude-3-5-sonnet-20241022"), 
                max_tokens=4096,
                messages=messages_for_llm,
                system=system_prompt,
                temperature=0.7)
            
            
            # 添加响应检查
            if not response:
                error_msg = "Empty response from Anthropic API"
                if debug:
                    print(f"[text_to_image] Error: {error_msg}")
                return None
                
            if not hasattr(response, 'content'):
                error_msg = "Response missing content attribute"
                if debug:
                    print(f"[text_to_image] Error: {error_msg}")
                    print(f"Response object: {response}")
                return None
                
            if not response.content:
                error_msg = "Empty content in response"
                if debug:
                    print(f"[text_to_image] Error: {error_msg}")
                    print(f"Response object: {response}")
                return None
            
            if debug:
                print("\n[text_to_image] Raw response from Anthropic API:")
                print(response)
            
            prompt_text = ""
            for content_item in response.content:
                if hasattr(content_item, 'type') and content_item.type == "text":
                    if hasattr(content_item, 'text'):
                        prompt_text += content_item.text
                    else:
                        if debug:
                            print(f"[text_to_image] Warning: Content item missing text attribute: {content_item}")
            
            if not prompt_text:
                error_msg = "No text content found in response"
                if debug:
                    print(f"[text_to_image] Error: {error_msg}")
                    print(f"Response content items: {response.content}")
                return None
            
            if debug:
                print("\n[text_to_image] Extracted prompt text:")
                print(prompt_text)
            
            # 解析输出格式
            text_prompt_match = re.search(r'<text_to_image_prompt>(.*?)</text_to_image_prompt>', prompt_text, re.DOTALL)
            negative_prompt_match = re.search(r'<negative_prompt>(.*?)</negative_prompt>', prompt_text, re.DOTALL)
            
            if not text_prompt_match:
                error_msg = "Failed to extract text prompt from response"
                if debug:
                    print(f"[text_to_image] Error: {error_msg}")
                    print(f"Response did not contain expected <text_to_image_prompt> tags")
                    print(f"Full prompt text: {prompt_text}")
                return None
                
            text_prompt = text_prompt_match.group(1).strip()
            negative_prompt = negative_prompt_match.group(1).strip() if negative_prompt_match else "blurry, low quality, distorted, extra limbs, bad anatomy, text, watermark, ugly"
            
            if not text_prompt:
                error_msg = "Extracted text prompt is empty"
                if debug:
                    print(f"[text_to_image] Error: {error_msg}")
                return None
            
            if debug:
                print("\n[text_to_image] Generated prompts:")
                print(f"Text prompt: {text_prompt}")
                print(f"Negative prompt: {negative_prompt}")
            
            return {
                "text_prompt": text_prompt,
                "negative_prompt": negative_prompt
            }
            
        except Exception as e:
            if debug:
                print(f"[text_to_image] Error during prompt generation: {str(e)}")
                import traceback
                print(f"[text_to_image] Full traceback:\n{traceback.format_exc()}")
            return None

    async def get_function_call_schemas(self):
        """
        获取所有 MCP 工具的 schema，供 LLM function call 注册用，返回 Anthropic tools 格式列表
        """
        if not self.tools_enabled:
            return None
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
            tool_schema = {
                "name": tool.name,
                "description": getattr(tool, "description", tool.name),
                "input_schema": params
            }
            tools.append(tool_schema)
        return tools

    async def handle_function_call(self, function_call: dict, session_id: Optional[str] = None):
        """
        处理 LLM 生成的 function_call 请求，自动分发到 MCP 工具
        function_call: 形如 {"name": "search_weather", "arguments": {"city": "北京"}}
        session_id: 可选的会话ID，用于需要会话上下文的工具（如文生图）
        """
        tool_name = function_call["name"]
        tool_args = function_call.get("arguments", {})
        debug = self.extra_config.get('debug', False)

        # Special handling for generate_image tool
        if tool_name == "generate_image":
            if not session_id:
                if debug:
                    print("[text_to_image] Error: No session ID provided for image generation")
                return "Error: No session ID provided for image generation"

            # Generate prompts using LLM
            prompt_result = await self.generate_text_to_image_prompt(session_id)
            if not prompt_result:
                if debug:
                    print("[text_to_image] Error: Failed to generate image prompts")
                return "Error: Failed to generate image prompts"

            # Call the internal image generation function
            try:
                result = await generate_image_from_description(
                    prompt=prompt_result["text_prompt"],
                    negative_prompt=prompt_result["negative_prompt"]
                )
                if not result:
                    if debug:
                        print("[text_to_image] Error: Image generation returned empty result")
                    return "Error: Image generation failed - empty result"
                return result
            except Exception as e:
                if debug:
                    print(f"[text_to_image] Error during image generation: {str(e)}")
                return f"Error: Image generation failed - {str(e)}"

        # Normal tool handling for other tools
        async with self.mcp_client as mcp_async_client:
            result = await mcp_async_client.call_tool(tool_name, tool_args)
            return extract_text_from_mcp_result(result)

    # 工具函数：规范化 tool_result 为 Anthropic 支持的 content block
    def _normalize_tool_content(self, tool_result):
        content = []
        if isinstance(tool_result, list):
            for c in tool_result:
                if isinstance(c, dict) and "type" in c and c["type"] in ("text", "image"):
                    content.append(c)
                elif isinstance(c, dict) and "inline_data" in c:
                    mime = c["inline_data"].get("mime_type", "image/png")
                    data = c["inline_data"]["data"]
                    content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime,
                            "data": data
                        }
                    })
                elif isinstance(c, dict) and "text" in c:
                    content.append({"type": "text", "text": str(c["text"])})
                elif c is not None:
                    content.append({"type": "text", "text": str(c)})
        elif tool_result is not None:
            content = [{"type": "text", "text": str(tool_result)}]
        else:
            content = [{"type": "text", "text": ""}]
        return content
