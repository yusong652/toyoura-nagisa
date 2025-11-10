"""
Gemini Context Manager - Manages original context during tool calls

This module is responsible for maintaining the original Gemini API response format
during tool calls, ensuring thinking chain and validation field integrity while
handling storage format messages.

Core design principles:
1. Working context: Maintain original Gemini API format with complete thinking chain and validation fields
2. Focus on context state management during tool calls
"""

from typing import Any, Optional, Dict
from backend.infrastructure.llm.base.context_manager import BaseContextManager
from backend.domain.models.messages import BaseMessage
from .message_formatter import GeminiMessageFormatter


class GeminiContextManager(BaseContextManager):
    """
    Manages context during Gemini API tool calls
    
    Core functionality:
    - Maintain working context in original format, ensuring thinking chain integrity
    - Provide context state management during tool calls
    - Support context continuity across multiple tool calls
    
    Usage scenarios:
    1. Initialization: Create initial context from message history
    2. Tool calls: Add original responses and tool results
    3. Finalization: Create standardized messages for storage
    """
    
    def __init__(self, session_id: str, provider_name: str = "gemini"):
        """Initialize context manager"""
        super().__init__(provider_name=provider_name, session_id=session_id)
        # working_contents already initialized in base class

    def add_response(self, response) -> None:
        """
        Add Gemini API response to working context
        
        Handles two types of responses:
        1. Original Gemini API response object (during tool calls)
        2. BaseMessage response (final response storage)
        
        Args:
            response: Original Gemini API response object or BaseMessage
        """
        if isinstance(response, BaseMessage):
            # Handle final BaseMessage response
            # Format and add to working context
            from backend.infrastructure.llm.shared.utils.provider_registry import get_message_formatter_class
            formatter_class = get_message_formatter_class(self._provider_name)
            formatted_response = formatter_class.format_single_message(response)

            self.working_contents.append(formatted_response)
        else:
            # Handle original Gemini API response
            try:
                candidate = response.candidates[0]
            except (AttributeError, IndexError):
                raise ValueError("Invalid Gemini API response format")
            raw_content = candidate.content
            # Add to working context
            self.working_contents.append(raw_content)
    
    async def add_tool_result(self, tool_call_id: str, tool_name: str, result: Any, inject_reminders: bool = False) -> None:
        """
        Add tool execution result to context - unified implementation (async)

        Use message formatter to handle format, maintaining consistent architecture pattern with Anthropic

        Args:
            tool_call_id: Unique identifier for tool call (required by interface, not used by Gemini)
            tool_name: Tool name
            result: Tool execution result
            inject_reminders: Whether to inject system reminders into this result
        """
        # Inject system reminders to result content if needed (async)
        if inject_reminders:
            print(f"[DEBUG] GeminiContextManager.add_tool_result: inject_reminders=True for session {self.session_id}")
            reminders = await self._get_background_task_reminders()
            print(f"[DEBUG] GeminiContextManager.add_tool_result: Got {len(reminders)} reminders")

            if len(reminders) == 0:
                print(f"[DEBUG] No reminders found for session {self.session_id}")

            if reminders:
                reminder_text = "\n\n" + "\n\n".join([
                    f"<system-reminder>\n{reminder}\n</system-reminder>"
                    for reminder in reminders
                ])

                # Modify result llm_content to inject reminders
                if isinstance(result, dict) and 'llm_content' in result:
                    llm_content = result['llm_content']

                    # Tool results use parts format: {"parts": [{"type": "text", "text": "..."}]}
                    if isinstance(llm_content, dict) and 'parts' in llm_content:
                        parts = llm_content.get('parts', [])
                        if isinstance(parts, list):
                            # Find last text part and append reminder
                            for part in reversed(parts):
                                if isinstance(part, dict) and part.get('type') == 'text' and 'text' in part:
                                    part['text'] += reminder_text
                                    print(f"[DEBUG] Injected reminders to tool result parts")
                                    break

        # Use message formatter to handle tool result format
        working_content = GeminiMessageFormatter.format_tool_result_for_context(tool_name, result)
        # Add to working context
        self.working_contents.append(working_content)
    
    def _is_tool_call(self, msg: Dict[str, Any]) -> bool:
        """
        Check if message contains tool calls (Gemini format)
        
        Handles both dictionary format (from formatted messages) and
        Gemini SDK Content objects (from API responses).
        
        Args:
            msg: Message to check (dict or Content object)
            
        Returns:
            bool: True if message contains tool calls
        """
        # Handle dictionary format (from formatted messages)
        if isinstance(msg, dict):
            # Check if it's a model role message with parts
            if msg.get('role') != 'model' or 'parts' not in msg:
                return False
                
            # Check if parts contain function_call
            parts = msg.get('parts', [])
            if not isinstance(parts, list):
                return False
                
            for part in parts:
                # Part can be either a dict or a SDK Part object
                if isinstance(part, dict):
                    if 'function_call' in part:
                        return True
                elif hasattr(part, 'function_call') and part.function_call:
                    # Handle SDK Part objects in dict message format
                    return True
        
        # Handle Gemini SDK Content object (from API responses)
        else:
            # Check if it's a Content object with model role
            if not hasattr(msg, 'role') or msg.role != 'model':
                return False
                
            # Check if parts contain function_call
            if hasattr(msg, 'parts'):
                for part in msg.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        return True
                
        return False
    
    def _is_tool_result(self, msg: Dict[str, Any]) -> bool:
        """
        Check if message is a tool result (Gemini format)
        
        Handles both dictionary format (from formatted messages) and
        Gemini SDK Content objects (from API responses).
        
        Args:
            msg: Message to check (dict or Content object)
            
        Returns:
            bool: True if message is a tool result
        """
        # Handle dictionary format (from formatted messages)
        if isinstance(msg, dict):
            # Check if it's a user role message with parts
            if msg.get('role') != 'user' or 'parts' not in msg:
                return False
                
            # Check if parts contain function_response
            parts = msg.get('parts', [])
            if not isinstance(parts, list):
                return False
                
            for part in parts:
                # Part can be either a dict or a SDK Part object
                if isinstance(part, dict):
                    if 'function_response' in part:
                        return True
                elif hasattr(part, 'function_response') and part.function_response:
                    # Handle SDK Part objects in dict message format
                    return True
        
        # Handle Gemini SDK Content object (from API responses)
        else:
            # Check if it's a Content object with user role
            if not hasattr(msg, 'role') or msg.role != 'user':
                return False
                
            # Check if parts contain function_response
            if hasattr(msg, 'parts'):
                for part in msg.parts:
                    if hasattr(part, 'function_response') and part.function_response:
                        return True

        return False
