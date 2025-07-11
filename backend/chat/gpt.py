import os
import re
import json 
from typing import List, Tuple, Optional, Dict, Any
import httpx
from backend.chat.base import LLMClientBase
from backend.chat.models import Message, LLMResponse, ResponseType, UserToolMessage, BaseMessage, UserMessage
from backend.chat.utils import parse_llm_output, get_latest_n_messages
from fastmcp import Client as MCPClient
from backend.nagisa_mcp.utils import extract_text_from_mcp_result
from openai import OpenAI
from backend.nagisa_mcp.smart_mcp_server import mcp as GLOBAL_MCP
from mcp.types import Implementation, CallToolRequestParams, CallToolRequest, ClientRequest, CallToolResult
from backend.config import get_text_to_image_config, get_llm_specific_config, get_system_prompt

class GPTClient(LLMClientBase):
    """
    GPT 客户端实现。
    继承自 LLMClientBase，实现具体的 API 调用逻辑。
    """
    
    def __init__(self, api_key: str, **kwargs):
        """
        初始化 GPT 客户端。
        Args:
            api_key: OpenAI API key。
            mcp_client: 可选，MCPClient实例，用于直接调用MCP工具。
        """
        super().__init__(**kwargs)
        self.api_key = api_key
        self.base_url = "https://api.openai.com/v1"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        print(f"ChatGPTClient initialized.")

        # -------------------------------------------------------------
        # FastMCP client management (session-scoped for context injection)
        # -------------------------------------------------------------
        # If caller passed an MCPClient instance, treat it as the source
        # and reuse directly; otherwise use the global SmartMCP server.
        self._mcp_client_source = GLOBAL_MCP

        # Cache of MCPClient per chat session id -> MCPClient
        self._mcp_clients: dict[str | None, MCPClient] = {}

        # -------------------------------------------------------------
        # Tool caching (meta + per-session) – aligns with Gemini/Anthropic
        # -------------------------------------------------------------
        self.tool_cache: Dict[str, Any] = {}
        self.meta_tools: set[str] = set()
        self.session_tool_cache: Dict[str, List[Dict[str, Any]]] = {}

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
            if isinstance(msg, UserToolMessage) or getattr(msg, "role", None) == "tool":
                json_str = json.dumps(msg.content, ensure_ascii=False)
                messages_for_llm.append({
                    "role": "tool",
                    "content": [{"type": "text", "text": json_str}],
                    "tool_call_id": getattr(msg, "tool_call_id", None)
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
                        elif c.get("type") == "thinking":
                            # Preserve model thoughts as normal text so they remain in context.
                            openai_content.append({"type": "text", "text": c.get("thinking", "")})
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

    def _format_llm_response(self, response) -> LLMResponse:
        """
        Format OpenAI API response into LLMResponse object.
        
        Args:
            response: Raw response from OpenAI API
            
        Returns:
            LLMResponse object containing the formatted response
        """
        if not response.choices:
            raise ValueError("No choices in OpenAI response")
            
        choice = response.choices[0].message
        debug_flag = self.extra_config.get("debug", False)

        if hasattr(choice, "tool_calls") and choice.tool_calls:
            tool_calls = []
            for tool_call in choice.tool_calls:
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

            # 同时提取 thinking 片段, 以统一 content 结构
            raw_content = choice.content or ""

            if debug_flag:
                print("\n[GPTClient] Raw model reply (tool_call path):")
                print(raw_content)

            thinking_parts = re.findall(r'<thinking>(.*?)</thinking>', raw_content, re.S)
            cleaned_content = re.sub(r'<thinking>.*?</thinking>', '', raw_content, flags=re.S).strip()

            if debug_flag and thinking_parts:
                print("\n[GPTClient] Thinking blocks (tool_call path):")
                for idx, blk in enumerate(thinking_parts, 1):
                    preview = blk.strip().replace("\n", " ")
                    print(f"  {idx}. {preview[:120]}{'...' if len(preview) > 120 else ''}")
                print("[GPTClient] Cleaned content:", cleaned_content[:200])

            content_blocks: List[Dict[str, Any]] = []
            if thinking_parts:
                content_blocks.append({
                    "type": "thinking",
                    "thinking": "\n".join(thinking_parts).strip()
                })
            if cleaned_content:
                content_blocks.append({"type": "text", "text": cleaned_content})

            return LLMResponse(
                content=content_blocks,
                response_type=ResponseType.FUNCTION_CALL,
                tool_calls=tool_calls
            )

        # ---- 普通文本回复 ----
        raw_reply = choice.content or ""

        if debug_flag:
            print("\n[GPTClient] Raw model reply:")
            print(raw_reply)

        thinking_blocks = re.findall(r'<thinking>(.*?)</thinking>', raw_reply, re.S)
        visible_reply = re.sub(r'<thinking>.*?</thinking>', '', raw_reply, flags=re.S).strip()

        if debug_flag and thinking_blocks:
            print("\n[GGPTClient] Thinking blocks:")
            for idx, blk in enumerate(thinking_blocks, 1):
                preview = blk.strip().replace("\n", " ")
                print(f"  {idx}. {preview[:120]}{'...' if len(preview) > 120 else ''}")
            print("[GPTClient] Visible reply:", visible_reply[:200])

        response_text, keyword = parse_llm_output(visible_reply)

        content_list: List[Dict[str, Any]] = []
        if thinking_blocks:
            content_list.append({
                "type": "thinking",
                "thinking": "\n".join(thinking_blocks).strip()
            })
        content_list.append({"type": "text", "text": response_text})

        return LLMResponse(
            content=content_list,
            response_type=ResponseType.TEXT,
            keyword=keyword
        )

    async def get_response(
        self,
        messages: List[BaseMessage],
        session_id: Optional[str] = None,
        **kwargs
    ) -> 'LLMResponse':
        tools = await self.get_function_call_schemas(session_id)
        tools_enabled = bool(tools)
        system_prompt = get_system_prompt(tools_enabled=tools_enabled)
        
        # --- build system prompt with optional CoT instruction ---
        enable_cot = self.extra_config.get("enable_cot", False)
        if enable_cot:
            cot_prompt = (
                "Think step-by-step in a private section wrapped inside <thinking> and </thinking> tags. "
                "This section will be removed before the answer is shown to the user. After the tag, provide "
                "the final answer for the user. Never reveal or reference these tags." 
            )
            combined_system_prompt = f"{cot_prompt}\n\n{system_prompt}"
        else:
            combined_system_prompt = system_prompt

        messages_for_llm, has_image = self._format_messages_for_openai(messages, system_prompt=combined_system_prompt)
        
        # 根据配置决定是否打印调试信息
        if self.extra_config.get('debug', False):
            print("\n========== OpenAI API 请求消息格式 ==========")
            import pprint; pprint.pprint(messages_for_llm)
            print("========== END ==========")
            
        model = self.extra_config.get("model", "gpt-4-turbo-preview")
        
        payload = {
            "model": model,
            "messages": messages_for_llm,
            "temperature": self.extra_config.get("temperature", 0.7),
            "tools": tools if tools else None
        }
        
        try:
            response = self.openai_client.chat.completions.create(
                model=payload["model"],
                messages=payload["messages"],
                temperature=payload["temperature"],
                tools=payload.get("tools")
            )
            return self._format_llm_response(response)
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
                "temperature": 1.0
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

    async def get_function_call_schemas(self, session_id: Optional[str] = None):
        """
        获取所有 MCP 工具的 schema，供 LLM function call 注册用，返回 OpenAI tools 格式列表
        """
        if not self.tools_enabled:
            return None
            
        mcp_client = self._get_mcp_client(session_id)
        async with mcp_client as mcp_async_client:
            mcp_tools = await mcp_async_client.list_tools()

        # Build map and separate meta tools
        tools_map: Dict[str, Any] = {}
        meta_tools: List[Dict[str, Any]] = []

        for tool in mcp_tools:
            params = getattr(tool, "inputSchema", {"type": "object", "properties": {}})
            # 自动补全 required 字段
            if "properties" in params:
                params["required"] = list(params["properties"].keys())
            if "additionalProperties" not in params:
                params["additionalProperties"] = False
            tool_schema = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": getattr(tool, "description", ""),
                    "parameters": params,
                    "strict": True
                }
            }
            tools_map[tool.name] = tool_schema
            if self._is_meta_tool(tool.name):
                meta_tools.append(tool_schema)

        final_tools: List[Dict[str, Any]] = meta_tools.copy()
        added_tool_names = {tool["function"]["name"] for tool in meta_tools}  # 追踪已添加的工具名

        # Add cached tools (避免重复)
        if session_id:
            for cached_tool in self._get_cached_tools_for_session(session_id):
                name = cached_tool["name"]
                if name in added_tool_names:
                    continue  # 跳过已经添加的工具
                    
                if name in tools_map:
                    final_tools.append(tools_map[name])
                    added_tool_names.add(name)
                else:
                    # Construct minimal schema if not in current MCP list
                    params_cached = dict(cached_tool.get("parameters", {}))
                    final_tools.append(
                        {
                            "type": "function",
                            "function": {
                                "name": name,
                                "description": cached_tool.get("description", name),
                                "parameters": {
                                    "type": "object",
                                    "properties": params_cached,
                                    "required": list(params_cached.keys()),
                                    "additionalProperties": False,
                                },
                            },
                        }
                    )
                    added_tool_names.add(name)

        return final_tools

    async def handle_function_call(self, function_call: dict, session_id: Optional[str] = None):
        """
        处理 LLM 生成的 function_call 请求，自动分发到 MCP 工具
        function_call: 形如 {"name": "search_weather", "arguments": {"city": "北京"}}
        """
        tool_name = function_call["name"]
        tool_args = function_call.get("arguments", {})

        debug = self.extra_config.get("debug", False)

        # Handle meta tools first (search_tools_by_keywords etc.)
        if self._is_meta_tool(tool_name):
            mcp_client = self._get_mcp_client(session_id)
            try:
                async with mcp_client as mcp_async_client:
                    # Inject _meta
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
                    else:
                        result = await mcp_async_client.call_tool(tool_name, tool_args)

                text_result = extract_text_from_mcp_result(result)

                # If meta search, cache tools
                if tool_name == "search_tools_by_keywords" and session_id:
                    try:
                        meta_result = text_result if isinstance(text_result, dict) else json.loads(text_result)
                    except Exception:
                        meta_result = {}
                    extracted = self._extract_tools_from_meta_result(meta_result)
                    if extracted:
                        self._cache_tools_for_session(session_id, extracted)
                        if debug:
                            print(f"[DEBUG] Cached {len(extracted)} tools for session {session_id}")

                return text_result
            except Exception as e:
                if debug:
                    print(f"Error calling meta tool {tool_name}: {e}")
                return {
                    "type": "tool_result",
                    "name": tool_name,
                    "content": f"Error: {e}",
                    "is_error": True,
                }

        # --- Normal tool handling below ---
        params = tool_args

        mcp_client = self._get_mcp_client(session_id)

        async with mcp_client as mcp_async_client:
            # Inject session_id into _meta for context-aware tools
            try:
                if session_id:
                    call_params = CallToolRequestParams(
                        name=tool_name,
                        arguments=params,
                        **{"_meta": {"client_id": session_id}},
                    )
                    call_req = ClientRequest(CallToolRequest(method="tools/call", params=call_params))
                    result: CallToolResult = await mcp_async_client.session.send_request(
                        call_req,
                        CallToolResult,
                    )
                else:
                    result = await mcp_async_client.call_tool(tool_name, params)
            except Exception:
                # Fallback to simple call if direct request fails
                result = await mcp_async_client.call_tool(tool_name, params)

            return extract_text_from_mcp_result(result)

    def _get_mcp_client(self, session_id: Optional[str] = None) -> MCPClient:
        """Return (and cache) an MCPClient bound to *session_id*.

        A unique client per chat session ensures that FastMCP Session-level
        context (client_id) remains isolated.
        """

        # If the source is already a concrete MCPClient, reuse it directly.
        if isinstance(self._mcp_client_source, MCPClient):
            return self._mcp_client_source

        key = session_id or "__default__"
        client = self._mcp_clients.get(key)
        if client is None:
            client = MCPClient(
                self._mcp_client_source,
                client_info=Implementation(name=session_id, version="0.1.0"),
            )
            self._mcp_clients[key] = client
        return client

    # ------------------------------------------------------------------
    # Meta-tool helpers (same as other clients)
    # ------------------------------------------------------------------

    def _is_meta_tool(self, tool_name: str) -> bool:
        """Return True if *tool_name* is considered a meta tool."""
        return tool_name in {
            "search_tools_by_keywords",
            "get_available_tool_categories",
        }

    def _extract_tools_from_meta_result(self, meta_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract regular tools from meta-tool search result."""
        tools: List[Dict[str, Any]] = []
        if isinstance(meta_result, dict) and "tools" in meta_result and isinstance(meta_result["tools"], list):
            for tool_info in meta_result["tools"]:
                if not isinstance(tool_info, dict) or "name" not in tool_info:
                    continue
                # parameters and tags may arrive as JSON string – try decode
                params = tool_info.get("parameters", {})
                if isinstance(params, str):
                    try:
                        params = json.loads(params)
                    except Exception:
                        params = {}
                tags = tool_info.get("tags", [])
                if isinstance(tags, str):
                    try:
                        tags = json.loads(tags)
                    except Exception:
                        tags = []
                tools.append(
                    {
                        "name": tool_info["name"],
                        "description": tool_info.get("description", ""),
                        "category": tool_info.get("category", "general"),
                        "docstring": tool_info.get("docstring", ""),
                        "parameters": params,
                        "tags": tags,
                    }
                )
        return tools

    def _cache_tools_for_session(self, session_id: str, tools: List[Dict[str, Any]]):
        """Cache *tools* list for *session_id*, avoiding duplicates."""
        if session_id not in self.session_tool_cache:
            self.session_tool_cache[session_id] = []
        existing = {t["name"] for t in self.session_tool_cache[session_id]}
        for t in tools:
            if t["name"] not in existing:
                self.session_tool_cache[session_id].append(t)
                existing.add(t["name"])

    def _get_cached_tools_for_session(self, session_id: str) -> List[Dict[str, Any]]:
        return self.session_tool_cache.get(session_id, [])

    def _clear_session_tool_cache(self, session_id: str):
        if session_id in self.session_tool_cache:
            del self.session_tool_cache[session_id]

    # ------------------------------------------------------------------
    # Text-to-Image prompt generator (parity with Gemini / Anthropic)
    # ------------------------------------------------------------------

    async def generate_text_to_image_prompt(self, session_id: Optional[str] = None) -> Optional[Dict[str, str]]:
        """Generate a high-quality text-to-image prompt and negative prompt.

        This follows the same logic implemented for GeminiClient / AnthropicClient
        so higher-level server code can call it uniformly.
        """

        debug = self.extra_config.get("debug", False)

        try:
            cfg = get_text_to_image_config()
            system_prompt = cfg.get(
                "system_prompt",
                "You are a professional prompt engineer. Please generate a detailed and creative text-to-image prompt based on the following conversation. The prompt should be suitable for high-quality image generation.",
            )

            n_ctx = cfg.get("context_message_count", 2)

            # Fetch latest n user/assistant messages for the session (if any)
            latest_messages = get_latest_n_messages(session_id, n_ctx) if session_id else tuple([None] * n_ctx)
            if not any(latest_messages):
                if debug:
                    print(f"[text_to_image] No context messages for session {session_id}")
                return None

            conversation_text = "Please generate text to image prompt based on the following conversation:\n\n"
            for msg in latest_messages:
                if msg is not None:
                    conversation_text += f"{msg.role}: {msg.content}\n"

            # Build OpenAI-style messages (system + user)
            base_messages = [UserMessage(role="user", content=conversation_text)]
            openai_msgs, _ = self._format_messages_for_openai(base_messages, system_prompt=system_prompt)

            if debug:
                print("[text_to_image] OpenAI prompt messages:")
                import pprint as _pp; _pp.pprint(openai_msgs)

            model_name = self.extra_config.get("model_for_text_to_image", "gpt-4o-mini")

            response = self.openai_client.chat.completions.create(
                model=model_name,
                messages=openai_msgs,
                temperature=0.7,
                max_tokens=self.extra_config.get("max_output_tokens", 1024),
            )

            if not response.choices:
                return None

            prompt_text = response.choices[0].message.content or ""

            text_match = re.search(r"<text_to_image_prompt>(.*?)</text_to_image_prompt>", prompt_text, re.DOTALL)
            neg_match = re.search(r"<negative_prompt>(.*?)</negative_prompt>", prompt_text, re.DOTALL)

            if not text_match:
                if debug:
                    print("[text_to_image] Failed to parse prompt tags", prompt_text)
                return None

            text_prompt = text_match.group(1).strip()
            negative_prompt = (
                neg_match.group(1).strip()
                if neg_match else "blurry, low quality, distorted, extra limbs, bad anatomy, text, watermark, ugly"
            )

            # Merge default positive / negative keywords
            default_pos = cfg.get("default_positive_prompt", "")
            default_neg = cfg.get("default_negative_prompt", "")

            if default_pos:
                missing = [kw.strip() for kw in default_pos.split(",") if kw.strip() and kw.strip() not in [t.strip() for t in text_prompt.split(",")]]
                if missing:
                    text_prompt = ", ".join(missing + [text_prompt.lstrip(", ").strip()])

            if default_neg:
                missing = [kw.strip() for kw in default_neg.split(",") if kw.strip() and kw.strip() not in [t.strip() for t in negative_prompt.split(",")]]
                if missing:
                    negative_prompt = ", ".join(missing + [negative_prompt.lstrip(", ").strip()])

            if debug:
                print(f"[text_to_image] Final text_prompt: {text_prompt}\n[neg]: {negative_prompt}")

            return {"text_prompt": text_prompt, "negative_prompt": negative_prompt}

        except Exception:
            if debug:
                import traceback; traceback.print_exc()
            return None