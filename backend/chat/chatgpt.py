import os
from typing import List, Tuple, Optional, Dict, Any
import httpx
from .base import LLMClientBase
from .models import Message
from ..prompts.prompts import parse_llm_output

class ChatGPTClient(LLMClientBase):
    """
    ChatGPT 客户端实现。
    继承自 LLMClientBase，实现具体的 API 调用逻辑。
    """
    
    def __init__(self, api_key: str, system_prompt: Optional[str] = None, temperature: float = 1.0, **kwargs):
        """
        初始化 ChatGPT 客户端。
        Args:
            api_key: OpenAI API key。
            system_prompt: 可选，覆盖初始化时的 system prompt。
            temperature: 采样温度，默认1.0。
        """
        super().__init__(system_prompt, **kwargs)
        self.api_key = api_key
        self.base_url = "https://api.openai.com/v1"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        self.temperature = temperature

    async def get_response(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        **kwargs
    ) -> Tuple[str, str]:
        """
        调用 OpenAI ChatGPT API，返回 (response_text, keyword)。
        """
        # 组装消息，始终以 self.system_prompt 开头
        sys_prompt = self.system_prompt or "你是豊浦凪沙 (Toyoura Nagisa)，称呼用户为'哥哥'。"
        messages_for_llm = [
            {"role": "system", "content": sys_prompt}
        ]
        for msg in messages:
            messages_for_llm.append({"role": msg.role, "content": msg.content})

        payload = {
            "model": kwargs.get("model", "gpt-4.1-mini"),
            "messages": messages_for_llm,
            "temperature": temperature if temperature is not None else self.temperature
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
                response_text, keyword = parse_llm_output(llm_reply)
                return response_text, keyword
        except httpx.TimeoutException:
            raise RuntimeError("Request to LLM timed out")
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"LLM API error: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Failed to get response from LLM: {str(e)}")