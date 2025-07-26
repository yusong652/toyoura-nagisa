"""
BaseContextManager - 所有LLM客户端Context Manager的抽象基类

专为aiNagisa多LLM架构设计的统一上下文管理接口。
定义了所有Context Manager必须实现的核心方法，确保一致性和可扩展性。
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from backend.chat.models import BaseMessage


class BaseContextManager(ABC):
    """
    LLM客户端上下文管理器的抽象基类
    
    定义了统一的接口规范，支持：
    - 消息历史管理和状态隔离
    - 工具调用序列记录和追踪  
    - 响应内容的上下文保持
    """
    
    def __init__(self):
        """初始化基础状态"""
        self._messages_history: List[BaseMessage] = []
        self._tool_call_sequence: List[Dict[str, Any]] = []
        self._current_iteration = 0
        self._execution_metadata: Dict[str, Any] = {}
    
    @abstractmethod
    def initialize_from_messages(self, messages: List[BaseMessage]) -> None:
        """
        从输入消息列表初始化上下文管理器
        
        Args:
            messages: 输入的消息历史列表
        """
        pass
    
    @abstractmethod
    def add_response(self, response) -> None:
        """
        添加LLM API响应到上下文中
        
        Args:
            response: 来自LLM API的原始响应对象
        """
        pass
    
    
    @abstractmethod
    def extract_tool_calls_from_response(self, response) -> List[Dict[str, Any]]:
        """
        从响应中提取工具调用信息
        
        Args:
            response: LLM API响应对象
            
        Returns:
            List[Dict[str, Any]]: 工具调用信息列表，每个工具调用包含name、arguments、id等字段
        """
        pass
    
    @abstractmethod
    def add_tool_result(self, tool_call_id: str, tool_name: str, result: Any) -> None:
        """
        添加工具执行结果到上下文中
        
        Args:
            tool_call_id: 工具调用的唯一标识
            tool_name: 工具名称
            result: 工具执行结果
        """
        pass
    
    # === 通用辅助方法 ===
    
    def get_current_iteration(self) -> int:
        """获取当前迭代次数"""
        return self._current_iteration
    
    def increment_iteration(self) -> None:
        """增加迭代次数"""
        self._current_iteration += 1
    
    def get_messages_count(self) -> int:
        """获取消息历史数量"""
        return len(self._messages_history)
    
    def get_tool_calls_count(self) -> int:
        """获取工具调用总数"""
        return len(self._tool_call_sequence)
    
    def set_execution_metadata(self, key: str, value: Any) -> None:
        """设置执行元数据"""
        self._execution_metadata[key] = value
    
    def get_execution_metadata(self, key: str, default: Any = None) -> Any:
        """获取执行元数据"""
        return self._execution_metadata.get(key, default)
    
    def clear_context(self) -> None:
        """清理上下文状态"""
        self._messages_history.clear()
        self._tool_call_sequence.clear()
        self._current_iteration = 0
        self._execution_metadata.clear()
    
    def get_debug_info(self) -> Dict[str, Any]:
        """获取调试信息"""
        return {
            'messages_count': self.get_messages_count(),
            'tool_calls_count': self.get_tool_calls_count(),
            'current_iteration': self.get_current_iteration(),
            'execution_metadata': self._execution_metadata.copy()
        }