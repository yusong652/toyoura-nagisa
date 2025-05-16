import os
from typing import List, Tuple, Optional, Dict, Any
import httpx
from backend.chat.base import LLMClientBase
from backend.chat.models import Message
from backend.chat.utils import parse_llm_output

class GPTClient(LLMClientBase):
    """
    GPT 客户端实现。
    继承自 LLMClientBase，实现具体的 API 调用逻辑。
    """
    
    def __init__(self, api_key: str, system_prompt: Optional[str] = None, **kwargs):
        """
        初始化 GPT 客户端。
        Args:
            api_key: OpenAI API key。
            system_prompt: 可选，覆盖初始化时的 system prompt。
        """
        super().__init__(system_prompt, **kwargs)
        self.api_key = api_key
        self.base_url = "https://api.openai.com/v1"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        print(f"ChatGPTClient initialized.")

    def _format_messages_for_openai(self, messages: List[Message]) -> Tuple[List[Dict[str, Any]], bool]:
        """
        将内部消息格式转换为OpenAI API所需的格式。
        
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
            # 自动转换为 OpenAI 多模态格式
            if isinstance(msg.content, list):
                openai_content = []
                for c in msg.content:
                    if isinstance(c, dict):
                        if "text" in c and "type" not in c:
                            # 普通文本，转为 openai 格式
                            openai_content.append({"type": "text", "text": c["text"]})
                        elif "inline_data" in c:
                            # 图片，转为 openai 格式
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
                            # 兜底：原样加入
                            openai_content.append(c)
                    else:
                        # 兜底：原样加入
                        openai_content.append(c)
                messages_for_llm.append({"role": msg.role, "content": openai_content})
            else:
                # 其它情况全部转为字符串
                if isinstance(msg.content, list):
                    text = "".join(str(c.get("text", "")) if isinstance(c, dict) else str(c) for c in msg.content)
                else:
                    text = str(msg.content)
                messages_for_llm.append({"role": msg.role, "content": text})
        
        return messages_for_llm, has_image

    async def get_response(
        self,
        messages: List[Message],
        **kwargs
    ) -> Tuple[str, str]:
        """
        调用 OpenAI GPT API，返回 (response_text, keyword)。
        """
        # 使用辅助方法格式化消息
        messages_for_llm, has_image = self._format_messages_for_openai(messages)
        
        # 使用类属性中的配置值
        model = "gpt-4.1" if has_image else self.extra_config.get("model", "gpt-4.1-mini")
        payload = {
            "model": model,
            "messages": messages_for_llm,
            "temperature": self.extra_config.get("temperature", 1.2)
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
                    raise ValueError("No choices in OpenAI response")
                llm_reply = response_data["choices"][0]["message"]["content"]
                print(f"LLM 回复: {llm_reply}")
                response_text, keyword = parse_llm_output(llm_reply)
                return response_text, keyword
        except httpx.TimeoutException:
            raise RuntimeError("Request to LLM timed out")
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"LLM API error: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Failed to get response from LLM: {str(e)}")