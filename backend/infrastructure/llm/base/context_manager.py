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

        # Request configuration storage
        self.agent_profile = "general"
        self.enable_memory = True

        # Tool call tracking
        self._has_tool_calls = False

        # Cached system reminders (captured before tool execution)
        self._cached_system_reminders: List[str] = []

        # PFC task status transition tracking (session-scoped, memory-only)
        self._notified_completions: set = set()  # Task IDs that have been notified as completed/failed
        self._last_task_states: Dict[str, str] = {}  # Last known status for each task_id

        # Streaming message tracking (set during streaming responses)
        self.streaming_message_id: Optional[str] = None  # Message ID for streaming response updates
    
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
        # Initialize working contents from history
        self.initialize_from_messages(historical_messages)

        # Mark as initialized
        self._initialized_from_history = True
    
    async def add_user_message(self, user_message: BaseMessage) -> None:
        """
        Add a new user message to the context incrementally (async).

        This method is called for each new user input, adding it to the
        existing context without re-processing historical messages.

        Now supports async reminder injection for both bash processes and PFC tasks.

        Args:
            user_message: New user message to add
        """
        if not self._initialized_from_history:
            # Fallback to old behavior if not properly initialized
            self.initialize_from_messages([user_message])
            return

        # Inject system reminders to user message content BEFORE formatting and storing
        # Now async to support both local bash processes and remote PFC task queries
        reminders = await self._get_background_task_reminders()
        print(f"[DEBUG] add_user_message: Got {len(reminders)} reminders for session {self.session_id}")

        if reminders:
            reminder_text = "\n\n" + "\n\n".join([
                f"<system-reminder>\n{reminder}\n</system-reminder>"
                for reminder in reminders
            ])

            # Modify user_message.content to inject reminders
            if isinstance(user_message.content, str):
                user_message.content += reminder_text
                print(f"[DEBUG] Injected reminders to string content")
            elif isinstance(user_message.content, list):
                # Find last text item and append
                for item in reversed(user_message.content):
                    if isinstance(item, dict) and 'text' in item:
                        item['text'] += reminder_text
                        print(f"[DEBUG] Injected reminders to list content")
                        break

        # Format and add to working contents
        formatter_class = get_message_formatter_class(self._provider_name)
        formatted_message = formatter_class.format_single_message(user_message)

        self.working_contents.append(formatted_message)

    async def add_user_message_from_data(self, parsed_data: dict) -> None:
        """
        Create user message from parsed data and update configuration (async).

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

        # Add to context with async reminder injection
        await self.add_user_message(user_message)

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
    async def add_tool_result(self, tool_call_id: str, tool_name: str, result: Any, inject_reminders: bool = False) -> None:
        """
        Add tool execution result to context (async).

        Since we manage messages sequentially, tool results are simply
        appended after their corresponding tool calls.

        Provider implementations should inject system reminders to result content if inject_reminders=True.
        Now async to support querying remote PFC task status.

        Args:
            tool_call_id: Unique identifier for tool call
            tool_name: Tool name
            result: Tool execution result
            inject_reminders: Whether to inject system reminders into this result
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
            'working_contents_count': len(self.working_contents),
            'initialized': self._initialized_from_history
        }
    
    def clear_runtime_context(self) -> None:
        """Clear runtime context for session cleanup."""
        self.working_contents.clear()
        self._initialized_from_history = False

    async def _get_background_task_reminders(self) -> List[str]:
        """
        Get background task status reminders (async).

        Queries both local bash processes and remote PFC tasks concurrently.

        Returns:
            List[str]: List of reminder strings for active background tasks
        """
        import asyncio

        reminders = []

        # Query bash processes (local, fast)
        try:
            from backend.infrastructure.mcp.tools.coding.utils.background_process_manager import get_process_manager

            process_manager = get_process_manager()
            bash_reminders = process_manager.get_system_reminders(self.session_id)
            reminders.extend(bash_reminders)
            print(f"[DEBUG] Got {len(bash_reminders)} bash process reminders")

        except Exception as e:
            print(f"[DEBUG] Failed to get bash process reminders: {e}")

        # Query PFC tasks (remote, may be slow)
        try:
            from backend.infrastructure.pfc.websocket_client import get_client

            # Get WebSocket client and query running tasks
            client = await get_client()
            result = await client.list_tasks(
                session_id=self.session_id,
                offset=0,
                limit=5  # Only get recent tasks for reminders
            )

            if result.get("status") == "success":
                tasks = result.get("data", [])
                current_states = {}  # Snapshot of current task states

                # Step 1: Detect status transitions (running → completed/failed)
                completion_notifications = []
                for task in tasks:
                    task_id = task.get("task_id", "unknown")
                    current_status = task.get("status", "unknown")
                    current_states[task_id] = current_status

                    # Check for transition: was running, now completed/failed
                    last_status = self._last_task_states.get(task_id)
                    if (last_status == "running" and
                        current_status in ["completed", "failed"] and
                        task_id not in self._notified_completions):

                        # Generate completion notification
                        description = task.get("description", "")
                        script_path = task.get("script_path", task.get("name", "unknown"))
                        elapsed_time = task.get("elapsed_time", 0)

                        # Status icon
                        status_icon = "✓" if current_status == "completed" else "✗"

                        completion_notifications.append(
                            f"{status_icon} PFC Task {task_id} {current_status}: "
                            f"{script_path} (elapsed: {elapsed_time:.1f}s) - {description}. "
                            f"Use pfc_check_task_status('{task_id}') to see results."
                        )

                        # Mark as notified
                        self._notified_completions.add(task_id)
                        print(f"[DEBUG] Task {task_id} transition detected: running → {current_status}")

                # Step 2: Add completion notifications first (higher priority)
                reminders.extend(completion_notifications)

                # Step 3: Add running tasks reminders (only tasks not notified as completed)
                running_tasks = [
                    task for task in tasks
                    if task.get("status") == "running"
                    and task.get("task_id") not in self._notified_completions
                ]

                # Limit to 3 tasks to avoid overwhelming LLM
                for task in running_tasks[:3]:
                    task_id = task.get("task_id", "unknown")
                    description = task.get("description", "")
                    script_path = task.get("script_path", task.get("name", "unknown"))
                    status = task.get("status", "unknown")
                    elapsed_time = task.get("elapsed_time", 0)

                    reminder = (
                        f"PFC Task {task_id} "
                        f"(script: {script_path}) "
                        f"(status: {status}) "
                        f"(elapsed: {elapsed_time:.1f}s) "
                        f"- {description}. "
                        "You can check its status and output using the pfc_check_task_status tool."
                    )
                    reminders.append(reminder)

                if len(running_tasks) > 3:
                    additional_count = len(running_tasks) - 3
                    reminders.append(
                        f"Note: {additional_count} more PFC task(s) are running. "
                        "Use pfc_list_tasks to see all tasks."
                    )

                # Step 4: Update state snapshot for next comparison
                self._last_task_states = current_states

                print(f"[DEBUG] Got {len(completion_notifications)} completion notifications, {len(running_tasks)} running task reminders")

        except Exception as e:
            # PFC server may not be running - this is normal, don't break the flow
            print(f"[DEBUG] Failed to get PFC task reminders: {e}")

        return reminders


