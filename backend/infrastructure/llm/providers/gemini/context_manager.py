"""
Gemini Context Manager - 管理工具调用期间的原始上下文

此模块负责在工具调用过程中保持 Gemini API 原始响应格式，
确保思维链和验证字段完整性，同时处理存储格式的消息。

核心设计原则：
1. 工作上下文：保持原始 Gemini API 格式，包含完整的思维链信息和验证字段
2. 专注于工具调用期间的上下文状态管理
"""

from typing import List, Dict, Any, Optional, Tuple
from google.genai import types
from backend.domain.models.messages import BaseMessage
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
        super().__init__()
        self.working_contents: List[Dict[str, Any]] = []  # 原始Gemini API格式上下文
        
    def initialize_from_messages(self, messages: List[BaseMessage]) -> None:
        """
        从历史消息初始化上下文管理器
        
        Args:
            messages: 历史消息列表，包含用户消息、助手消息等
        """
        # 转换为Gemini API格式的工作上下文
        self.working_contents = GeminiMessageFormatter.format_messages_for_gemini(messages)
        
    
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
    
    def _create_multimodal_parts(self, tool_name: str, result: Dict[str, Any]) -> List[Any]:
        """
        创建多模态内容的 Parts
        
        Args:
            result: 工具执行结果
            tool_name: 工具名称
            
        Returns:
            包含多模态内容的 Parts 列表
        """
        parts = []
        
        # 使用基类方法提取 inline_data
        inline_data = self.extract_inline_data(result)
        if inline_data:
            blob = GeminiMessageFormatter._process_inline_data(inline_data)
            if blob:
                parts.append(types.Part(inline_data=blob))
                self.debug_multimodal_content(tool_name, blob.mime_type, len(blob.data))
        
        return parts
    
    def _create_function_response_part(self, tool_name: str, result: Any) -> types.Part:
        """
        创建函数响应 Part
        
        Args:
            tool_name: 工具名称
            result: 工具执行结果
            
        Returns:
            函数响应的 Part 对象
        """
        # 使用基类方法处理工具结果
        response_dict = self.process_tool_result_for_llm(result)
        
        # 使用基类方法过滤多模态内容
        response_dict = self.filter_multimodal_from_response(response_dict)
        
        function_response = types.FunctionResponse(
            name=tool_name,
            response=response_dict
        )
        
        return types.Part(function_response=function_response)
    
    
    def get_working_contents(self) -> List[Dict[str, Any]]:
        """
        获取工作上下文（原始Gemini API格式）
        
        Returns:
            原始格式的上下文列表，用于API调用
        """
        return self.working_contents
    
    def add_tool_result(self, tool_call_id: str, tool_name: str, result: Any) -> None:
        """添加工具执行结果到上下文中 - 基类接口实现"""
        # tool_call_id is required by interface but not used in this implementation
        parts = []
        
        # 创建多模态内容 Parts（如果存在）
        multimodal_parts = self._create_multimodal_parts(tool_name, result)
        parts.extend(multimodal_parts)
        
        # 创建函数响应 Part
        function_part = self._create_function_response_part(tool_name, result)
        parts.append(function_part)
        
        # 构建工作上下文内容
        working_content = {
            "role": "user",
            "parts": parts
        }
        
        # 添加到工作上下文
        self.working_contents.append(working_content)
    
    
    
