# backend/chat/base.py

from abc import ABC, abstractmethod # 导入 ABC 和 abstractmethod
from typing import List, Tuple, Optional, Dict, Any       # 导入类型提示
from backend.chat.models import Message, LLMResponse         # 从同目录的 models.py 导入 Message 模型

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

    @abstractmethod
    async def generate_title_from_messages(
        self,
        first_user_message: Message,
        first_assistant_message: Message,
        title_generation_system_prompt: Optional[str] = None
    ) -> Optional[str]:
        """
        根据对话的第一轮消息生成一个简洁的对话标题。
        不同的LLM客户端会有不同的实现方式，以适应各自API的特点。

        Args:
            first_user_message: 用户的第一条消息（Message对象，支持多模态）
            first_assistant_message: AI助手对第一条消息的回复（Message对象，支持多模态）
            title_generation_system_prompt: 用于生成标题的特定system prompt，
                                           如果不提供则使用客户端默认的system prompt

        Returns:
            生成的对话标题，如果生成失败则返回None
        """
        pass

    @abstractmethod
    async def handle_function_call_closed_loop(
        self,
        messages: List[Message],
        tool_call: dict,
        tool_result: Any,
        **kwargs
    ) -> 'LLMResponse':
        """
        Handle the function call closed-loop: after receiving a function_call from LLM, call the tool,
        then send the function call and its result back to the LLM to get the final natural language response.
        Args:
            messages: The original conversation history (list of Message)
            tool_call: The function call info (name, arguments, etc)
            tool_result: The result from the tool execution
        Returns:
            LLMResponse: The final LLM response after the closed-loop
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