"""
Enhanced Context Manager with Runtime Tool History Preservation

This module provides an enhanced context manager that preserves tool calling
history during active sessions, solving the "tool amnesia" problem in
multi-turn conversations.

Key Features:
- Tool call-result pairing with atomicity guarantees  
- Runtime-scoped tool context preservation
- Session-based tool history management
- Provider-specific message injection
"""

from abc import abstractmethod
from typing import List, Dict, Any, Optional, NamedTuple
from datetime import datetime
from dataclasses import dataclass, field
from backend.infrastructure.llm.base.context_manager import BaseContextManager


class ToolCallPair(NamedTuple):
    """
    Atomic tool call-result pair for context preservation.
    
    Attributes:
        request: Tool call request from LLM response
        result: Tool execution result
        timestamp: When the tool was called
        tool_name: Name of the tool for quick reference
        tool_call_id: Unique identifier for the tool call
    """
    request: Dict[str, Any]
    result: Dict[str, Any]
    timestamp: datetime
    tool_name: str
    tool_call_id: str


@dataclass
class RuntimeToolContext:
    """
    Runtime-scoped tool context for a session.
    
    Attributes:
        tool_pairs: Matched pairs of calls and results
        session_id: Current session identifier
        provider: Provider used for this runtime
        created_at: When this runtime context was created
    """
    tool_pairs: List[ToolCallPair] = field(default_factory=list)
    session_id: Optional[str] = None
    provider: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    def add_tool_pair(self, pair: ToolCallPair) -> None:
        """Add a tool call-result pair to runtime context."""
        self.tool_pairs.append(pair)
    
    def get_recent_pairs(self, limit: int = 10) -> List[ToolCallPair]:
        """Get most recent tool pairs."""
        return self.tool_pairs[-limit:] if self.tool_pairs else []
    
    def clear(self) -> None:
        """Clear runtime context (e.g., on session end)."""
        self.tool_pairs.clear()


class EnhancedContextManager(BaseContextManager):
    """
    Enhanced context manager with runtime tool history preservation.
    
    This manager extends the base context manager to maintain tool calling
    history during active sessions, ensuring the LLM has access to its
    previous tool usage for better decision making.
    
    Design Principles:
    1. Runtime-scoped tool context lives in memory during session
    2. Atomic tool call-result pairs to prevent orphaned results
    3. Provider-specific message injection for compatibility
    """
    
    def __init__(self, provider_name: str, session_id: Optional[str] = None):
        """
        Initialize enhanced context manager.
        
        Args:
            provider_name: LLM provider name
            session_id: Optional session ID for runtime context
        """
        super().__init__(provider_name)
        self.session_id = session_id
        
        # Runtime tool context for this session
        self.runtime_context = RuntimeToolContext(
            session_id=session_id,
            provider=provider_name
        ) if session_id else None
        
        # Temporary storage for unpaired tool calls
        self.pending_tool_calls: Dict[str, Dict[str, Any]] = {}
    
    def initialize_from_messages(self, messages: List[Any]) -> None:
        """
        Initialize from messages and inject runtime tool context.
        
        Args:
            messages: Historical messages from storage
        """
        # First, do normal initialization
        super().initialize_from_messages(messages)
        
        # Then inject runtime tool context if available
        if self.runtime_context and self.runtime_context.tool_pairs:
            self._inject_runtime_tools()
    
    def _inject_runtime_tools(self) -> None:
        """
        Inject runtime tool context into working contents.
        
        This method adds tool history from the current runtime
        into the working context for API calls.
        """
        if not self.runtime_context:
            return
        
        # Get recent tool pairs from runtime
        recent_pairs = self.runtime_context.get_recent_pairs(limit=10)
        
        # Each provider will override this to format appropriately
        for pair in recent_pairs:
            self._inject_tool_pair(pair)
    
    @abstractmethod
    def _inject_tool_pair(self, pair: ToolCallPair) -> None:
        """
        Inject a single tool pair into working context.
        
        Providers must override this to format according to their API.
        
        Args:
            pair: Tool call-result pair to inject
        """
        pass
    
    def add_response(self, response: Any) -> None:
        """
        Add response and track any tool calls for pairing.
        
        Args:
            response: Provider-specific response object
        """
        # Base implementation - providers must override
        pass
    
    def track_tool_call(self, tool_call: Dict[str, Any]) -> None:
        """
        Track a tool call from LLM response for later pairing.
        
        Args:
            tool_call: Tool call information from LLM response
        """
        tool_id = tool_call.get('id', tool_call.get('name', ''))
        self.pending_tool_calls[tool_id] = {
            'request': tool_call,
            'timestamp': datetime.now()
        }
    
    def add_tool_result(self, tool_call_id: str, tool_name: str, result: Any) -> None:
        """
        Add tool result and create atomic pair with its request.
        
        Args:
            tool_call_id: Tool call identifier
            tool_name: Name of the tool
            result: Tool execution result
        """
        # Create pair if we have the matching request
        if tool_call_id in self.pending_tool_calls:
            pending = self.pending_tool_calls.pop(tool_call_id)
            
            # Create atomic pair
            pair = ToolCallPair(
                request=pending['request'],
                result=result,
                timestamp=pending['timestamp'],
                tool_name=tool_name,
                tool_call_id=tool_call_id
            )
            
            # Add to runtime context
            if self.runtime_context:
                self.runtime_context.add_tool_pair(pair)
    
    def get_runtime_summary(self) -> Dict[str, Any]:
        """
        Get summary of runtime tool usage.
        
        Returns:
            Summary dictionary with tool usage statistics
        """
        if not self.runtime_context:
            return {'active': False}
        
        return {
            'active': True,
            'session_id': self.runtime_context.session_id,
            'provider': self.runtime_context.provider,
            'total_pairs': len(self.runtime_context.tool_pairs),
            'created_at': self.runtime_context.created_at.isoformat()
        }
    
    def clear_runtime_context(self) -> None:
        """Clear runtime context for session cleanup."""
        if self.runtime_context:
            self.runtime_context.clear()
            self.pending_tool_calls.clear()