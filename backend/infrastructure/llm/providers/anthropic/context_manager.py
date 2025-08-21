"""
AnthropicContextManager - Anthropic Claude特化的上下文管理器

针对Anthropic API响应格式和工具调用机制优化的上下文管理实现。
采用与Gemini相同的双轨制设计：保持原始API格式用于工作上下文，标准化格式用于存储。
"""

from typing import Any
from backend.infrastructure.llm.base.context_manager import BaseContextManager


class AnthropicContextManager(BaseContextManager):
    """
    Anthropic Claude特化的上下文管理器
    
    专注于工作上下文管理：
    - 工作上下文：保持原始Anthropic API格式，确保完整性
    - 支持工具调用期间的上下文状态管理
    """
    
    def __init__(self):
        super().__init__(provider_name="anthropic")
        # 统一使用 working_contents，移除历史遗留的 working_messages
    
    def add_response(self, response) -> None:
        """
        添加Anthropic API响应到上下文中 - 按官方文档要求保存完整原始响应
        
        根据Anthropic官方文档：
        - "pass back the complete, unmodified thinking blocks to the API"
        - "always passing back all thinking blocks to the API"
        - 保持"模型推理流程和对话完整性"
        
        Args:
            response: Anthropic Messages API的响应对象
        """
        if not hasattr(response, 'content') or not response.content:
            raise ValueError("Invalid Anthropic API response format")
        
        # ✅ 按官方文档：过滤响应对象，只保留API支持的字段
        # 官方API只支持 role 和 content 字段
        filtered_message = {
            "role": response.role,
            "content": response.content
        }
        self.working_contents.append(filtered_message)
    
    def add_tool_result(self, tool_call_id: str, tool_name: str, result: Any) -> None:
        """
        添加工具执行结果到上下文中 - 统一实现
        
        使用消息格式化器处理格式，保持架构一致性
        
        Args:
            tool_call_id: 工具调用的唯一标识
            tool_name: 工具名称
            result: 工具执行结果
        """
        from .message_formatter import MessageFormatter
        
        # 使用消息格式化器处理工具结果格式
        working_content = MessageFormatter.format_tool_result_for_context(tool_call_id, tool_name, result)
        
        # 添加到工作上下文
        self.working_contents.append(working_content)
