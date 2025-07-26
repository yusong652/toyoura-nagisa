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
from backend.chat.models import BaseMessage
from backend.chat.base_context_manager import BaseContextManager
from .message_formatter import MessageFormatter


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
        self.working_contents = MessageFormatter.format_messages_for_gemini(messages)
        
    
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
        
        # 多模态内容检测：支持新的统一格式和旧格式
        if isinstance(result, dict):
            # 检查新格式：包含 inline_data 字段的结果
            if 'inline_data' in result:
                blob = MessageFormatter.process_inline_data(result['inline_data'])
                if blob:
                    parts.append(types.Part(inline_data=blob))
                    print(f"[DEBUG] Created multimodal Part for {tool_name}: {blob.mime_type}, {len(blob.data)} bytes")
            
            # 兼容旧格式：data.processing_result.content.inline_data 路径
            elif result.get('data', {}).get('processing_result', {}).get('content_format') == 'inline_data':
                inline_data = result['data']['processing_result']['content']['inline_data']
                blob = MessageFormatter.process_inline_data(inline_data)
                if blob:
                    parts.append(types.Part(inline_data=blob))
                    print(f"[DEBUG] Created multimodal Part for {tool_name}: {blob.mime_type}, {len(blob.data)} bytes")
        
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
        # 处理不同类型的工具结果
        if isinstance(result, dict):
            response_dict = result.copy()
        elif isinstance(result, str):
            response_dict = {"result": result}
        else:
            response_dict = {"result": str(result)}
        
        # 对于多模态内容，排除大的 inline_data 避免重复
        if 'inline_data' in response_dict:
            response_dict = {k: v for k, v in response_dict.items() if k != 'inline_data'}
        
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
    
    def extract_tool_calls_from_response(self, response) -> List[Dict[str, Any]]:
        """
        从响应中提取工具调用信息
        
        Args:
            response: Gemini API响应对象
            
        Returns:
            工具调用列表，格式：[{'name': str, 'arguments': dict, 'id': str}]
        """
        try:
            candidate = response.candidates[0]
            if candidate.content.role != "model":
                return []
            
            tool_calls = []
            for part in candidate.content.parts:
                if part.function_call:
                    tool_call = {
                        'name': part.function_call.name,
                        'arguments': getattr(part.function_call, 'args', getattr(part.function_call, 'arguments', {})),
                        'id': getattr(part.function_call, 'id', part.function_call.name)
                    }
                    tool_calls.append(tool_call)
            
            return tool_calls
        except (AttributeError, IndexError):
            return []
    
