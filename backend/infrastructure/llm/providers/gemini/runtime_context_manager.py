"""
Gemini Runtime Context Manager - Runtime tool preservation for Gemini

Provider-specific implementation of runtime context management for Google Gemini.
Handles Gemini-specific formatting while maintaining runtime tool context.
"""

from typing import Dict, Any, Optional
from backend.infrastructure.llm.base.runtime_context_manager import EnhancedBaseContextManager
from backend.infrastructure.llm.providers.gemini.context_manager import GeminiContextManager
from backend.infrastructure.llm.providers.gemini.message_formatter import GeminiMessageFormatter


class GeminiRuntimeContextManager(GeminiContextManager, EnhancedBaseContextManager):
    """
    Gemini-specific runtime context manager.
    
    Combines Gemini's native context management with runtime tool preservation.
    This allows tool context to persist during active sessions while keeping
    storage format unchanged.
    """
    
    def __init__(self, session_id: Optional[str] = None):
        """
        Initialize Gemini runtime context manager.
        
        Args:
            session_id: Optional session ID for runtime tracking
        """
        # Initialize both parent classes
        GeminiContextManager.__init__(self)
        
        # Set up runtime context
        self.session_id = session_id
        if session_id:
            from backend.infrastructure.llm.base.runtime_context_manager import RuntimeContextManager
            self.runtime_context = RuntimeContextManager.get_or_create_context(
                session_id, "gemini"
            )
        else:
            self.runtime_context = None
    
    def add_response(self, response) -> None:
        """
        Add response and track tool calls in runtime.
        
        Args:
            response: Gemini API response object
        """
        # First, use parent's add_response
        super().add_response(response)
        
        # Then track tool calls in runtime if present
        if self.runtime_context:
            try:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    for part in candidate.content.parts:
                        if hasattr(part, 'function_call'):
                            # Track Gemini function call
                            tool_call = {
                                'id': getattr(part.function_call, 'id', None),
                                'name': part.function_call.name,
                                'args': dict(part.function_call.args) if hasattr(part.function_call, 'args') else {}
                            }
                            self.runtime_context.add_tool_call(tool_call)
            except (AttributeError, IndexError):
                pass  # No tool calls in this response
    
    def add_tool_result(self, tool_call_id: str, tool_name: str, result: Any) -> None:
        """
        Add tool result and track in runtime.
        
        Args:
            tool_call_id: Tool call identifier (Gemini may not use this)
            tool_name: Name of the tool
            result: Tool execution result
        """
        # First, use parent's add_tool_result
        super().add_tool_result(tool_call_id, tool_name, result)
        
        # Then track in runtime
        if self.runtime_context:
            self.runtime_context.add_tool_result(tool_call_id, {
                'tool_name': tool_name,
                'result': result
            })
    
    def _inject_tool_pair(self, call: Dict[str, Any], result: Dict[str, Any]) -> None:
        """
        Inject tool pair in Gemini format.
        
        Args:
            call: Tool call from runtime context
            result: Tool result from runtime context
        """
        # Format as Gemini function call and response
        # This ensures tool history is available in the conversation
        
        # Add function call as model message part
        function_call_content = {
            "role": "model",
            "parts": [{
                "functionCall": {
                    "name": call.get('name', ''),
                    "args": call.get('args', {})
                }
            }]
        }
        self.working_contents.append(function_call_content)
        
        # Add function response
        tool_result = result.get('result', {})
        function_response_content = GeminiMessageFormatter.format_tool_result_for_context(
            call.get('name', ''),
            tool_result
        )
        self.working_contents.append(function_response_content)
    
    def initialize_from_messages(self, messages) -> None:
        """
        Initialize from messages and inject runtime tool context.
        
        Args:
            messages: Historical messages
        """
        # Do base initialization
        super().initialize_from_messages(messages)
        
        # Inject runtime tool context if available
        if self.runtime_context and self.runtime_context.tool_pairs:
            # Get recent pairs and inject them
            recent_pairs = self.runtime_context.get_recent_pairs(limit=5)
            for call, result in recent_pairs:
                self._inject_tool_pair(call, result)
    
    def get_context_summary(self) -> Dict[str, Any]:
        """
        Get summary of current context state.
        
        Returns:
            Context summary including runtime tool info
        """
        summary = {
            'provider': 'gemini',
            'working_contents_count': len(self.working_contents),
            'session_id': self.session_id
        }
        
        if self.runtime_context:
            summary['runtime_tools'] = {
                'total_calls': len(self.runtime_context.tool_calls),
                'paired_calls': len(self.runtime_context.tool_pairs),
                'recent_tools': [
                    call.get('name', 'unknown')
                    for call, _ in self.runtime_context.get_recent_pairs(3)
                ]
            }
        
        return summary