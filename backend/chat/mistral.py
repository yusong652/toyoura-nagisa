import os
from typing import List, Tuple, Optional, Dict, Any
import httpx
import json
from backend.chat.base import LLMClientBase
from backend.chat.models import Message, LLMResponse, ResponseType
from backend.chat.utils import parse_llm_output
import re

class MistralClient(LLMClientBase):
    """
    Mistral 客户端实现。
    继承自 LLMClientBase，实现具体的 API 调用逻辑。
    """
    
    def __init__(self, api_key: str, system_prompt: Optional[str] = None, **kwargs):
        """
        初始化 Mistral 客户端。
        Args:
            api_key: Mistral API key。
            system_prompt: 可选，覆盖初始化时的 system prompt。
        """
        super().__init__(system_prompt, **kwargs)
        self.api_key = api_key
        self.base_url = "https://api.mistral.ai/v1"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        print(f"MistralClient initialized.")

    def _format_messages_for_mistral(self, messages: List[Message], system_prompt: Optional[str] = None) -> Tuple[List[Dict[str, Any]], bool]:
        messages_for_llm = [
            {"role": "system", "content": [{
                "type": "text",
                "text": system_prompt if system_prompt is not None else self.system_prompt
            }]}
        ]
        has_image = False
        for msg in messages:
            # 自动转换为 Mistral 多模态格式
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
                # 所有消息都使用统一的数组格式
                messages_for_llm.append({
                    "role": msg.role, 
                    "content": [{
                        "type": "text",
                        "text": str(msg.content)
                    }]
                })
        return messages_for_llm, has_image

    async def get_response(
        self,
        messages: List[Message],
        **kwargs
    ) -> 'LLMResponse':
        """
        调用 Mistral API，返回 LLMResponse。
        """
        messages_for_llm, has_image = self._format_messages_for_mistral(messages)
        model = self.extra_config.get("model", "pixtral-large-2411")
        payload = {
            "model": model,
            "messages": messages_for_llm,
            "temperature": self.extra_config.get("temperature", 0.7),
            "max_tokens": self.extra_config.get("max_tokens", 1024),
            "stream": False
        }
        try:
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
                    raise ValueError("No choices in Mistral response")
                llm_reply = response_data["choices"][0]["message"]["content"]
                response_text, keyword = parse_llm_output(llm_reply)
                return LLMResponse(
                    content=response_text,
                    response_type=ResponseType.TEXT,
                    keyword=keyword
                )
        except httpx.TimeoutException as e:
            return LLMResponse(
                content="Request to LLM timed out",
                response_type=ResponseType.ERROR
            )
        except httpx.HTTPStatusError as e:
            return LLMResponse(
                content=f"LLM API error: {str(e)}",
                response_type=ResponseType.ERROR
            )
        except Exception as e:
            return LLMResponse(
                content=f"Failed to get response from LLM: {str(e)}",
                response_type=ResponseType.ERROR
            )

    async def generate_title_from_messages(
        self,
        first_user_message: Message,
        first_assistant_message: Message,
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
                Message(role="user", content=[{"type": "text", "text": "请为上面对话生成标题"}])
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
        获取所有 MCP 工具的 schema，供 LLM function call 注册用，返回 Gemini Tool 对象列表
        """
        # 占位实现，返回空列表
        return []

    async def handle_function_call_closed_loop(
        self,
        messages: List[Message],
        tool_call: dict,
        tool_result: Any,
        **kwargs
    ) -> 'LLMResponse':
        """
        Mistral function call闭环：
        1. 将function_call和其结果作为新对话轮次加入messages
        2. 再次调用Mistral，获得最终自然语言回复
        """
        # 占位实现，返回错误响应
        from backend.chat.models import LLMResponse, ResponseType
        return LLMResponse(
            content="Function call closed-loop not supported in Mistral client.",
            response_type=ResponseType.ERROR
        ) 