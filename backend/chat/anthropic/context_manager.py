"""
AnthropicContextManager - Anthropic Claude特化的上下文管理器

针对Anthropic API响应格式和工具调用机制优化的上下文管理实现。
采用与Gemini相同的双轨制设计：保持原始API格式用于工作上下文，标准化格式用于存储。
"""

from typing import List, Dict, Any
from backend.chat.base_context_manager import BaseContextManager
from backend.chat.models import BaseMessage, AssistantMessage, ToolResultMessage


class AnthropicContextManager(BaseContextManager):
    """
    Anthropic Claude特化的上下文管理器
    
    采用双轨制设计，与Gemini保持一致：
    - 工作上下文：保持原始Anthropic API格式，确保完整性
    - 存储上下文：转换为标准化消息格式，用于历史记录
    - 双轨制管理：确保API调用时的上下文完整性，同时支持标准化存储
    """
    
    def __init__(self):
        super().__init__()
        self.working_messages: List[Dict[str, Any]] = []  # 原始Anthropic API格式上下文
        self.storage_messages: List[BaseMessage] = []     # 标准化存储格式消息
    
    def initialize_from_messages(self, messages: List[BaseMessage]) -> None:
        """
        从输入消息列表初始化上下文管理器
        
        Args:
            messages: 输入的消息历史列表
        """
        from .message_formatter import MessageFormatter
        
        # 转换为Anthropic API格式的工作上下文
        self.working_messages = MessageFormatter.format_messages_for_anthropic(messages)
        
        # 保存存储格式的副本
        self.storage_messages = messages.copy()
    
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
        self.working_messages.append(filtered_message)
    
    def add_tool_result(self, tool_call_id: str, tool_name: str, result: Any) -> None:
        """
        添加工具执行结果到上下文中 - 简化实现
        
        直接构建符合Anthropic API要求的tool_result块并添加到工作上下文
        
        Args:
            tool_call_id: 工具调用的唯一标识
            tool_name: 工具名称
            result: 工具执行结果
        """
        from .message_formatter import MessageFormatter
        
        # 构建tool_result块
        tool_result_block = {
            "type": "tool_result",
            "tool_use_id": tool_call_id,
            "content": MessageFormatter.format_tool_result_content(result)
        }
        
        # 构建user消息包含tool_result
        user_message = {
            "role": "user",
            "content": [tool_result_block]
        }
        
        # 添加到工作上下文
        self.working_messages.append(user_message)
        
        # 创建对应的存储格式消息
        storage_message = ToolResultMessage(
            tool_call_id=tool_call_id,
            name=tool_name,
            content=result
        )
        self.storage_messages.append(storage_message)
    
    def get_working_messages(self) -> List[Dict[str, Any]]:
        """
        获取工作上下文（原始Anthropic API格式）
        
        Returns:
            原始格式的消息列表，用于API调用
        """
        return self.working_messages
    
    def get_storage_messages(self) -> List[BaseMessage]:
        """
        获取存储格式的消息列表
        
        Returns:
            标准化的消息列表，用于历史记录存储
        """
        return self.storage_messages
    
    
    def extract_tool_calls_from_response(self, response) -> List[Dict[str, Any]]:
        """
        从响应中提取工具调用信息
        
        Args:
            response: Anthropic API响应对象
            
        Returns:
            工具调用列表，格式：[{'name': str, 'arguments': dict, 'id': str}]
        """
        if not hasattr(response, 'content') or not response.content:
            return []
        
        if response.role != "assistant":
            return []
        
        tool_calls = []
        for item in response.content:
            if item.type == "tool_use":
                tool_calls.append({
                    'name': item.name,
                    'arguments': item.input,
                    'id': item.id
                })
        
        return tool_calls
    
    def should_continue_tool_calling(self) -> bool:
        """
        判断是否应该继续工具调用循环 - Anthropic client不使用此方法
        实际使用should_continue_tool_calling_from_response()
        
        Returns:
            bool: 始终返回False，因为client有自己的工具调用逻辑
        """
        return False
    
    def should_continue_tool_calling_from_response(self, response) -> bool:
        """
        根据API响应判断是否应该继续工具调用循环 - 与Gemini对齐
        
        Args:
            response: Anthropic API响应对象
            
        Returns:
            bool: 如果响应包含工具调用返回True
        """
        if not hasattr(response, 'content') or not response.content:
            return False
            
        # 检查响应中是否包含tool_use
        for item in response.content:
            if item.type == "tool_use":
                return True
        
        return False
    
    def finalize_and_get_storage_message(self, final_response) -> BaseMessage:
        """
        完成当前对话轮次，返回用于存储的最终消息对象
        
        Args:
            final_response: 最终的Anthropic API响应
            
        Returns:
            BaseMessage: 格式化后的用于存储的消息对象
        """
        # 提取最终响应内容
        content = []
        text_content = ""
        
        for item in final_response.content:
            if item.type == "text":
                content.append({"type": "text", "text": item.text})
                text_content += item.text
            elif item.type == "thinking":
                content.append({"type": "thinking", "thinking": item.thinking})
        
        # 解析关键词（如果有）
        keyword = None
        if text_content:
            from backend.chat.utils import parse_llm_output
            _, keyword = parse_llm_output(text_content)
        
        # 创建标准化的助手消息
        storage_message = AssistantMessage(
            role="assistant",
            content=content,
            keyword=keyword
        )
        
        # 添加到存储消息列表
        self.storage_messages.append(storage_message)
        
        return storage_message
    
    def clear_context(self) -> None:
        """清理上下文状态"""
        super().clear_context()
        self.working_messages.clear()
        self.storage_messages.clear()