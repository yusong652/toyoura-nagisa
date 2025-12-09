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
    
    def __init__(self, provider_name: str, session_id: str):
        """
        Initialize context manager and load historical messages.

        Automatically loads conversation history from storage and initializes
        the context manager with formatted messages, making it ready to use
        immediately after construction.

        Args:
            provider_name: LLM provider name (e.g., 'gemini', 'anthropic', 'openai')
            session_id: Session ID for loading history and runtime state
        """
        self._provider_name = provider_name
        self.session_id = session_id

        # Request configuration storage
        self.agent_profile = "general"
        self.enable_memory = True

        # Tool call tracking
        self._has_tool_calls = False

        # Cached system reminders (captured before tool execution)
        self._cached_system_reminders: List[str] = []

        # Streaming message tracking (set during streaming responses)
        self.streaming_message_id: Optional[str] = None  # Message ID for streaming response updates

        # Status monitor for background tasks and system state
        from backend.infrastructure.monitoring import get_status_monitor
        self._status_monitor = get_status_monitor(session_id)

        # Load historical messages and initialize working contents
        # Use load_history (not load_all_message_history) to exclude image/video messages
        from backend.infrastructure.storage.session_manager import load_history
        from backend.domain.models.message_factory import message_factory

        history_dicts = load_history(session_id)
        historical_messages = [message_factory(msg) for msg in history_dicts]
        self.working_contents: List[Dict[str, Any]] = []

        if historical_messages:
            self.initialize_from_messages(historical_messages)

        # Handle interrupted response if needed (StatusMonitor loaded the flag)
        # This merges consecutive user messages in history when previous response was interrupted
        if self._status_monitor.was_last_response_interrupted():
            self._handle_interrupted_response_on_init()
    
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

    def _handle_interrupted_response_on_init(self) -> None:
        """
        Handle interrupted response by merging consecutive user messages.

        When a response is interrupted and user sends another message, this method
        merges the two consecutive user messages with an interrupt notification.
        Updates both in-memory context (working_contents) and persistent storage.

        This is called during __init__ when loading from history with interrupt flag set.
        """
        # Check if we have at least two messages to potentially merge
        if len(self.working_contents) < 2:
            return

        # Check if last two messages are both user messages
        last_msg = self.working_contents[-1]
        second_last_msg = self.working_contents[-2]

        # Extract roles (handle both dict and object types)
        last_role = last_msg.get('role') if isinstance(last_msg, dict) else getattr(last_msg, 'role', None)
        second_last_role = second_last_msg.get('role') if isinstance(second_last_msg, dict) else getattr(second_last_msg, 'role', None)

        if last_role != 'user' or second_last_role != 'user':
            return

        # Extract content from last message (the "new" message)
        new_content = ""
        if isinstance(last_msg, dict):
            content = last_msg.get('content', '')
            if isinstance(content, str):
                new_content = content
            elif isinstance(content, list):
                new_content = "".join([
                    item.get('text', '')
                    for item in content
                    if isinstance(item, dict) and 'text' in item
                ])
        elif hasattr(last_msg, 'content'):
            new_content = str(last_msg.content)

        # Build merge text with system-reminder
        reminder = "Previous response interrupted by user."
        merge_text = f"\n\n<system-reminder>\n{reminder}\nUser sent another message:\n</system-reminder>\n\n{new_content}"

        # Merge in memory (working_contents)
        if isinstance(second_last_msg, dict):
            if isinstance(second_last_msg.get('content'), str):
                second_last_msg['content'] += merge_text
            elif isinstance(second_last_msg.get('content'), list):
                for block in reversed(second_last_msg['content']):
                    if isinstance(block, dict) and block.get('type') == 'text':
                        block['text'] += merge_text
                        break
        elif hasattr(second_last_msg, 'parts'):
            # Gemini Content object
            for part in reversed(second_last_msg.parts):
                if hasattr(part, 'text'):
                    part.text += merge_text
                    break

        # Remove last message from working_contents
        self.working_contents.pop()

        # Merge in database
        from backend.infrastructure.storage.session_manager import (
            load_all_message_history,
            save_history
        )
        from backend.domain.models.message_factory import message_factory

        history = load_all_message_history(self.session_id)
        history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in history]

        # Find last two user messages
        user_messages_indices = [
            i for i, msg in enumerate(history_msgs)
            if getattr(msg, 'role', None) == 'user'
        ]

        if len(user_messages_indices) >= 2:
            first_idx = user_messages_indices[-2]
            second_idx = user_messages_indices[-1]
            first_msg = history_msgs[first_idx]

            # Merge content in first message
            if isinstance(first_msg.content, str):
                first_msg.content += merge_text
            elif isinstance(first_msg.content, list):
                for block in reversed(first_msg.content):
                    if isinstance(block, dict) and block.get('type') == 'text':
                        block['text'] += merge_text
                        break

            # Delete second message
            del history_msgs[second_idx]
            save_history(self.session_id, history_msgs)

        # Clear interrupt flag via StatusMonitor
        self._status_monitor.clear_interrupt_flag()


    async def add_user_message(self, user_message: BaseMessage) -> None:
        """
        Add a new user message to the context incrementally (async).

        This method is called for each new user input, adding it to the
        existing context without re-processing historical messages.

        Supports async reminder injection for background tasks, interrupt status,
        and queue messages (during tool recursion).

        Args:
            user_message: New user message to add
        """
        # Track conversation turn for periodic todo reminders
        # Must happen BEFORE get_all_reminders() to ensure correct count
        self._status_monitor.todo_monitor.track_conversation_turn()

        # Check if previous response was interrupted (determines merge behavior)
        needs_merge = False
        if self._status_monitor.was_last_response_interrupted():
            # Check if we need to merge with previous user message
            if self.working_contents:
                last_msg = self.working_contents[-1]
                # Check role - handle both dict and object types
                last_role = None
                if isinstance(last_msg, dict):
                    last_role = last_msg.get('role')
                elif hasattr(last_msg, 'role'):
                    last_role = last_msg.role

                if last_role == 'user':
                    needs_merge = True

        # Get all system reminders (interrupt, bash processes, PFC tasks, etc.)
        # StatusMonitor automatically includes interrupt reminder and clears the flag
        # Note: check_queue=False (default) because user messages have already been
        # processed from the queue at this point. Queue messages are only checked
        # during tool result injection (when user sends new messages while tools are executing).
        reminders = await self._status_monitor.get_all_reminders(
            agent_profile=self.agent_profile
        )

        if needs_merge:
            # Merge with previous user message instead of creating new one
            # Extract new message content
            new_content = ""
            if isinstance(user_message.content, str):
                new_content = user_message.content
            elif isinstance(user_message.content, list):
                # Extract text from list
                text_parts = []
                for item in user_message.content:
                    if isinstance(item, dict) and 'text' in item:
                        text_parts.append(item['text'])
                new_content = "".join(text_parts)

            # Build merged content with LLM-friendly format:
            # 1. System reminders (already wrapped in system-reminder tags by StatusMonitor)
            # 2. Natural transition: "User sent another message:"
            # 3. New message content
            if reminders:
                reminder_text = "\n\n".join(reminders)  # Complete blocks from StatusMonitor
                transition = "\n\nUser sent another message:"
                merge_text = f"\n\n{reminder_text}{transition}\n\n{new_content}"
            else:
                merge_text = f"\n\nUser sent another message:\n\n{new_content}"

            # Merge into last message
            last_msg = self.working_contents[-1]
            if isinstance(last_msg, dict):
                # Dict format (Kimi/OpenAI)
                if isinstance(last_msg.get('content'), str):
                    last_msg['content'] += merge_text
                elif isinstance(last_msg.get('content'), list):
                    # Find last text block
                    for block in reversed(last_msg['content']):
                        if isinstance(block, dict) and block.get('type') == 'text':
                            block['text'] += merge_text
                            break
            elif hasattr(last_msg, 'parts'):
                # Gemini Content object with parts
                # Find last text part
                for part in reversed(last_msg.parts):
                    if hasattr(part, 'text'):
                        part.text += merge_text
                        break

            # Update database: merge messages persistently
            # 1. Load full history from database
            from backend.infrastructure.storage.session_manager import load_all_message_history, save_history
            from backend.domain.models.message_factory import message_factory

            history = load_all_message_history(self.session_id)
            history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in history]

            # 2. Find the last two user messages
            user_messages_indices = []
            for i, msg in enumerate(history_msgs):
                if getattr(msg, 'role', None) == 'user':
                    user_messages_indices.append(i)

            if len(user_messages_indices) >= 2:
                # Get the last two user message indices
                first_idx = user_messages_indices[-2]
                second_idx = user_messages_indices[-1]

                first_msg = history_msgs[first_idx]

                # 3. Merge content: update first message with merged content
                if isinstance(first_msg.content, str):
                    first_msg.content += merge_text
                elif isinstance(first_msg.content, list):
                    # Find last text block in first message
                    for block in reversed(first_msg.content):
                        if isinstance(block, dict) and block.get('type') == 'text':
                            block['text'] += merge_text
                            break

                # 4. Delete second message from history
                del history_msgs[second_idx]

                # 5. Save updated history back to database
                save_history(self.session_id, history_msgs)

        else:
            # Normal flow: add reminders and create new message
            if reminders:
                # StatusMonitor now returns complete system-reminder blocks
                # Just join them with newlines
                reminder_text = "\n\n" + "\n\n".join(reminders)

                # Modify user_message.content to inject reminders
                if isinstance(user_message.content, str):
                    user_message.content += reminder_text
                elif isinstance(user_message.content, list):
                    # Find last text item and append
                    for item in reversed(user_message.content):
                        if isinstance(item, dict) and 'text' in item:
                            item['text'] += reminder_text
                            break

            # Format and add to working contents
            formatter_class = get_message_formatter_class(self._provider_name)
            formatted_message = formatter_class.format_single_message(user_message)
            self.working_contents.append(formatted_message)

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

    async def _inject_reminders_to_result(self, result: Any) -> None:
        """
        Inject system reminders into tool result content.

        Delegates to ReminderInjector for unified reminder collection and injection.
        Should be called when inject_reminders=True in add_tool_result.

        Args:
            result: Tool result dict containing llm_content with parts format
        """
        from backend.application.services.reminder import ReminderInjector

        injector = ReminderInjector(self.session_id, self.agent_profile)
        await injector.inject_to_tool_result(result)

    @abstractmethod
    async def add_tool_result(self, tool_call_id: str, tool_name: str, result: Any, inject_reminders: bool = False) -> None:
        """
        Add tool execution result to context (async).

        Since we manage messages sequentially, tool results are simply
        appended after their corresponding tool calls.

        Provider implementations should inject system reminders to result content if inject_reminders=True.
        When injecting reminders, implementations MUST call get_all_reminders(check_queue=True) to
        capture user messages sent during tool execution. These messages are removed from the queue
        and injected as system-reminder blocks, allowing the LLM to immediately respond to user's
        updated instructions.

        Now async to support querying remote PFC task status and queue messages.

        Args:
            tool_call_id: Unique identifier for tool call
            tool_name: Tool name
            result: Tool execution result
            inject_reminders: Whether to inject system reminders (including queue messages) into this result
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

        # Count non-tool messages
        non_tool_count = sum(
            1 for msg in messages
            if not self._is_tool_call(msg) and not self._is_tool_result(msg)
        )

        # If we already have fewer non-tool messages than recent_messages_length, return all
        if non_tool_count <= recent_messages_length:
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
            'working_contents_count': len(self.working_contents)
        }
    
    def clear_runtime_context(self) -> None:
        """Clear runtime context for session cleanup."""
        self.working_contents.clear()

        # Clear status monitor for this session
        from backend.infrastructure.monitoring import clear_status_monitor
        clear_status_monitor(self.session_id)


