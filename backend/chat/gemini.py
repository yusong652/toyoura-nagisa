import os
from typing import List, Tuple, Optional, Dict, Any
import httpx
import google.generativeai as genai
from .base import LLMClientBase
from .models import Message
from ..prompts.prompts import parse_llm_output

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
        genai.configure(api_key=self.api_key)
        self.temperature = temperature

    async def get_response(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        **kwargs
    ) -> Tuple[str, str]:
        """
        调用 Google Gemini API，返回 (response_text, keyword)。
        """
        # 组装消息，始终以 self.system_prompt 开头
        sys_prompt = self.system_prompt or "你是豊浦凪沙 (Toyoura Nagisa)，称呼用户为'哥哥'。"
        
        # 初始化 Gemini 模型
        model = genai.GenerativeModel('gemini-pro')
        
        # 准备对话历史
        chat = model.start_chat(history=[])
        
        # 添加系统提示
        chat.send_message(sys_prompt)
        
        # 处理用户消息
        for msg in messages:
            if isinstance(msg.content, list):
                # 处理多模态内容
                content = " ".join([c.get("text", "") for c in msg.content if c.get("type") == "text"])
                if content:
                    chat.send_message(content)
            else:
                chat.send_message(msg.content)
        
        try:
            # 获取响应
            response = chat.send_message(
                "",
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature if temperature is not None else self.temperature
                )
            )
            
            # 解析响应
            llm_reply = response.text
            response_text, keyword = parse_llm_output(llm_reply)
            return response_text, keyword
            
        except Exception as e:
            raise RuntimeError(f"Failed to get response from Gemini: {str(e)}") 