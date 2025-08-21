"""
Runtime Context Manager - Session-scoped tool context preservation

This module implements a runtime-scoped context manager that maintains tool calling
history during active sessions while keeping persistent storage provider-agnostic.

Architecture:
- Runtime scope: Tool context lives in memory during session runtime
- Persistent storage: Only final responses stored (provider-agnostic)
- Provider flexibility: Can switch providers between sessions
- Tool continuity: Maintains tool context within single runtime

Key Benefits:
1. No changes to existing storage format
2. Tool context preserved during active conversations
3. Clean separation between runtime and persistent state
4. Provider switching remains possible between sessions
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from backend.infrastructure.llm.base.context_manager import BaseContextManager


@dataclass
class RuntimeToolContext:
    """
    Runtime-scoped tool context for a session.
    
    Attributes:
        tool_calls: List of tool call requests from LLM
        tool_results: List of tool execution results
        tool_pairs: Matched pairs of calls and results
        session_id: Current session identifier
        provider: Provider used for this runtime
        created_at: When this runtime context was created
    """
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    tool_pairs: List[Tuple[Dict, Dict]] = field(default_factory=list)
    session_id: Optional[str] = None
    provider: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    def add_tool_call(self, call: Dict[str, Any]) -> None:
        """Add a tool call to runtime context."""
        self.tool_calls.append(call)
    
    def add_tool_result(self, call_id: str, result: Dict[str, Any]) -> None:
        """Add tool result and create pair if matching call exists."""
        self.tool_results.append(result)
        
        # Try to match with pending call
        for call in self.tool_calls:
            if call.get('id') == call_id or call.get('name') == result.get('tool_name'):
                self.tool_pairs.append((call, result))
                break
    
    def get_recent_pairs(self, limit: int = 5) -> List[Tuple[Dict, Dict]]:
        """Get most recent tool pairs."""
        return self.tool_pairs[-limit:] if self.tool_pairs else []
    
    def clear(self) -> None:
        """Clear runtime context (e.g., on session end)."""
        self.tool_calls.clear()
        self.tool_results.clear()
        self.tool_pairs.clear()


class RuntimeContextManager:
    """
    Manages runtime tool context across all providers.
    
    This manager acts as a runtime cache for tool context, sitting between
    the provider-specific context managers and persistent storage.
    
    Design Principles:
    1. Runtime-scoped: Lives only during active session
    2. Provider-agnostic storage: Tool pairs stored in normalized format
    3. Provider-specific injection: Each provider formats tool history as needed
    4. Memory-efficient: Automatic cleanup on session end
    """
    
    # Class-level storage for active runtime contexts
    _active_contexts: Dict[str, RuntimeToolContext] = {}
    
    @classmethod
    def get_or_create_context(cls, session_id: str, provider: str) -> RuntimeToolContext:
        """
        Get existing or create new runtime context for session.
        
        Args:
            session_id: Session identifier
            provider: LLM provider name
            
        Returns:
            RuntimeToolContext for the session
        """
        if session_id not in cls._active_contexts:
            cls._active_contexts[session_id] = RuntimeToolContext(
                session_id=session_id,
                provider=provider
            )
        return cls._active_contexts[session_id]
    
    @classmethod
    def clear_session_context(cls, session_id: str) -> None:
        """
        Clear runtime context for a session.
        
        Args:
            session_id: Session to clear
        """
        if session_id in cls._active_contexts:
            cls._active_contexts[session_id].clear()
            del cls._active_contexts[session_id]
    
    @classmethod
    def get_active_sessions(cls) -> List[str]:
        """Get list of sessions with active runtime contexts."""
        return list(cls._active_contexts.keys())


class EnhancedBaseContextManager(BaseContextManager):
    """
    Enhanced base context manager with runtime tool preservation.
    
    Extends the base context manager to work with RuntimeContextManager
    for maintaining tool context during active sessions.
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
        self.runtime_context: Optional[RuntimeToolContext] = None
        
        # Get or create runtime context if session provided
        if session_id:
            self.runtime_context = RuntimeContextManager.get_or_create_context(
                session_id, provider_name
            )
    
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
        for call, result in recent_pairs:
            self._inject_tool_pair(call, result)
    
    def _inject_tool_pair(self, call: Dict[str, Any], result: Dict[str, Any]) -> None:
        """
        Inject a single tool pair into working context.
        
        Providers should override this to format according to their API.
        
        Args:
            call: Tool call request
            result: Tool execution result
        """
        # Default implementation - providers should override
        pass
    
    def track_tool_call(self, tool_call: Dict[str, Any]) -> None:
        """
        Track a tool call in runtime context.
        
        Args:
            tool_call: Tool call information from LLM response
        """
        if self.runtime_context:
            self.runtime_context.add_tool_call(tool_call)
    
    def track_tool_result(self, call_id: str, result: Dict[str, Any]) -> None:
        """
        Track a tool result in runtime context.
        
        Args:
            call_id: Tool call identifier
            result: Tool execution result
        """
        if self.runtime_context:
            self.runtime_context.add_tool_result(call_id, result)
    
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
            'total_calls': len(self.runtime_context.tool_calls),
            'total_results': len(self.runtime_context.tool_results),
            'paired_calls': len(self.runtime_context.tool_pairs),
            'created_at': self.runtime_context.created_at.isoformat()
        }


def integrate_with_existing_flow(context_manager: BaseContextManager, session_id: str) -> EnhancedBaseContextManager:
    """
    Helper to upgrade existing context manager with runtime capabilities.
    
    This allows gradual migration without breaking existing code.
    
    Args:
        context_manager: Existing context manager instance
        session_id: Session ID for runtime tracking
        
    Returns:
        Enhanced context manager with runtime capabilities
    """
    # Create enhanced version
    enhanced = EnhancedBaseContextManager(
        provider_name=context_manager._provider_name,
        session_id=session_id
    )
    
    # Copy existing state
    enhanced.working_contents = context_manager.working_contents.copy()
    enhanced._messages_history = context_manager._messages_history.copy()
    
    return enhanced