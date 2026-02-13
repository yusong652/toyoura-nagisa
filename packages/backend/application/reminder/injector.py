"""
ReminderInjector - Unified service for injecting system status reminders.

This service centralizes the logic for collecting and injecting reminders into:
1. User messages (with file mentions, without queue messages)
2. Tool results (without file mentions, with queue messages)

Replaces scattered injection logic in ChatService and BaseContextManager.
"""
import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class ReminderInjector:
    """
    Unified service for collecting and injecting system status reminders.

    Provides two main injection points:
    - User messages: Includes file mentions, excludes queue messages
    - Tool results: Excludes file mentions, includes queue messages

    Usage:
        injector = ReminderInjector(session_id, agent_profile)

        # For user messages
        await injector.inject_to_user_message(content, mentioned_files)

        # For tool results
        await injector.inject_to_tool_result(result)
    """

    def __init__(self, session_id: str, agent_profile = "pfc_expert"):
        """
        Initialize ReminderInjector with session context.

        Args:
            session_id: Session identifier for status monitor lookup
            agent_profile: Agent profile type for workspace-dependent monitors
        """
        self.session_id = session_id
        self.agent_profile = agent_profile

    async def inject_to_user_message(
        self,
        content: List[Dict[str, Any]],
        mentioned_files: Optional[List[str]] = None,
    ) -> None:
        """
        Inject reminders into user message content.

        Collects file mentions and status reminders (without queue messages),
        then injects them into the content list in-place.

        Args:
            content: User message content list (modified in-place)
            mentioned_files: List of file paths mentioned with @ syntax

        Note:
            - File mentions are processed first
            - Queue messages are NOT checked (user is initiating, not responding)
            - Supports multimodal content (text + inline_data for images)
        """
        reminders = await self._collect_reminders(
            check_queue=False,
            mentioned_files=mentioned_files,
        )

        if not reminders:
            return

        self._inject_to_content_list(content, reminders)

    async def inject_to_tool_result(self, result: Dict[str, Any]) -> None:
        """
        Inject reminders into tool result content.

        Collects status reminders (with queue messages) and injects them
        into the tool result's llm_content in-place.

        Args:
            result: Tool result dict with llm_content (modified in-place)

        Note:
            - File mentions are NOT processed (already in user message)
            - Queue messages ARE checked (may contain user updates during tool execution)
            - Only injects text reminders (no multimodal support for tool results)
        """
        reminders = await self._collect_reminders(check_queue=True)

        if not reminders:
            return

        self._inject_to_llm_content(result, reminders)

    async def _collect_reminders(
        self,
        check_queue: bool,
        mentioned_files: Optional[List[str]] = None,
    ) -> List[Union[str, Dict[str, Any]]]:
        """
        Collect all reminders from various sources.

        Collection order (for user messages):
        1. Rejection context
        2. File mentions
        3. Status reminders

        Args:
            check_queue: Whether to check queue for user messages during tool execution
            mentioned_files: List of file paths to process (only for user messages)

        Returns:
            List of reminders (strings or multimodal dicts)
        """
        reminders = []

        # 1. Check for rejection context (only for user messages, not tool results)
        if not check_queue:
            rejection_reminder = await self._get_rejection_context_reminder()
            if rejection_reminder:
                reminders.append(rejection_reminder)

        # 2. Process file mentions (only for user messages)
        if mentioned_files:
            from backend.infrastructure.file_mention import FileMentionProcessor
            processor = FileMentionProcessor(self.session_id, self.agent_profile)
            file_reminders = await processor.process_mentioned_files(mentioned_files)
            reminders.extend(file_reminders)

        # 3. Get status reminders from StatusMonitor
        from backend.infrastructure.monitoring import get_status_monitor
        status_monitor = get_status_monitor(self.session_id)
        status_reminders = await status_monitor.get_all_reminders(
            agent_profile=self.agent_profile,
            check_queue=check_queue
        )
        reminders.extend(status_reminders)

        return reminders

    async def _get_rejection_context_reminder(self) -> Optional[str]:
        """
        Get rejection context reminder if user previously rejected a tool.

        When user rejects a tool and then provides new input, we inject context
        about what was rejected so the agent understands the situation.

        Returns:
            Formatted reminder string or None if no rejection context exists
        """
        from backend.infrastructure.storage.session_manager import (
            load_runtime_state,
            update_runtime_state,
        )

        state = load_runtime_state(self.session_id)
        rejection_context = state.get("rejection_context")

        if not rejection_context:
            return None

        # Clear the rejection context after reading (one-time injection)
        update_runtime_state(self.session_id, "rejection_context", None)

        rejected_tools = rejection_context.get("rejected_tools", [])
        rejection_message = rejection_context.get("rejection_message")
        is_subagent = rejection_context.get("is_subagent", False)

        # Format the reminder
        tools_str = ", ".join(rejected_tools) if rejected_tools else "unknown"

        if is_subagent:
            reminder = (
                f"<system-reminder>\n"
                f"The user just rejected a SubAgent's tool call ({tools_str})."
            )
        else:
            reminder = (
                f"<system-reminder>\n"
                f"The user just rejected a tool call ({tools_str})."
            )

        if rejection_message:
            reminder += f"\nUser's reason: {rejection_message}"

        reminder += (
            f"\nPlease take this rejection into account and adjust your approach "
            f"based on the user's new input below.\n"
            f"</system-reminder>"
        )

        print(f"[ReminderInjector] Injecting rejection context reminder for session {self.session_id}")
        return reminder

    def _inject_to_content_list(
        self,
        content: List[Dict[str, Any]],
        reminders: List[Union[str, Dict[str, Any]]]
    ) -> None:
        """
        Inject reminders into a content list (user message format).

        Handles both text reminders and multimodal reminders (images).

        Args:
            content: Content list to modify in-place
            reminders: List of reminders to inject
        """
        if not isinstance(content, list):
            print(f"[WARNING] Unexpected content format: {type(content)}")
            return

        # Separate text and multimodal reminders
        text_reminders = []
        inline_data_parts = []

        for reminder in reminders:
            if isinstance(reminder, dict) and reminder.get("type") == "multimodal_file_mention":
                # Multimodal file mention (image, binary)
                for part in reminder.get("parts", []):
                    if isinstance(part, dict):
                        if part.get("type") == "text" and "text" in part:
                            text_reminders.append(part["text"])
                        elif "inline_data" in part:
                            inline_data_parts.append(part)
            elif isinstance(reminder, str):
                text_reminders.append(reminder)

        # Inject text reminders into last text part
        if text_reminders:
            reminder_text = "\n\n" + "\n\n".join(text_reminders)
            injected = False

            for part in reversed(content):
                if isinstance(part, dict) and part.get('type') == 'text' and 'text' in part:
                    part['text'] += reminder_text
                    injected = True
                    break

            # If no text part exists (image-only message), create one
            if not injected:
                content.append({
                    "type": "text",
                    "text": reminder_text.lstrip()
                })

        # Inject inline_data parts directly
        if inline_data_parts:
            content.extend(inline_data_parts)
            print(f"[DEBUG] Injected {len(inline_data_parts)} inline_data parts")

    def _inject_to_llm_content(
        self,
        result: Dict[str, Any],
        reminders: List[Union[str, Dict[str, Any]]]
    ) -> None:
        """
        Inject reminders into tool result's llm_content.

        Only processes text reminders (tool results don't support multimodal).

        Args:
            result: Tool result dict with llm_content to modify in-place
            reminders: List of reminders to inject
        """
        # Filter to text-only reminders for tool results
        text_reminders = [r for r in reminders if isinstance(r, str)]

        if not text_reminders:
            return

        reminder_text = "\n\n" + "\n\n".join(text_reminders)

        if not isinstance(result, dict) or 'llm_content' not in result:
            return

        llm_content = result.get('llm_content')
        if not isinstance(llm_content, dict) or 'parts' not in llm_content:
            return

        parts = llm_content.get('parts')
        if not isinstance(parts, list) or not parts:
            return

        # Find last text part and append reminder
        for part in reversed(parts):
            if isinstance(part, dict) and part.get('type') == 'text' and 'text' in part:
                part['text'] += reminder_text
                break

