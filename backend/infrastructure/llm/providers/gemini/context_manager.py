"""
Gemini Context Manager - 管理工具调用期间的原始上下文

此模块负责在工具调用过程中保持 Gemini API 原始响应格式，
确保思维链和验证字段完整性，同时处理存储格式的消息。

核心设计原则：
1. 工作上下文：保持原始 Gemini API 格式，包含完整的思维链信息和验证字段
2. 专注于工具调用期间的上下文状态管理
"""

from typing import Any
from backend.infrastructure.llm.base.context_manager import BaseContextManager
from .message_formatter import GeminiMessageFormatter


class GeminiContextManager(BaseContextManager):
    """
    管理 Gemini API 工具调用过程中的上下文
    
    核心功能：
    - 维护原始格式的工作上下文，确保思维链完整性
    - 提供工具调用期间的上下文状态管理
    - 支持多轮工具调用的上下文连续性
    
    使用场景：
    1. 初始化：从历史消息创建初始上下文
    2. 工具调用：添加原始响应和工具结果
    3. 最终化：创建用于存储的标准化消息
    """
    
    def __init__(self):
        """初始化上下文管理器"""
        super().__init__(provider_name="gemini")
        # working_contents 已在基类中初始化
    
    def add_response(self, response) -> None:
        """
        添加原始 Gemini API 响应到工作上下文
        
        按照官方最佳实践，直接使用 candidate.content 而不是重构，
        确保完整保留所有原始字段，包括思维链、验证字段等。
        
        Args:
            response: 原始 Gemini API 响应对象
        """
        try:
            candidate = response.candidates[0]
        except (AttributeError, IndexError):
            raise ValueError("Invalid Gemini API response format")
        
        # ✅ 官方最佳实践：直接使用 candidate.content，不重构任何内容
        # 这确保了完整保留所有原始字段，包括思维链、验证字段等
        raw_content = candidate.content
        
        # 添加到工作上下文
        self.working_contents.append(raw_content)
    
    def add_tool_result(self, tool_call_id: str, tool_name: str, result: Any) -> None:
        """
        添加工具执行结果到上下文中 - 统一实现
        
        使用消息格式化器处理格式，保持与Anthropic一致的架构模式
        
        Args:
            tool_call_id: 工具调用的唯一标识（接口要求，Gemini不使用）
            tool_name: 工具名称
            result: 工具执行结果
        """
        # 使用消息格式化器处理工具结果格式
        working_content = GeminiMessageFormatter.format_tool_result_for_context(tool_name, result)
        
        # 添加到工作上下文
        self.working_contents.append(working_content)
    
    
    
