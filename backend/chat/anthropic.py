import os
import re
from typing import List, Tuple, Optional, Dict, Any
import httpx
import json
from backend.chat.base import LLMClientBase
from backend.chat.models import Message
from backend.chat.utils import parse_llm_output

class AnthropicClient(LLMClientBase):
    """
    Anthropic 客户端实现。
    继承自 LLMClientBase，实现具体的 API 调用逻辑。
    """
    
    def __init__(self, api_key: str, system_prompt: Optional[str] = None, **kwargs):
        """
        初始化 Anthropic 客户端。
        Args:
            api_key: Anthropic API key。
            system_prompt: 可选，覆盖初始化时的 system prompt。
        """
        super().__init__(system_prompt, **kwargs)
        self.api_key = api_key
        self.base_url = "https://api.anthropic.com/v1"
        self.headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }

    def _format_messages_for_anthropic(self, messages: List[Message]) -> Tuple[List[Dict[str, Any]], bool]:
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
            if msg.role == "system":
                continue  # Anthropic 使用单独的 system 参数
            
            if isinstance(msg.content, list):
                # 处理多模态内容
                content = []
                for c in msg.content:
                    if isinstance(c, dict):
                        if "type" in c and c["type"] == "text" and "text" in c:
                            content.append({
                                "type": "text",
                                "text": c["text"]
                            })
                        elif "text" in c and "type" not in c:
                            content.append({
                                "type": "text",
                                "text": c["text"]
                            })
                        elif "inline_data" in c:
                            # 图片，转为 Anthropic 格式
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
                            # 兜底：转为文本
                            text = str(c.get("text", ""))
                            content.append({
                                "type": "text",
                                "text": text
                            })
                    else:
                        # 字符串直接转为 text 类型
                        content.append({
                            "type": "text",
                            "text": str(c)
                        })
                # 兜底：如果 content 为空，补一个空字符串
                if not content:
                    content = [{"type": "text", "text": ""}]
                anthropic_messages.append({
                    "role": "user" if msg.role == "user" else "assistant",
                    "content": content
                })
            else:
                # 普通字符串内容
                text = str(msg.content) if msg.content else ""
                anthropic_messages.append({
                    "role": "user" if msg.role == "user" else "assistant",
                    "content": [{
                        "type": "text",
                        "text": text
                    }]
                })
        
        return anthropic_messages, has_image

    async def get_response(
        self,
        messages: List[Message],
        **kwargs
    ) -> Tuple[str, str]:
        """
        调用 Anthropic API，返回 (response_text, keyword)。
        """
        # 使用辅助方法格式化消息
        anthropic_messages, has_image = self._format_messages_for_anthropic(messages)
        
        # 使用类属性中的配置值
        model = self.extra_config.get("model", "claude-3-5-sonnet-20241022")
        
        # 构建请求体
        payload = {
            "model": model,
            "messages": anthropic_messages,
            "system": self.system_prompt,
            "max_tokens": self.extra_config.get("max_tokens", 1024),
            "temperature": self.extra_config.get("temperature", 0.7),
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers=self.headers,
                    json=payload,
                    timeout=20.0
                )
                
                if response.status_code != 200:
                    response.raise_for_status()
                    
                response_data = response.json()
                if "content" not in response_data or not response_data["content"]:
                    raise ValueError("No content in Anthropic response")
                
                # 获取文本内容
                llm_reply = ""
                for content_item in response_data["content"]:
                    if content_item["type"] == "text":
                        llm_reply += content_item["text"]
                
                response_text, keyword = parse_llm_output(llm_reply)
                return response_text, keyword
        except httpx.TimeoutException:
            raise RuntimeError("Request to LLM timed out")
        except httpx.HTTPStatusError as e:
            print("Anthropic API error response:", e.response.text)
            raise RuntimeError(f"LLM API error: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Failed to get response from LLM: {str(e)}")

    async def generate_title_from_messages(
        self,
        first_user_message: Message,
        first_assistant_message: Message,
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
            
            # 使用相同的消息格式转换逻辑
            messages_for_llm, has_image = self._format_messages_for_anthropic([
                
                first_user_message,
                first_assistant_message
            ])
            
            payload = {
                "model": self.extra_config.get("model", "claude-3-5-sonnet-20241022"),
                "messages": messages_for_llm,
                "system": system_prompt,
                "max_tokens": 100,
                "temperature": 1
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