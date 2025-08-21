"""
Enhanced Context Manager with Tool History Preservation

This module provides an enhanced context manager that preserves tool calling
history across conversation rounds, solving the "tool amnesia" problem in
multi-turn conversations.

Key Features:
- Tool call-result pairing with atomicity guarantees
- Provider-locked sessions for optimal performance
- Configurable context length management
- Foundation for future compression capabilities
"""

from abc import abstractmethod
from typing import List, Dict, Any, Optional, Tuple, NamedTuple
from datetime import datetime
from backend.infrastructure.llm.base.context_manager import BaseContextManager


class ToolCallPair(NamedTuple):
    """
    Atomic tool call-result pair for context preservation.
    
    Attributes:
        request: Tool call request from LLM response
        result: Tool execution result
        timestamp: When the tool was called
        importance_score: For future compression decisions
        tool_name: Name of the tool for quick reference
        tool_call_id: Unique identifier for the tool call
    """
    request: Dict[str, Any]
    result: Dict[str, Any]
    timestamp: datetime
    importance_score: float
    tool_name: str
    tool_call_id: str


class EnhancedContextManager(BaseContextManager):
    """
    Enhanced context manager with tool history preservation.
    
    This manager extends the base context manager to maintain tool calling
    history across conversation rounds, ensuring the LLM has access to its
    previous tool usage for better decision making.
    
    Design Principles:
    1. Provider-locked sessions for optimal performance
    2. Atomic tool call-result pairs to prevent orphaned results
    3. Configurable context windows for different message types
    4. Extensible compression interface for future enhancements
    """
    
    def __init__(self, provider_name: str):
        """
        Initialize enhanced context manager.
        
        Args:
            provider_name: LLM provider name (session will be locked to this provider)
        """
        super().__init__(provider_name)
        
        # Tool history management
        self.tool_call_pairs: List[ToolCallPair] = []
        self.pending_tool_calls: Dict[str, Dict[str, Any]] = {}  # Temporary storage for unpaired calls
        
        # Session configuration
        self.provider_locked = True
        self.session_provider = provider_name
        
        # Context window configuration (can be adjusted dynamically)
        self.max_tool_pairs = 10  # Maximum tool pairs to keep in active context
        self.max_normal_messages = 20  # Maximum normal messages
        self.tool_context_ratio = 0.3  # 30% of context for tools
        
    def initialize_from_messages_with_tools(
        self, 
        messages: List[Any],
        tool_history: Optional[List[ToolCallPair]] = None
    ) -> None:
        """
        Initialize context with both messages and tool history.
        
        Args:
            messages: Conversation messages
            tool_history: Previous tool call-result pairs from storage
        """
        # Initialize base messages
        self.initialize_from_messages(messages)
        
        # Restore tool history if provided
        if tool_history:
            self.tool_call_pairs = tool_history
            self._inject_tool_history_into_context()
    
    def _inject_tool_history_into_context(self) -> None:
        """
        Inject relevant tool history into working context.
        
        This method selectively adds tool call-result pairs to the working
        context based on importance and recency.
        """
        # Get recent important tool pairs
        relevant_pairs = self._select_relevant_tool_pairs()
        
        # Each provider will implement injection differently
        self._provider_specific_injection(relevant_pairs)
    
    @abstractmethod
    def _provider_specific_injection(self, tool_pairs: List[ToolCallPair]) -> None:
        """
        Provider-specific method to inject tool history into working context.
        
        Args:
            tool_pairs: Tool pairs to inject
        """
        pass
    
    def _select_relevant_tool_pairs(self) -> List[ToolCallPair]:
        """
        Select which tool pairs to include in active context.
        
        Returns:
            List of tool pairs to include based on importance and recency
        """
        if not self.tool_call_pairs:
            return []
        
        # Sort by importance and recency
        sorted_pairs = sorted(
            self.tool_call_pairs,
            key=lambda p: (p.importance_score, p.timestamp.timestamp()),
            reverse=True
        )
        
        # Take top N pairs within limits
        return sorted_pairs[:self.max_tool_pairs]
    
    def add_response_with_tool_tracking(self, response: Any) -> None:
        """
        Add response and track any tool calls for pairing.
        
        Args:
            response: Provider-specific response object
        """
        # First, use base add_response
        self.add_response(response)
        
        # Then extract and track tool calls
        tool_calls = self._extract_tool_calls_from_response(response)
        for tool_call in tool_calls:
            tool_id = tool_call.get('id', tool_call.get('name', ''))
            self.pending_tool_calls[tool_id] = {
                'request': tool_call,
                'timestamp': datetime.now(),
                'response_context': self._extract_response_context(response)
            }
    
    @abstractmethod
    def _extract_tool_calls_from_response(self, response: Any) -> List[Dict[str, Any]]:
        """
        Extract tool calls from provider-specific response.
        
        Args:
            response: Provider response object
            
        Returns:
            List of tool call dictionaries
        """
        pass
    
    @abstractmethod
    def _extract_response_context(self, response: Any) -> Dict[str, Any]:
        """
        Extract relevant context from response for tool pairing.
        
        Args:
            response: Provider response object
            
        Returns:
            Context dictionary with provider-specific info
        """
        pass
    
    def add_tool_result_with_pairing(
        self, 
        tool_call_id: str, 
        tool_name: str, 
        result: Any
    ) -> None:
        """
        Add tool result and create atomic pair with its request.
        
        Args:
            tool_call_id: Tool call identifier
            tool_name: Name of the tool
            result: Tool execution result
        """
        # First, use base add_tool_result
        self.add_tool_result(tool_call_id, tool_name, result)
        
        # Then create pair if we have the matching request
        if tool_call_id in self.pending_tool_calls:
            pending = self.pending_tool_calls.pop(tool_call_id)
            
            # Calculate importance (can be enhanced later)
            importance = self._calculate_tool_importance(tool_name, result)
            
            # Create atomic pair
            pair = ToolCallPair(
                request=pending['request'],
                result=result,
                timestamp=pending['timestamp'],
                importance_score=importance,
                tool_name=tool_name,
                tool_call_id=tool_call_id
            )
            
            self.tool_call_pairs.append(pair)
    
    def _calculate_tool_importance(self, tool_name: str, result: Any) -> float:
        """
        Calculate importance score for a tool call.
        
        Args:
            tool_name: Name of the tool
            result: Tool execution result
            
        Returns:
            Importance score between 0 and 1
        """
        # Base importance by tool type
        importance_map = {
            'web_search': 0.8,
            'code_execution': 0.9,
            'file_operations': 0.7,
            'memory_operations': 0.9,
            'calendar': 0.6,
            'email': 0.7,
        }
        
        # Start with base importance
        base_importance = 0.5
        for key, score in importance_map.items():
            if key in tool_name.lower():
                base_importance = score
                break
        
        # Adjust based on result success/failure
        if isinstance(result, dict):
            if result.get('status') == 'error':
                base_importance *= 0.5  # Lower importance for errors
            elif result.get('data'):
                base_importance *= 1.1  # Higher importance for data-rich results
        
        return min(1.0, base_importance)
    
    def get_context_with_tool_history(self) -> Tuple[List[Dict[str, Any]], List[ToolCallPair]]:
        """
        Get working context with relevant tool history.
        
        Returns:
            Tuple of (working_contents, included_tool_pairs)
        """
        # Inject tool history if not already done
        if self.tool_call_pairs and not self._tool_history_injected():
            self._inject_tool_history_into_context()
        
        relevant_pairs = self._select_relevant_tool_pairs()
        return self.working_contents, relevant_pairs
    
    def _tool_history_injected(self) -> bool:
        """
        Check if tool history has been injected into context.
        
        Returns:
            True if tool history is already in context
        """
        # This is a simplified check - providers can override with specific logic
        return any(
            'tool' in str(content).lower() 
            for content in self.working_contents[-5:] if content
        )
    
    def truncate_context_with_pairing(self, max_tokens: int) -> None:
        """
        Truncate context while preserving tool call-result pairs.
        
        Args:
            max_tokens: Maximum token limit for context
        """
        # This ensures we never split tool pairs during truncation
        # Implementation would be provider-specific for token counting
        pass
    
    def get_serializable_tool_history(self) -> List[Dict[str, Any]]:
        """
        Get tool history in serializable format for storage.
        
        Returns:
            List of tool pair dictionaries
        """
        return [
            {
                'request': pair.request,
                'result': pair.result,
                'timestamp': pair.timestamp.isoformat(),
                'importance_score': pair.importance_score,
                'tool_name': pair.tool_name,
                'tool_call_id': pair.tool_call_id
            }
            for pair in self.tool_call_pairs
        ]
    
    @classmethod
    def deserialize_tool_history(cls, data: List[Dict[str, Any]]) -> List[ToolCallPair]:
        """
        Deserialize tool history from storage format.
        
        Args:
            data: Serialized tool history
            
        Returns:
            List of ToolCallPair objects
        """
        return [
            ToolCallPair(
                request=item['request'],
                result=item['result'],
                timestamp=datetime.fromisoformat(item['timestamp']),
                importance_score=item['importance_score'],
                tool_name=item['tool_name'],
                tool_call_id=item['tool_call_id']
            )
            for item in data
        ]