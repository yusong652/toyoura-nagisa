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
from backend.chat.models import BaseMessage, UserToolMessage, AssistantMessage, message_factory
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
        
        这是核心方法，确保原始响应格式完整保留，包括：
        - 思维链内容 (thinking)
        - 验证字段 (如 thought_signature)
        - 工具调用信息
        - 所有原始API字段
        
        Args:
            response: 原始 Gemini API 响应对象
            
        Returns:
            添加到上下文的原始内容字典
        """
        if not (hasattr(response, 'candidates') and response.candidates and 
                hasattr(response.candidates[0], 'content')):
            raise ValueError("Invalid Gemini API response format")
        
        candidate = response.candidates[0]
        
        # 构建完整的原始内容，保持所有字段
        raw_content = {
            "role": "model",
            "parts": []
        }
        
        # 保留完整的parts列表，包括思维、文本和工具调用
        if hasattr(candidate.content, 'parts'):
            # 直接使用原始parts，确保没有信息丢失
            raw_content["parts"] = candidate.content.parts
        
        # 如果有顶层思维内容，也要保留
        if hasattr(candidate, 'thought') and candidate.thought:
            # 注意：顶层thought通常已经包含在parts中，这里做额外记录
            raw_content["_top_level_thought"] = candidate.thought
        
        # 添加到工作上下文
        self.working_contents.append(raw_content)
        
        # 记录工具调用序列（如果存在）
        self._record_tool_calls_from_response(response)
        
        return raw_content
    
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
        # 处理不同类型的工具结果
        if isinstance(result, dict):
            response_dict = result
        elif isinstance(result, str):
            response_dict = {"result": result}
        else:
            response_dict = {"result": str(result)}
        
        # 创建标准的Gemini API工具响应格式
        function_response = types.FunctionResponse(
            name=tool_name,
            response=response_dict
        )
        
        # 构建工作上下文内容
        working_content = {
            "role": "user",
            "parts": [types.Part(function_response=function_response)]
        }
        
        # 添加到工作上下文
        self.working_contents.append(working_content)
        
        # 创建对应的存储格式消息
        storage_message = UserToolMessage(
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
        if latest_content.get("role") != "model":
            return []
        
        tool_calls = []
        parts = latest_content.get("parts", [])
        
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
    
    def get_context_summary(self) -> Dict[str, Any]:
        """
        获取上下文状态摘要，用于调试和监控
        
        Returns:
            包含上下文状态信息的字典
        """
        return {
            "working_contents_count": len(self.working_contents),
            "storage_messages_count": len(self.storage_messages),
            "pending_tool_calls": len(self._tool_call_sequence),
            "last_role": self.working_contents[-1]["role"] if self.working_contents else None,
            "has_tool_calls": self.should_continue_tool_calling()
        } 