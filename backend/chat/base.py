# backend/chat/base.py

from abc import ABC, abstractmethod # 导入 ABC 和 abstractmethod
from typing import List, Tuple, Optional, Dict, Any       # 导入类型提示
from .models import Message         # 从同目录的 models.py 导入 Message 模型

# 定义一个简单的模型来表示 LLM 的输出（或者直接用 Tuple）
# from pydantic import BaseModel
# class LLMOutput(BaseModel):
#     response_text: str
#     keyword: str

class LLMClientBase(ABC):
    """
    Abstract Base Class for Large Language Model clients.
    统一 LLM 客户端接口，便于多模型扩展和主流程解耦。
    """

    def __init__(self, system_prompt: Optional[str] = None, **kwargs):
        """
        可选初始化方法，支持传递 system_prompt 及其他参数。
        子类可根据需要扩展。
        """
        self.system_prompt = system_prompt or ""
        self.extra_config = kwargs

    @abstractmethod
    async def get_response(
        self,
        messages: List[Message],
        **kwargs
    ) -> Tuple[str, str]:
        """
        异步发送对话历史给 LLM，返回回复文本和关键词。
        Args:
            messages: Message 对象列表，包含历史和最新用户输入。
            kwargs: 其他可选参数（如温度、max_tokens等）。
        Returns:
            (response_text, keyword)
        """
        pass

    def set_system_prompt(self, prompt: str):
        """动态设置/更新 system prompt。"""
        self.system_prompt = prompt

    def get_system_prompt(self) -> str:
        """获取当前 system prompt。"""
        return self.system_prompt

    def update_config(self, **kwargs):
        """动态更新额外配置参数。"""
        self.extra_config.update(kwargs)

    def get_config(self) -> Dict[str, Any]:
        """获取当前所有配置参数。"""
        return self.extra_config

    # 可以根据需要添加其他通用的抽象方法，比如初始化、设置参数等
    # def __init__(self, api_key: str, model_name: str, ...) -> None:
    #     pass