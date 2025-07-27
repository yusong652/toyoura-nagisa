# backend/chat/base.py

import os
from abc import ABC, abstractmethod # 导入 ABC 和 abstractmethod
from typing import List, Optional, Dict, Any, Tuple, AsyncGenerator, Union # 导入类型提示
from backend.infrastructure.llm.models import BaseMessage, LLMResponse         # 从同目录的 models.py 导入 Message 模型
from backend.config import get_system_prompt

# 定义一个简单的模型来表示 LLM 的输出（或者直接用 Tuple）
# from pydantic import BaseModel
# class LLMOutput(BaseModel):
#     response_text: str
#     keyword: str

class LLMClientBase(ABC):
    """
    LLM客户端的基础类，定义了所有LLM客户端需要实现的接口
    
    SOTA流式架构设计 - 专注于实时工具调用通知：
    - 核心接口：get_response() - 流式处理，实时通知
    - 专用接口：generate_title_from_messages(), generate_text_to_image_prompt()
    - 配置管理：update_config() - 动态配置更新
    
    架构优势：
    - 实时性：工具调用过程中即时推送状态更新
    - 高效性：AsyncGenerator实现零延迟事件传递
    - 一致性：统一的流式接口，避免冗余包装器
    """
    
    def __init__(self, tools_enabled: bool = True, extra_config: Dict[str, Any] = None):
        """
        初始化LLM客户端基础类
        
        Args:
            tools_enabled: 是否启用工具调用功能
            extra_config: 额外的配置参数
        """
        self.tools_enabled = tools_enabled
        self.extra_config = extra_config or {}

    @abstractmethod
    async def get_response(
        self,
        messages: List[BaseMessage],
        session_id: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[Union[Dict[str, Any], Tuple[BaseMessage, Dict[str, Any]]], None]:
        """
        [核心接口] 获取LLM响应，支持实时工具调用通知
        
        专为实时工具调用通知设计的SOTA架构，采用流式状态机模式：
        1. 实时yield工具调用开始/进行/完成通知
        2. 实时yield工具执行进度和状态更新
        3. 最终yield完整响应和执行元数据
        4. 完整的错误处理和恢复机制
        
        此方法是新架构的核心，解决了传统批量通知的延迟问题，
        让前端能够实时感知工具调用状态，大幅提升用户体验。
        
        Args:
            messages: 输入消息列表
            session_id: 会话ID，用于工具和上下文管理
            **kwargs: 额外参数（如max_iterations、temperature等）
            
        Yields:
            Union[Dict[str, Any], Tuple[BaseMessage, Dict[str, Any]]]:
            - Dict[str, Any]: 中间通知 (工具调用状态更新)
            - Tuple[BaseMessage, Dict[str, Any]]: 最终结果 (final_message, execution_metadata)
            
        Note:
            通知格式示例：
            - 工具开始: {'type': 'NAGISA_IS_USING_TOOL', 'tool_name': 'search', 'action_text': '正在搜索...'}
            - 工具进行: {'type': 'NAGISA_IS_USING_TOOL', 'tool_name': 'search', 'action_text': '使用搜索工具...'}
            - 工具完成: {'type': 'NAGISA_IS_USING_TOOL', 'tool_name': 'search', 'action_text': '完成搜索'}
            - 序列结束: {'type': 'NAGISA_TOOL_USE_CONCLUDED'}
            - 最终结果: (final_message, {'execution_id': '...', 'tool_calls_executed': 3, ...})
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

    # ========== 专用内容生成接口 ==========

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

    # Note: get_enhanced_response() 方法已被移除
    # 现在统一使用 get_response() 作为核心接口
    # 这样避免了冗余的包装器逻辑，提高了架构的一致性和性能