# backend/chat/base.py

from abc import ABC, abstractmethod # 导入 ABC 和 abstractmethod
from typing import List, Tuple, Optional, Dict, Any       # 导入类型提示
from backend.chat.models import Message, LLMResponse, BaseMessage         # 从同目录的 models.py 导入 Message 模型
from backend.config import get_system_prompt

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

    def __init__(self, **kwargs):
        """
        可选初始化方法，支持传递其他参数。
        """
        self.extra_config = kwargs
        self.tools_enabled = kwargs.get("tools_enabled", True)  # 默认开启工具

    @abstractmethod
    async def get_response(
        self,
        messages: List[BaseMessage],
        session_id: Optional[str] = None,
        **kwargs
    ) -> Tuple[str, str]:
        """
        异步发送对话历史给 LLM，返回回复文本和关键词。
        Args:
            messages: Message 对象列表，包含历史和最新用户输入。
            session_id: 可选的会话ID，用于支持会话级别的功能（如工具缓存）。
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

    def update_config(self, **kwargs):
        """动态更新额外配置参数。"""
        self.extra_config.update(kwargs)
        if "tools_enabled" in kwargs:
            self.tools_enabled = kwargs["tools_enabled"]

    def get_config(self) -> Dict[str, Any]:
        """获取当前所有配置参数。"""
        return self.extra_config

    async def get_function_call_schemas(self):
        """
        获取所有 MCP 工具的 schema，供 LLM function call 注册用。
        如果 tools_enabled 为 False，则返回 None。
        """
        if not self.tools_enabled:
            return None
        # 子类需要实现具体的获取工具schema的逻辑
        raise NotImplementedError("Subclasses must implement get_function_call_schemas")

    # 可以根据需要添加其他通用的抽象方法，比如初始化、设置参数等
    # def __init__(self, api_key: str, model_name: str, ...) -> None:
    #     pass