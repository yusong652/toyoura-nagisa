import os
import httpx
from typing import List, Tuple, Optional, Dict, Any
from google import genai
from google.genai import types
from backend.config import get_llm_specific_config
from .base import LLMClientBase
from .models import Message
from .utils import parse_llm_output

class GeminiClient(LLMClientBase):
    """
    Google Gemini 客户端实现。
    继承自 LLMClientBase，实现具体的 API 调用逻辑。
    """
    
    def __init__(self, api_key: str, system_prompt: Optional[str] = None, temperature: float = 1.2, **kwargs):
        """
        初始化 Gemini 客户端。
        Args:
            api_key: Google API key。
            system_prompt: 可选，覆盖初始化时的 system prompt。
            temperature: 采样温度，默认1.2。
        """
        super().__init__(system_prompt, **kwargs)
        self.api_key = api_key
        self.client = genai.Client(api_key=self.api_key)
        self.temperature = temperature
        self.safety_settings = [
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE
            )
        ]
        print(f"Gemini Client initialized.")

    def map_role(self, role: str) -> str:
        if role == "assistant":
            return "model"
        # system 也映射为 user，或直接拼到第一条 user 消息
        return "user"

    async def get_response(self, messages: List[Message], temperature: Optional[float] = None, **kwargs) -> Tuple[str, str]:
        contents = []
        # system prompt 通过 config 传递，不加到 contents
        for msg in messages:
            parts = []
            if isinstance(msg.content, list):
                for item in msg.content:
                    if "text" in item:
                        parts.append({"text": item['text']})
                    elif "inline_data" in item:
                        # 保证图片用inline_data结构
                        parts.append({
                            "inline_data": {
                                "mime_type": item['inline_data'].get('mime_type', 'image/png'),
                                "data": item['inline_data']['data']
                            }
                        })
            else:
                parts.append({"text": msg.content})
            contents.append({"role": msg.role, "parts": parts})

        # 只允许Gemini支持的参数
        allowed_keys = {"temperature", "top_p", "top_k", "max_output_tokens", "stop_sequences"}
        user_config = kwargs.get('generation_config', {})
        if isinstance(user_config, dict):
            filtered_config = {k: v for k, v in user_config.items() if k in allowed_keys}
        else:
            filtered_config = {}
        config = types.GenerateContentConfig(
            system_instruction=self.system_prompt,
            safety_settings=self.safety_settings,
            temperature=temperature if temperature is not None else self.temperature,
            topP=kwargs.get('top_p', get_llm_specific_config('gemini').get('top_p', 0.95)),
            topK=kwargs.get('top_k', get_llm_specific_config('gemini').get('top_k', 40)),
            max_output_tokens=kwargs.get('max_output_tokens', get_llm_specific_config('gemini').get('maxOutputTokens', 2048)),
            **filtered_config
        )

        # print(f"contents: {contents}")
        try:
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=contents,
                config=config
            )
            if hasattr(response, 'candidates') and response.candidates and response.candidates[0].content.parts:
                response_text = response.candidates[0].content.parts[0].text
            else:
                response_text = ""  # 处理没有生成内容的情况
            response_text, keyword = parse_llm_output(response_text)
            return response_text, keyword
        except Exception as e:
            print(f"Gemini API error: {e}")
            raise RuntimeError(f"Failed to get response from Gemini: {str(e)}")