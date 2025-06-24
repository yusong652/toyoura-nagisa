import os
import re
from typing import List, Tuple, Optional, Dict, Any
import httpx
import json
from backend.chat.base import LLMClientBase
from backend.chat.models import BaseMessage, LLMResponse, ResponseType, UserToolMessage, UserMessage
from backend.chat.utils import parse_llm_output, get_latest_n_messages
import anthropic
from fastmcp import Client as MCPClient
from backend.nagisa_mcp.tools.text_to_image import generate_image_from_description
from backend.nagisa_mcp.utils import extract_text_from_mcp_result
from backend.config import get_models_lab_config, get_text_to_image_config

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
        
        # 工具缓存机制
        self.tool_cache = {}  # 缓存查询到的工具
        self.meta_tools = set()  # meta tool名称集合
        self.session_tool_cache = {}  # 按会话ID缓存工具

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
                        tools.append({
                            "name": tool_info["name"],
                            "description": tool_info.get("description", ""),
                            "category": tool_info.get("category", "general"),
                            "docstring": tool_info.get("docstring", ""),
                            "parameters": tool_info.get("parameters", {}),
                            "tags": tool_info.get("tags", [])
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
            # 处理 assistant function_call 消息（带 tool_calls 字段，转为 Anthropic 官方格式）
            if msg.role == "assistant" and getattr(msg, "tool_calls", None):
                # 构造消息块
                blocks = []
                # 如果有 thinking 块，添加到最前面
                if isinstance(msg.content, list):
                    for item in msg.content:
                        if isinstance(item, dict) and item.get("type") == "thinking":
                            blocks.append(item)
                # 添加工具调用块
                for call in msg.tool_calls:
                    # 兼容 arguments 为 str 或 dict
                    arguments = call["function"].get("arguments", {})
                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except Exception:
                            arguments = {}
                    blocks.append({
                        "type": "tool_use",
                        "id": call["id"],
                        "name": call["function"]["name"],
                        "input": arguments
                    })
                anthropic_messages.append({
                    "role": "assistant",
                    "content": blocks
                })
                continue

            # 修正：识别 UserToolMessage（工具响应，role 仍为 user，但有 tool_request 字段）
            if isinstance(msg, UserToolMessage) or getattr(msg, "role", None) == "tool":
                # 如果 content 是字典且包含 is_error 字段，保持原样
                if isinstance(msg.content, dict) and "is_error" in msg.content:
                    content = json.dumps(msg.content, ensure_ascii=False)
                # 如果 content 是字典且包含 text 字段，只使用 text 内容
                elif isinstance(msg.content, dict) and "text" in msg.content:
                    content = msg.content["text"]
                # 其他情况，转为 JSON 字符串
                else:
                    content = json.dumps(msg.content, ensure_ascii=False)
                    
                tool_result_block = {
                    "type": "tool_result",
                    "tool_use_id": getattr(msg, "tool_call_id", ""),
                    "content": content
                }
                anthropic_messages.append({
                    "role": "user",
                    "content": [tool_result_block]
                })
                continue

            # 处理 user/assistant 角色
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

                # 处理多模态内容，包括 thinking 和 redacted_thinking 块
                content = []
                for c in msg.content:
                    if isinstance(c, dict):
                        if c.get("type") in ["thinking", "redacted_thinking"]:
                            # 直接保留 thinking 和 redacted_thinking 块的原始结构
                            content.append(c)
                        elif "type" in c and c["type"] == "text" and "text" in c:
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
        if not hasattr(response, "content") or not response.content:
            return LLMResponse(content=[{"type": "text", "text": ""}], response_type=ResponseType.TEXT)

        tool_calls = []
        llm_content = []
        llm_reply = ""

        for item in response.content:
            item_dict = {"type": item.type}
            if item.type == "text":
                item_dict["text"] = item.text
                llm_reply += item.text
            elif item.type == "tool_use":
                item_dict["name"] = item.name
                item_dict["input"] = item.input
                item_dict["id"] = item.id
                tool_calls.append({
                    'name': item.name,
                    'arguments': item.input,
                    'id': item.id
                })
            elif item.type == "thinking":
                item_dict["thinking"] = item.thinking
                item_dict["signature"] = item.signature
            elif item.type == "redacted_thinking":
                pass
            
            llm_content.append(item_dict)

        if tool_calls:
            return LLMResponse(
                content=llm_content,
                response_type=ResponseType.FUNCTION_CALL,
                tool_calls=tool_calls
            )
        
        response_text, keyword = parse_llm_output(llm_reply)
        
        return LLMResponse(
            content=llm_content,
            response_type=ResponseType.TEXT,
            keyword=keyword
        )

    async def get_response(
        self,
        messages: List[BaseMessage],
        session_id: Optional[str] = None,
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
        # 自动获取 tools，传递session_id以支持动态工具选择
        tools = await self.get_function_call_schemas(session_id)
        print(f"[DEBUG] tools from get_function_call_schemas: {tools}")
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

            # 检查是否为claude 3.7及以上模型，自动添加thinking参数
            if (
                model.startswith("claude-3-7-") or
                model.startswith("claude-sonnet-4-") or
                model.startswith("claude-4-") or
                model.startswith("claude-3-opus-")
            ):
                budget_tokens = self.extra_config.get("thinking_budget_tokens", 10000)
                kwargs_api["thinking"] = {
                    "type": "enabled",
                    "budget_tokens": budget_tokens
                }

            response = self.anthropic_client.messages.create(**kwargs_api)
            print(f"keyword: {kwargs_api}")
            if self.extra_config.get('debug', False):
                import pprint; pprint.pprint(response)
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
            system_prompt = get_text_to_image_config().get("system_prompt", "")
            if not system_prompt:
                error_msg = "Empty system prompt for text-to-image generation"
                if debug:
                    print(f"[text_to_image] Error: {error_msg}")
                return None

            # 获取n的配置
            n = get_text_to_image_config().get("context_message_count", 2)
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
            messages_for_llm, _ = self._format_messages_for_anthropic(messages)
            if debug:
                print("\n[text_to_image] Messages for prompt generation:")
                import pprint; pprint.pprint(messages_for_llm)
            
            # 添加请求前的日志
            if debug:
                print("\n[text_to_image] Sending request to Anthropic API with:")
                print(f"Model: {self.extra_config.get('model_for_text_to_image', 'claude-3-5-sonnet-20241022')}")
                print(f"System prompt length: {len(system_prompt)}")
                print(f"Messages count: {len(messages_for_llm)}")
            
            response = self.anthropic_client.messages.create(
                model=self.extra_config.get("model_for_text_to_image", "claude-3-5-sonnet-20241022"), 
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

    async def get_function_call_schemas(self, session_id: Optional[str] = None):
        """
        获取所有 MCP 工具的 schema，供 LLM function call 注册用，返回 Anthropic tools 格式列表
        只返回 meta tools + cached tools，不返回所有 regular tools。
        """
        if not self.tools_enabled:
            return None
        
        debug = self.extra_config.get('debug', False)
        
        # 获取会话缓存的工具
        cached_tools = []
        if session_id:
            cached_tools = self._get_cached_tools_for_session(session_id)
            if debug:
                print(f"[DEBUG] Found {len(cached_tools)} cached tools for session {session_id}")
        
        # 获取所有MCP工具
        async with self.mcp_client as mcp_async_client:
            mcp_tools = await mcp_async_client.list_tools()
        
        # 构建工具映射
        tools_map = {}
        meta_tools = []
        
        for tool in mcp_tools:
            tool_name = tool.name
            
            # 简化参数处理
            input_schema = getattr(tool, "inputSchema", {"type": "object", "properties": {}})
            if "properties" in input_schema:
                # 确保所有参数都有描述
                for prop in input_schema["properties"].values():
                    if "description" not in prop:
                        prop["description"] = f"Parameter value"
                # 设置required字段
                input_schema["required"] = list(input_schema["properties"].keys())
            
            # 确保schema完整性
            if "type" not in input_schema:
                input_schema["type"] = "object"
            if "additionalProperties" not in input_schema:
                input_schema["additionalProperties"] = False
            
            tool_schema = {
                "name": tool_name,
                "description": getattr(tool, "description", tool_name),
                "input_schema": input_schema
            }
            
            tools_map[tool_name] = tool_schema
            if self._is_meta_tool(tool_name):
                meta_tools.append(tool_schema)
        
        # 构建最终工具列表：meta tools + cached tools
        final_tools = meta_tools.copy()
        
        for cached_tool in cached_tools:
            tool_name = cached_tool["name"]
            if tool_name in tools_map:
                final_tools.append(tools_map[tool_name])
                if debug:
                    print(f"[DEBUG] Added cached tool: {tool_name}")
            else:
                # 为缓存工具创建基础schema
                final_tools.append({
                    "name": tool_name,
                    "description": cached_tool.get("description", tool_name),
                    "input_schema": {
                        "type": "object",
                        "properties": cached_tool.get("parameters", {}),
                        "required": list(cached_tool.get("parameters", {}).keys()),
                        "additionalProperties": False
                    }
                })
                if debug:
                    print(f"[DEBUG] Added cached tool with basic schema: {tool_name}")
        
        if debug:
            print(f"[DEBUG] Final tools count: {len(final_tools)} (meta: {len(meta_tools)}, cached: {len(cached_tools)})")
        
        return final_tools

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

        # 处理meta tool调用
        if self._is_meta_tool(tool_name):
            if debug:
                print(f"[DEBUG] Handling meta tool: {tool_name}")
            
            try:
                async with self.mcp_client as mcp_async_client:
                    result = await mcp_async_client.call_tool(tool_name, tool_args)
                    text_result = extract_text_from_mcp_result(result)
                    
                    # 检查结果是否表示错误
                    if isinstance(result, dict) and result.get("error"):
                        return {
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "name": tool_name,
                            "content": text_result,
                            "is_error": True
                        }
                    
                    # 如果是search_tools_by_keywords，缓存查询到的工具
                    if tool_name == "search_tools_by_keywords" and session_id:
                        try:
                            # 尝试解析结果为JSON
                            if isinstance(result, dict):
                                meta_result = result
                            else:
                                meta_result = json.loads(text_result) if isinstance(text_result, str) else {}
                            
                            # 提取并缓存工具
                            extracted_tools = self._extract_tools_from_meta_result(meta_result)
                            if extracted_tools:
                                self._cache_tools_for_session(session_id, extracted_tools)
                                if debug:
                                    print(f"[DEBUG] Cached {len(extracted_tools)} tools for session {session_id}")
                                    for tool in extracted_tools:
                                        print(f"[DEBUG]   - {tool['name']}: {tool.get('description', '')}")
                        except Exception as e:
                            if debug:
                                print(f"[DEBUG] Failed to cache tools from meta result: {e}")
                    
                    return text_result
                    
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

        # Special handling for generate_image tool
        if tool_name == "generate_image":
            if not session_id:
                if debug:
                    print("[text_to_image] Error: No session ID provided for image generation")
                return {
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "name": tool_name,
                    "content": "Error: No session ID provided for image generation",
                    "is_error": True
                }

            # Generate prompts using LLM
            prompt_result = await self.generate_text_to_image_prompt(session_id)
            if not prompt_result:
                if debug:
                    print("[text_to_image] Error: Failed to generate image prompts")
                return {
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "name": tool_name,
                    "content": "Error: Failed to generate image prompts",
                    "is_error": True
                }

            # Call the internal image generation function
            try:
                result = await generate_image_from_description(
                    prompt=prompt_result["text_prompt"],
                    negative_prompt=prompt_result["negative_prompt"]
                )
                if not result:
                    if debug:
                        print("[text_to_image] Error: Image generation returned empty result")
                    return {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "name": tool_name,
                        "content": "Error: Image generation failed - empty result",
                        "is_error": True
                    }
                return result
            except Exception as e:
                if debug:
                    print(f"[text_to_image] Error during image generation: {str(e)}")
                return {
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "name": tool_name,
                    "content": f"Error: Image generation failed - {str(e)}",
                    "is_error": True
                }

        # Normal tool handling for other tools
        try:
            async with self.mcp_client as mcp_async_client:
                result = await mcp_async_client.call_tool(tool_name, tool_args)
                text_result = extract_text_from_mcp_result(result)
                # Check if the result indicates an error
                if isinstance(result, dict) and result.get("error"):
                    return {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "name": tool_name,
                        "content": text_result,
                        "is_error": True
                    }
                return text_result
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
