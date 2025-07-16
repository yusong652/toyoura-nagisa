"""
Gemini Context Manager - 管理工具调用期间的原始上下文

此模块负责在工具调用过程中保持 Gemini API 原始响应格式，
确保思维链和验证字段完整性，同时处理存储格式的消息。

核心设计原则：
1. 工作上下文：保持原始 Gemini API 格式，包含完整的思维链信息和验证字段
2. 存储上下文：转换为标准化消息格式，用于本地存储和历史记录
3. 双轨制管理：确保API调用时的上下文完整性，同时支持标准化存储
"""

from typing import List, Dict, Any, Optional, Tuple
from google.genai import types
from backend.chat.models import BaseMessage, ToolResultMessage, message_factory
from .message_formatter import MessageFormatter


class GeminiContextManager:
    """
    管理 Gemini API 工具调用过程中的双轨制上下文
    
    核心功能：
    - 维护原始格式的工作上下文，确保思维链完整性
    - 管理标准化的存储上下文，用于历史记录
    - 提供工具调用期间的上下文状态管理
    - 支持多轮工具调用的上下文连续性
    
    使用场景：
    1. 初始化：从历史消息创建初始上下文
    2. 工具调用：添加原始响应和工具结果
    3. 最终化：创建用于存储的标准化消息
    """
    
    def __init__(self):
        """初始化上下文管理器"""
        self.working_contents: List[Dict[str, Any]] = []  # 原始Gemini API格式上下文
        self.storage_messages: List[BaseMessage] = []     # 标准化存储格式消息
        self._tool_call_sequence: List[Dict[str, Any]] = []  # 工具调用序列追踪
        
    def initialize_from_messages(self, messages: List[BaseMessage]) -> None:
        """
        从历史消息初始化上下文管理器
        
        Args:
            messages: 历史消息列表，包含用户消息、助手消息等
        """
        # 转换为Gemini API格式的工作上下文
        self.working_contents = MessageFormatter.format_messages_for_gemini(messages)
        
        # 保存存储格式的副本
        self.storage_messages = messages.copy()
        
        # 清空工具调用序列
        self._tool_call_sequence = []
    
    def add_raw_response(self, response) -> Dict[str, Any]:
        """
        添加原始 Gemini API 响应到工作上下文
        
        按照官方最佳实践，直接使用 candidate.content 而不是重构，
        确保完整保留所有原始字段，包括思维链、验证字段等。
        
        Args:
            response: 原始 Gemini API 响应对象
            
        Returns:
            添加到上下文的原始内容字典
        """
        if not (hasattr(response, 'candidates') and response.candidates and 
                hasattr(response.candidates[0], 'content')):
            raise ValueError("Invalid Gemini API response format")
        
        candidate = response.candidates[0]
        
        # ✅ 官方最佳实践：直接使用 candidate.content，不重构任何内容
        # 这确保了完整保留所有原始字段，包括思维链、验证字段等
        raw_content = candidate.content
        
        # 添加到工作上下文
        self.working_contents.append(raw_content)
        
        # 记录工具调用序列（如果存在）
        self._record_tool_calls_from_response(response)
        
        return raw_content
    
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
        
        # 检查并处理 inline_data（多模态内容）
        if isinstance(result, dict) and 'inline_data' in result:
            inline_data = result['inline_data']
            
            # 使用统一的 inline_data 处理方法，保持架构一致性
            blob = MessageFormatter.process_inline_data(inline_data)
            if blob:
                parts.append(types.Part(inline_data=blob))
                print(f"[DEBUG] Created multimodal Part for {tool_name}: {blob.mime_type}, {len(blob.data)} bytes")
            else:
                print(f"[WARNING] Failed to process inline_data for {tool_name}")
        
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
            response_dict['multimodal_content'] = 'Processed as separate image Part'
        
        function_response = types.FunctionResponse(
            name=tool_name,
            response=response_dict
        )
        
        return types.Part(function_response=function_response)
    
    def add_tool_response(self, tool_name: str, tool_call_id: str, result: Any) -> Dict[str, Any]:
        """
        添加工具响应到工作上下文
        
        Args:
            tool_name: 工具名称
            tool_call_id: 工具调用ID
            result: 工具执行结果
            
        Returns:
            添加到上下文的工具响应内容
        """
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
        
        # 创建对应的存储格式消息
        storage_message = ToolResultMessage(
            tool_call_id=tool_call_id,
            name=tool_name,
            content=result
        )
        self.storage_messages.append(storage_message)
        
        return working_content
    
    def get_working_contents(self) -> List[Dict[str, Any]]:
        """
        获取工作上下文（原始Gemini API格式）
        
        Returns:
            原始格式的上下文列表，用于API调用
        """
        return self.working_contents
    
    def get_storage_messages(self) -> List[BaseMessage]:
        """
        获取存储格式的消息列表
        
        Returns:
            标准化的消息列表，用于历史记录存储
        """
        return self.storage_messages
    
    def finalize_and_get_storage_message(self, final_response, keyword: Optional[str] = None) -> BaseMessage:
        """
        完成工具调用序列，创建最终的存储消息
        
        此方法在工具调用完成后调用，用于：
        1. 处理最终的文本响应
        2. 创建用于存储的标准化消息
        3. 清理临时状态
        
        Args:
            final_response: 最终的 Gemini API 响应（通常是文本响应）
            keyword: 提取的关键词
            
        Returns:
            格式化后的存储消息
        """
        # 使用ResponseProcessor格式化最终响应
        from .response_processor import ResponseProcessor
        llm_response = ResponseProcessor.format_llm_response(final_response)
        
        # 创建标准化的助手消息
        storage_message = message_factory({
            "role": "assistant",
            "content": llm_response.content,
            "keyword": keyword
        })
        
        # 添加到存储消息列表
        self.storage_messages.append(storage_message)
        
        return storage_message
    
    def has_pending_tool_calls(self) -> bool:
        """
        检查是否有待处理的工具调用
        
        Returns:
            如果有待处理的工具调用返回True
        """
        return len(self._tool_call_sequence) > 0
    
    def get_tool_call_sequence(self) -> List[Dict[str, Any]]:
        """
        获取当前的工具调用序列
        
        Returns:
            工具调用序列列表
        """
        return self._tool_call_sequence.copy()
    
    def clear_tool_call_sequence(self) -> None:
        """清空工具调用序列"""
        self._tool_call_sequence = []
    
    def _record_tool_calls_from_response(self, response) -> None:
        """
        从响应中记录工具调用信息
        
        Args:
            response: Gemini API 响应对象
        """
        if not (hasattr(response, 'candidates') and response.candidates):
            return
            
        candidate = response.candidates[0]
        if not (hasattr(candidate, 'content') and hasattr(candidate.content, 'parts')):
            return
        
        # 提取工具调用
        for part in candidate.content.parts:
            if hasattr(part, 'function_call') and part.function_call:
                tool_call = {
                    'name': part.function_call.name,
                    'arguments': part.function_call.args if hasattr(part.function_call, 'args') else part.function_call.arguments,
                    'id': part.function_call.id or part.function_call.name
                }
                self._tool_call_sequence.append(tool_call)
    
    def extract_tool_calls_from_latest_response(self) -> List[Dict[str, Any]]:
        """
        从最新添加的响应中提取工具调用信息
        
        Returns:
            工具调用列表，格式：[{'name': str, 'arguments': dict, 'id': str}]
        """
        if not self.working_contents:
            return []
        
        latest_content = self.working_contents[-1]
        
        # 安全地检查 role，支持对象和字典两种格式
        content_role = None
        if hasattr(latest_content, 'role'):
            content_role = latest_content.role
        elif isinstance(latest_content, dict) and 'role' in latest_content:
            content_role = latest_content['role']
        
        if content_role != "model":
            return []
        
        tool_calls = []
        
        # 安全地获取 parts，支持对象和字典两种格式
        parts = []
        if hasattr(latest_content, 'parts'):
            parts = latest_content.parts
        elif isinstance(latest_content, dict) and 'parts' in latest_content:
            parts = latest_content['parts']
        
        for part in parts:
            if hasattr(part, 'function_call') and part.function_call:
                tool_call = {
                    'name': part.function_call.name,
                    'arguments': part.function_call.args if hasattr(part.function_call, 'args') else part.function_call.arguments,
                    'id': part.function_call.id or part.function_call.name
                }
                tool_calls.append(tool_call)
        
        return tool_calls
    
    def should_continue_tool_calling(self) -> bool:
        """
        检查最新响应是否包含工具调用，判断是否需要继续工具调用流程
        
        Returns:
            如果需要继续工具调用返回True
        """
        tool_calls = self.extract_tool_calls_from_latest_response()
        return len(tool_calls) > 0