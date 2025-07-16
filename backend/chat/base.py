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
    
    SOTA架构抽象基类 - 为新的状态机工具调用架构设计
    
    此基类定义了统一的LLM客户端接口，专为以下特性优化：
    - 内部状态机工具调用
    - 简化的响应模型（移除ResponseType依赖）
    - 增强的元数据支持
    - 会话级别的功能支持
    """

    def __init__(self, **kwargs):
        """
        初始化LLM客户端基类
        
        Args:
            **kwargs: 客户端配置参数
        """
        self.extra_config = kwargs
        self.tools_enabled = kwargs.get("tools_enabled", True)  # 默认开启工具

    @abstractmethod
    async def get_response(
        self,
        messages: List[BaseMessage],
        session_id: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        [核心接口] 异步获取LLM响应
        
        此方法应该返回一个LLMResponse对象，包含处理后的响应内容。
        对于支持工具调用的客户端，应该在内部处理所有工具调用逻辑。
        
        Args:
            messages: Message 对象列表，包含历史和最新用户输入
            session_id: 可选的会话ID，用于支持会话级别的功能（如工具缓存）
            **kwargs: 其他可选参数（如温度、max_tokens等）
            
        Returns:
            LLMResponse: 包含响应内容和元数据的响应对象
            
        Note:
            对于新的SOTA架构，工具调用应该在客户端内部通过状态机处理，
            不应该依赖API层的递归逻辑。
        """
        pass

    def update_config(self, **kwargs):
        """
        更新客户端配置
        
        Args:
            **kwargs: 要更新的配置参数
        """
        # 提供默认实现，子类可以覆盖
        for key, value in kwargs.items():
            setattr(self, key, value)
            # 同时更新 extra_config
            self.extra_config[key] = value

    # ========== 可选扩展接口 ==========
    
    async def get_enhanced_response(
        self,
        messages: List[BaseMessage],
        session_id: Optional[str] = None,
        **kwargs
    ) -> Tuple[BaseMessage, Dict[str, Any]]:
        """
        [可选接口] 获取增强响应，包含详细元数据
        
        此方法为支持高级功能的客户端提供，返回最终消息和执行元数据。
        
        Args:
            messages: 输入消息列表
            session_id: 会话ID
            **kwargs: 额外参数
            
        Returns:
            Tuple[BaseMessage, Dict[str, Any]]: (最终消息, 执行元数据)
            
        Raises:
            NotImplementedError: 如果客户端不支持此功能
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support enhanced response mode"
        )

    async def generate_title_from_messages(
        self,
        first_user_message: BaseMessage,
        first_assistant_message: BaseMessage,
        title_generation_system_prompt: Optional[str] = None
    ) -> Optional[str]:
        """
        [可选接口] 根据对话消息生成标题
        
        Args:
            first_user_message: 第一条用户消息
            first_assistant_message: 第一条助手消息
            title_generation_system_prompt: 可选的标题生成系统提示
            
        Returns:
            生成的标题字符串，如果失败则返回None
            
        Raises:
            NotImplementedError: 如果客户端不支持此功能
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support title generation"
        )

    async def generate_text_to_image_prompt(
        self, 
        session_id: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        """
        [可选接口] 生成文生图提示词
        
        Args:
            session_id: 会话ID，用于获取上下文
            
        Returns:
            包含文本提示和负面提示的字典，如果失败则返回None
            
        Raises:
            NotImplementedError: 如果客户端不支持此功能
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support image prompt generation"
        )