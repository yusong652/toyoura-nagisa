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
from backend.chat.utils import parse_llm_output, get_latest_n_messages
from fastmcp import Client as MCPClient
from backend.nagisa_mcp.utils import extract_text_from_mcp_result
from backend.nagisa_mcp.tools.text_to_image import generate_image_from_description
from backend.config import get_models_lab_config, get_text_to_image_config

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
        
        print(f"Gemini Client initialized.")
        # 集成 MCPClient
        self.mcp_client = mcp_client if mcp_client is not None else MCPClient("nagisa_mcp/fast_mcp_server.py")


    def map_role(self, role: str) -> str:
        if role == "assistant":
            return "model"
        return "user"

    def _format_messages_for_gemini(self, messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """
        Format messages into Gemini API compatible format.
        
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
                # 保证 response 字段为 dict
                response_dict = msg.content if isinstance(msg.content, dict) else {"result": msg.content}
                parts = [types.Part(function_response=types.FunctionResponse(
                    name=tool_name,
                    response=response_dict
                ))]
                contents.append({
                    "role": "tool",
                    "parts": parts
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

    def _print_debug_request(self, contents, config):
        print("\n========== Gemini API 请求消息格式 ==========")
        print("Payload:")
        import pprint; pprint.pprint({
            "contents": contents,
            # "config": config
        })
        print("========== END ==========")

    def _print_debug_response(self, response):
        print("\n========== Gemini API 响应详情 ==========")
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                for part in candidate.content.parts:
                    if not getattr(part, 'text', None):
                        continue
                    if getattr(part, 'thought', False):
                        print("\n## **Thoughts summary:**")
                        print(part.text)
                        print()
                    else:
                        print("\n## **Answer:**")
                        print(part.text)
                        print()
                    # 代码相关内容依然保留
                    if hasattr(part, 'executable_code') and part.executable_code:
                        print("\n可执行代码:")
                        print(f"```python\n{part.executable_code.code}\n```")
                        print("---")
                    if hasattr(part, 'code_execution_result') and part.code_execution_result:
                        print("\n代码执行结果:")
                        print(f"```{part.code_execution_result.output}\n```")
                        print("---")
        # 打印 token 使用情况
        if hasattr(response, 'usage_metadata'):
            print("\nToken 使用情况:")
            print(f"Prompt Tokens: {response.usage_metadata.prompt_token_count}")
            print(f"Thoughts Tokens: {getattr(response.usage_metadata, 'thoughts_token_count', '-')}")
            print(f"Output Tokens: {getattr(response.usage_metadata, 'candidates_token_count', '-')}")
            print(f"Total Tokens: {response.usage_metadata.total_token_count}")
        print("========== END ==========")

    async def get_function_call_schemas(self):
        """
        获取所有工具的 schema，包括 MCP 工具和 Gemini 内置代码执行工具
        Returns:
            List[types.Tool]: 所有可用工具的 schema 列表
        """
        if not self.tools_enabled:
            return []
            
        tools = []
        # 1. 添加 MCP 工具
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
        if function_declarations:
            tools.append(types.Tool(function_declarations=function_declarations))
        
        # 2. 添加代码执行工具
        # tools.append(types.Tool(code_execution=types.ToolCodeExecution()))
        # tools.append(types.Tool(google_search=types.GoogleSearch()))
        
        return tools

    async def get_response(self, messages: List[BaseMessage], **kwargs) -> LLMResponse:
        # 1. 获取所有工具 schemas（包括 MCP 工具和代码执行工具）
        tool_schemas = await self.get_function_call_schemas()

        # 2. 构造 Gemini API payload，注册 tools
        contents = self._format_messages_for_gemini(messages)
        config_kwargs = dict(
            system_instruction=self.system_prompt,
            safety_settings=self.safety_settings,
            temperature=self.extra_config.get('temperature', 2.0),
            max_output_tokens=self.extra_config.get('max_output_tokens', 4096),
            tools=tool_schemas
        )
        if self.extra_config.get('model', "").startswith("gemini-2.5"):
            config_kwargs["thinking_config"] = types.ThinkingConfig(include_thoughts=True)
        config = types.GenerateContentConfig(**config_kwargs)

        if self.extra_config.get('debug', False):
            self._print_debug_request(contents, config)

        try:
            response = self.client.models.generate_content(
                model=self.extra_config.get('model', "gemini-2.0-flash-lite"),
                contents=contents,
                config=config
            )
            if self.extra_config.get('debug', False):
                print("[Gemini] Raw response:")
                import pprint; pprint.pprint(response) 
            
            if self.extra_config.get('debug', False):
                self._print_debug_response(response)
            
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
        处理 LLM 生成的 function_call 请求，自动分发到 MCP 工具。
        对于需要 session_id 的工具（如 generate_image），由后端逻辑传递 session_id，避免 LLM 填写。
        其余工具直接用 mcp_client 调用。
        function_call: 形如 {"name": "search_weather", "arguments": {"city": "北京"}}
        session_id: 可选的会话ID，用于需要会话上下文的工具
        """
        tool_name = function_call["name"]
        params = function_call.get("arguments", {})
        # 需要 session_id 的工具
        tools_need_session = {"generate_image"}
        if tool_name in tools_need_session:
            if not session_id:
                return "Error: No session ID provided for this tool."
            # generate_image 需要先生成 prompt，再调用图片生成
            prompt_result = await self.generate_text_to_image_prompt(session_id)
            if not prompt_result:
                return "Error: Failed to generate image prompts."
            try:
                result = await generate_image_from_description(
                    prompt=prompt_result["text_prompt"],
                    negative_prompt=prompt_result["negative_prompt"]
                )
                if not result:
                    return "Error: Image generation failed - empty result"
                return result
            except Exception as e:
                return f"Error: Image generation failed - {str(e)}"
        # 其余工具直接调用
        async with self.mcp_client as mcp_async_client:
            result = await mcp_async_client.call_tool(tool_name, params)
            return extract_text_from_mcp_result(result)

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
            system_prompt = get_text_to_image_config().get("system_prompt", "You are a professional prompt engineer. Please generate a detailed and creative text-to-image prompt based on the following conversation. The prompt should be suitable for high-quality image generation.")
            latest_messages = get_latest_n_messages(session_id) if session_id else (None, None)
            if not any(latest_messages):
                error_msg = f"Missing conversation context for session {session_id}"
                if debug:
                    print(f"[text_to_image] Error: {error_msg}")
                return None
            messages = []
            if latest_messages[0] and latest_messages[1]:
                conversation_text = f"Please generate text to image prompt based on the following conversation:\n\n{latest_messages[0].role}: {latest_messages[0].content}\n{latest_messages[1].role}: {latest_messages[1].content}"
                messages.append(UserMessage(role="user", content=conversation_text))
            contents = self._format_messages_for_gemini(messages)
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
                print("[Gemini][text_to_image] Messages for prompt generation:")
                import pprint; pprint.pprint(messages)
                print("[Gemini][text_to_image] Formatted contents:")
                pprint.pprint(contents)
                print("[Gemini][text_to_image] Prompt config:")
                pprint.pprint(prompt_config)
            
            response = self.client.models.generate_content(
                model=self.extra_config.get("model_for_text_to_image", "gemini-2.5-flash-preview-05-20"),
                contents=contents,
                config=prompt_config
            )
            if debug:
                print("[Gemini][text_to_image] Raw response:")
                pprint.pprint(response)
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