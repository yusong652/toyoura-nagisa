import os
from typing import List, Tuple, Optional, Dict, Any
import httpx
import json
from backend.chat.base import LLMClientBase
from backend.chat.models import Message
from backend.chat.utils import parse_llm_output

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

    def _format_messages_for_mistral(self, messages: List[Message]) -> Tuple[List[Dict[str, Any]], bool]:
        """
        将内部消息格式转换为Mistral API所需的格式。
        
        Args:
            messages: 内部消息列表
            
        Returns:
            Tuple[List[Dict], bool]: 格式化后的消息列表和是否包含图片的标志
        """
        messages_for_llm = [
            {"role": "system", "content": self.system_prompt}
        ]
        
        has_image = False
        for msg in messages:
            # 自动转换为 Mistral 多模态格式
            if isinstance(msg.content, list):
                mistral_content = []
                has_text = False
                
                # 处理内容
                for c in msg.content:
                    if isinstance(c, dict):
                        if "type" in c and c["type"] == "text" and "text" in c:
                            # 保持 type=text 的格式
                            mistral_content.append({
                                "type": "text",
                                "text": c["text"]
                            })
                            has_text = True
                        elif "text" in c and "type" not in c:
                            # 普通文本
                            mistral_content.append({
                                "type": "text",
                                "text": c["text"]
                            })
                            has_text = True
                        elif "inline_data" in c:
                            # 图片，转为 mistral 格式
                            mime = c["inline_data"].get("mime_type", "image/png")
                            data = c["inline_data"]["data"]
                            mistral_content.append({
                                "type": "image_url",
                                "image_url": f"data:{mime};base64,{data}"
                            })
                            has_image = True
                        elif "type" in c and c["type"] == "image_url" and "image_url" in c:
                            # 已经是 image_url 格式，直接保留
                            mistral_content.append({
                                "type": "image_url",
                                "image_url": c["image_url"]
                            })
                            has_image = True
                        else:
                            # 兜底：转为文本
                            text = str(c.get("text", ""))
                            mistral_content.append({
                                "type": "text",
                                "text": text
                            })
                            has_text = True
                    else:
                        # 字符串直接转为 text 类型
                        mistral_content.append({
                            "type": "text",
                            "text": str(c)
                        })
                        has_text = True
                
                # 如果只有图片没有文本，添加一个空文本
                if has_image and not has_text:
                    mistral_content.insert(0, {
                        "type": "text",
                        "text": ""
                    })
            
                messages_for_llm.append({"role": msg.role, "content": mistral_content})
            else:
                # 其它情况全部转为字符串
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
    ) -> Tuple[str, str]:
        """
        调用 Mistral API，返回 (response_text, keyword)。
        """
        # 使用辅助方法格式化消息
        messages_for_llm, has_image = self._format_messages_for_mistral(messages)
        
        # 使用类属性中的配置值，始终使用配置中定义的模型
        model = self.extra_config.get("model", "pixtral-large-2411")
        payload = {
            "model": model,
            "messages": messages_for_llm,
            "temperature": self.extra_config.get("temperature", 0.7),
            "max_tokens": self.extra_config.get("max_tokens", 1024),
            "stream": False  # 确保不使用流式响应，等待完整回复
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    response.raise_for_status()
                    
                response_data = response.json()
                if not response_data.get("choices"):
                    raise ValueError("No choices in Mistral response")
                    
                llm_reply = response_data["choices"][0]["message"]["content"]
                response_text, keyword = parse_llm_output(llm_reply)
                return response_text, keyword
        except httpx.TimeoutException as e:
            raise RuntimeError("Request to LLM timed out")
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"LLM API error: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Failed to get response from LLM: {str(e)}")

    async def generate_title_from_messages(
        self,
        first_user_message_content: str,
        first_assistant_message_content: str,
        title_generation_system_prompt: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate a concise conversation title using the Mistral API.
        Args:
            first_user_message_content: The user's first message content
            first_assistant_message_content: The assistant's first reply content
            title_generation_system_prompt: Optional system prompt for title generation
        Returns:
            The generated conversation title, or None if generation fails
        """
        import re
        try:
            system_prompt = title_generation_system_prompt or "你是一个专业的对话标题生成助手。请根据提供的对话内容，生成一个简洁的标题（5-15个字）。标题应准确概括对话的主要主题或意图。你必须将标题放在<title></title>标签中，并且除了这些标签和标题本身外，不要输出任何其他内容。"
            user_prompt = f"""以下是对话内容，请为这个对话生成一个简洁的标题：\n\n{first_user_message_content}\n\n{first_assistant_message_content}\n\n请生成一个5-15个字的标题，并将标题放在<title></title>标签中。你的回复应该只包含这对标签和标题内容，不要包含任何其他文字。\n\n例如，回复应该是这样的格式：<title>这是一个标题示例</title>"""
            messages_for_llm = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [{"type": "text", "text": user_prompt}]}
            ]
            payload = {
                "model": self.extra_config.get("model", "pixtral-large-2411"),
                "messages": messages_for_llm,
                "temperature": 0.5,
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