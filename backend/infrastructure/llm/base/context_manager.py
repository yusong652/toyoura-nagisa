"""
BaseContextManager - Enhanced context manager with runtime tool history preservation.

This module provides the foundational context manager that all provider-specific
context managers inherit from, featuring incremental message management and
tool context preservation during active sessions.

Key Features:
- Incremental message management for efficiency
- Sequential tool call and result management
- Smart truncation preserving tool integrity
- Session-based context persistence
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from backend.domain.models.messages import BaseMessage
from backend.infrastructure.llm.shared.utils.provider_registry import get_message_formatter_class


class BaseContextManager(ABC):
    """
    Enhanced context manager with incremental message management and tool preservation.
    
    This manager implements an efficient incremental approach where:
    1. Historical messages are loaded once at session initialization
    2. New messages are added incrementally without re-processing history
    3. Tool calls and results are managed sequentially
    4. Context is maintained persistently throughout the session
    
    Design Principles:
    1. Incremental updates for efficiency
    2. Sequential tool management (calls followed by results)
    3. Smart truncation preserving message integrity
    4. Session-persistent context management
    """
    
    def __init__(self, provider_name: str, session_id: Optional[str] = None):
        """
        Initialize context manager.
        
        Args:
            provider_name: LLM provider name (e.g., 'gemini', 'anthropic', 'openai')
            session_id: Optional session ID for runtime context
        """
        self._provider_name = provider_name
        self.session_id = session_id
        
        # Working contents will be populated by initialize methods
        self.working_contents: List[Dict[str, Any]] = []
        
        # Track if we've initialized from history
        self._initialized_from_history = False
        
        # Message management
        self._message_history: List[BaseMessage] = []

        # Request configuration storage
        self.agent_profile = "general"
        self.enable_memory = True

        # Tool call tracking
        self._has_tool_calls = False
    
    def initialize_from_messages(self, messages: List[BaseMessage]) -> None:
        """
        Initialize context manager from input message list.
        
        Uses provider-specific message formatter to convert messages
        to the appropriate format for the LLM API.
        
        Args:
            messages: Input message history list
            
        Raises:
            ValueError: If provider name is not set
        """
        if not self._provider_name:
            raise ValueError("Provider name not set in context manager")
            
        # Get the appropriate message formatter
        formatter_class = get_message_formatter_class(self._provider_name)
        
        # Call the unified format_messages method
        self.working_contents = formatter_class.format_messages(messages)
    
    def initialize_session_from_history(self, historical_messages: List[BaseMessage]) -> None:
        """
        Initialize context manager with historical messages at session start.
        
        This should be called once when a session begins or switches,
        loading all historical messages and setting up the base context.
        
        Args:
            historical_messages: All historical messages from storage
        """
        # Store message history
        self._message_history = historical_messages.copy()
        
        # Initialize working contents from history
        self.initialize_from_messages(historical_messages)
        
        # Mark as initialized
        self._initialized_from_history = True
    
    def add_user_message(self, user_message: BaseMessage) -> None:
        """
        Add a new user message to the context incrementally.
        
        This method is called for each new user input, adding it to the
        existing context without re-processing historical messages.
        
        Args:
            user_message: New user message to add
        """
        if not self._initialized_from_history:
            # Fallback to old behavior if not properly initialized
            self.initialize_from_messages([user_message])
            return
        
        # Add to message history
        self._message_history.append(user_message)
        
        # Format and add to working contents
        formatter_class = get_message_formatter_class(self._provider_name)
        formatted_message = formatter_class.format_single_message(user_message)
        
        self.working_contents.append(formatted_message)

    def add_user_message_from_data(self, parsed_data: dict) -> None:
        """
        Create user message from parsed data and update configuration.

        Args:
            parsed_data: Parsed message data including agent_profile, enable_memory configuration
        """
        # Update configuration
        self.agent_profile = parsed_data.get('agent_profile', 'general')
        self.enable_memory = parsed_data.get('enable_memory', True)

        # Create user message
        from backend.domain.models.messages import UserMessage
        from datetime import datetime

        timestamp = parsed_data.get('timestamp')
        user_message = UserMessage(
            content=parsed_data['content'],
            timestamp=datetime.fromtimestamp(timestamp / 1000) if timestamp else datetime.now(),
            id=parsed_data.get('id')
        )

        # Add to context
        self.add_user_message(user_message)

    @abstractmethod
    def add_response(self, response: Any) -> None:
        """
        Add LLM response to context.
        
        Provider-specific implementations must handle both:
        1. Raw provider API responses (during tool calling)
        2. Final BaseMessage responses (for storage)
        
        Args:
            response: Provider-specific response object or BaseMessage
        """
        pass
    
    @abstractmethod
    def add_tool_result(self, tool_call_id: str, tool_name: str, result: Any) -> None:
        """
        Add tool execution result to context.
        
        Since we manage messages sequentially, tool results are simply
        appended after their corresponding tool calls.
        
        Args:
            tool_call_id: Unique identifier for tool call
            tool_name: Tool name
            result: Tool execution result
        """
        pass
    
    def get_working_contents(self) -> List[Dict[str, Any]]:
        """
        Get working contents with smart truncation preserving tool integrity.

        Automatically retrieves recent_messages_length from configuration.
        Ensures that exactly recent_messages_length non-tool messages are retained while
        preserving the integrity of tool calls and their results. Guarantees
        clean start boundary by ensuring the result starts with a non-tool message.

        This method ensures that:
        1. Tool calls and results are kept together
        2. Most recent messages are prioritized
        3. Clean message boundaries (no orphaned tool results)

        Returns:
            List[Dict[str, Any]]: Truncated messages with clean start boundary
        """
        # Get recent_messages_length from configuration
        from backend.config import get_llm_settings
        recent_messages_length = get_llm_settings().recent_messages_length

        messages = self.working_contents

        # Debug: Print message details
        print(f"[DEBUG] Total messages: {len(messages)}")
        print(f"[DEBUG] recent_messages_length: {recent_messages_length}")
        
        for i, msg in enumerate(messages):
            is_tool_call = self._is_tool_call(msg)
            is_tool_result = self._is_tool_result(msg)
            
            if isinstance(msg, dict):
                role = msg.get('role', 'unknown')
                parts_info = "dict format"
                # Debug parts structure for dict messages
                if 'parts' in msg:
                    parts = msg['parts']
                    if isinstance(parts, list) and len(parts) > 0:
                        first_part = parts[0]
                        if isinstance(first_part, dict):
                            part_keys = list(first_part.keys())
                            print(f"[DEBUG]   First part keys: {part_keys}")
                        else:
                            print(f"[DEBUG]   First part type: {type(first_part)}")
            else:
                role = getattr(msg, 'role', 'unknown')
                parts_info = "SDK object"
            
            print(f"[DEBUG] Message {i}: role={role}, is_tool_call={is_tool_call}, is_tool_result={is_tool_result}, format={parts_info}")
        
        # Count non-tool messages
        non_tool_count = sum(
            1 for msg in messages 
            if not self._is_tool_call(msg) and not self._is_tool_result(msg)
        )
        
        print(f"[DEBUG] Non-tool message count: {non_tool_count}")
        
        # If we already have fewer non-tool messages than recent_messages_length, return all
        if non_tool_count <= recent_messages_length:
            print(f"[DEBUG] Returning all messages (non_tool_count <= recent_messages_length)")
            return messages
        
        # Work backwards to collect the most recent non-tool messages
        # Tool messages are included but don't count toward the limit
        result = []
        non_tool_collected = 0
        i = len(messages) - 1
        
        while i >= 0 and non_tool_collected < recent_messages_length:
            msg = messages[i]
            
            if not self._is_tool_call(msg) and not self._is_tool_result(msg):
                # Non-tool message: include and count
                result.insert(0, msg)
                non_tool_collected += 1
            else:
                # Tool message (call or result): include but don't count
                result.insert(0, msg)
            
            i -= 1
        
        return result
    
    @abstractmethod
    def _is_tool_call(self, msg: Dict[str, Any]) -> bool:
        """
        Check if message contains tool calls.
        
        Provider-specific implementations must implement this method
        according to their message format.
        
        Args:
            msg: Message to check
            
        Returns:
            bool: True if message contains tool calls
        """
        pass
    
    @abstractmethod
    def _is_tool_result(self, msg: Dict[str, Any]) -> bool:
        """
        Check if message is a tool result.
        
        Provider-specific implementations must implement this method
        according to their message format.
        
        Args:
            msg: Message to check
            
        Returns:
            bool: True if message is a tool result
        """
        pass
    
    def get_runtime_summary(self) -> Dict[str, Any]:
        """
        Get summary of runtime context.
        
        Returns:
            Summary dictionary with context statistics
        """
        return {
            'active': True,
            'session_id': self.session_id,
            'provider': self._provider_name,
            'message_count': len(self._message_history),
            'working_contents_count': len(self.working_contents),
            'initialized': self._initialized_from_history
        }
    
    def clear_runtime_context(self) -> None:
        """Clear runtime context for session cleanup."""
        self._message_history.clear()
        self.working_contents.clear()
        self._initialized_from_history = False

