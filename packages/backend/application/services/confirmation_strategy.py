"""
Tool Confirmation Strategy - Handles user confirmation for tool execution.

Extracted confirmation logic for extensibility.
Used by Agent to request user confirmation before executing tools.
Supports different confirmation types: exec, edit, info.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


@dataclass
class ConfirmationInfo:
    """Information needed for tool confirmation request."""
    tool_name: str
    tool_id: str
    command: str
    description: Optional[str]
    confirmation_type: str  # "exec", "edit", "info"
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    file_diff: Optional[str] = None
    original_content: Optional[str] = None
    new_content: Optional[str] = None


class ConfirmationStrategy:
    """
    Strategy for handling tool confirmation requests.

    Supports extensible confirmation for different tool types.
    Future subagents can override or extend confirmation behavior.
    """

    def __init__(self, tool_manager: Any):
        """
        Initialize ConfirmationStrategy.

        Args:
            tool_manager: ToolManager for checking confirmation requirements
        """
        self.tool_manager = tool_manager

    def requires_confirmation(self, tool_name: str, tool_args: Dict) -> bool:
        """Check if tool requires user confirmation."""
        return self.tool_manager._requires_user_confirmation(tool_name, tool_args)

    async def build_confirmation_info(
        self,
        tool_call: Dict
    ) -> ConfirmationInfo:
        """
        Build confirmation information for a tool call.

        Args:
            tool_call: Tool call dict with 'id', 'name', 'arguments'

        Returns:
            ConfirmationInfo with all required confirmation data
        """
        tool_name = tool_call.get('name', '')
        tool_args = tool_call.get('arguments', {})
        tool_id = tool_call.get('id', '')

        # Dispatch to specific handler based on tool type
        if tool_name == "bash":
            return self._build_bash_confirmation(tool_id, tool_name, tool_args)
        elif tool_name == "edit":
            return await self._build_edit_confirmation(tool_id, tool_name, tool_args)
        elif tool_name == "write":
            return await self._build_write_confirmation(tool_id, tool_name, tool_args)
        elif tool_name == "pfc_execute_task":
            return self._build_pfc_confirmation(tool_id, tool_name, tool_args)
        elif tool_name == "invoke_agent":
            return self._build_invoke_agent_confirmation(tool_id, tool_name, tool_args)
        else:
            return self._build_generic_confirmation(tool_id, tool_name, tool_args)

    def _build_bash_confirmation(
        self,
        tool_id: str,
        tool_name: str,
        tool_args: Dict
    ) -> ConfirmationInfo:
        """Build confirmation info for bash command."""
        command = tool_args.get("command", "")
        description = tool_args.get("description")
        if not description:
            description = f"Execute bash command: {command}"

        return ConfirmationInfo(
            tool_name=tool_name,
            tool_id=tool_id,
            command=command,
            description=description,
            confirmation_type="exec"
        )

    async def _build_edit_confirmation(
        self,
        tool_id: str,
        tool_name: str,
        tool_args: Dict
    ) -> ConfirmationInfo:
        """Build confirmation info for file edit."""
        file_path = tool_args.get("file_path", "unknown")
        command = f"Edit file: {file_path}"
        description = tool_args.get("description")

        # Generate diff
        file_diff = None
        original_content = None
        new_content = None

        diff_info = await self.tool_manager._generate_edit_diff(file_path, tool_args)
        if diff_info:
            file_diff = diff_info.get("diff")
            original_content = diff_info.get("original", "")
            new_content = diff_info.get("new", "")

        return ConfirmationInfo(
            tool_name=tool_name,
            tool_id=tool_id,
            command=command,
            description=description,
            confirmation_type="edit",
            file_name=Path(file_path).name if file_path else "unknown",
            file_path=file_path,
            file_diff=file_diff,
            original_content=original_content,
            new_content=new_content
        )

    async def _build_write_confirmation(
        self,
        tool_id: str,
        tool_name: str,
        tool_args: Dict
    ) -> ConfirmationInfo:
        """Build confirmation info for file write."""
        file_path = tool_args.get("file_path", "unknown")
        command = f"Write file: {file_path}"
        description = tool_args.get("description")

        # Generate diff
        file_diff = None
        original_content = None
        new_content = None

        diff_info = await self.tool_manager._generate_write_diff(file_path, tool_args)
        if diff_info:
            file_diff = diff_info.get("diff")
            original_content = diff_info.get("original", "")
            new_content = diff_info.get("new", "")

        return ConfirmationInfo(
            tool_name=tool_name,
            tool_id=tool_id,
            command=command,
            description=description,
            confirmation_type="edit",
            file_name=Path(file_path).name if file_path else "unknown",
            file_path=file_path,
            file_diff=file_diff,
            original_content=original_content,
            new_content=new_content
        )

    def _build_pfc_confirmation(
        self,
        tool_id: str,
        tool_name: str,
        tool_args: Dict
    ) -> ConfirmationInfo:
        """Build confirmation info for PFC task execution."""
        entry_script = tool_args.get("entry_script", "unknown")
        run_in_background = tool_args.get("run_in_background", True)
        bg_info = " (background)" if run_in_background else " (foreground)"
        command = f"Execute PFC task{bg_info}: {entry_script}"
        description = tool_args.get("description")

        return ConfirmationInfo(
            tool_name=tool_name,
            tool_id=tool_id,
            command=command,
            description=description,
            confirmation_type="exec"
        )

    def _build_invoke_agent_confirmation(
        self,
        tool_id: str,
        tool_name: str,
        tool_args: Dict
    ) -> ConfirmationInfo:
        """Build confirmation info for SubAgent invocation."""
        # Parameter names match invoke_agent tool definition
        subagent_type = tool_args.get("subagent_type", "unknown")
        prompt = tool_args.get("prompt", "")
        task_description = tool_args.get("description", "")
        # Truncate long prompts
        if len(prompt) > 100:
            prompt = prompt[:100] + "..."
        command = f"Invoke SubAgent: {subagent_type}"
        # Prefer task description over prompt for display
        description = f"Task: {task_description}" if task_description else (f"Prompt: {prompt}" if prompt else None)

        return ConfirmationInfo(
            tool_name=tool_name,
            tool_id=tool_id,
            command=command,
            description=description,
            confirmation_type="info"
        )

    def _build_generic_confirmation(
        self,
        tool_id: str,
        tool_name: str,
        tool_args: Dict
    ) -> ConfirmationInfo:
        """Build confirmation info for generic tool."""
        command = f"{tool_name} operation"
        description = tool_args.get("description")

        return ConfirmationInfo(
            tool_name=tool_name,
            tool_id=tool_id,
            command=command,
            description=description,
            confirmation_type="info"
        )

    async def request_confirmation(
        self,
        info: ConfirmationInfo,
        session_id: str,
        message_id: str
    ):
        """
        Request user confirmation for tool execution.

        Args:
            info: ConfirmationInfo with all confirmation data
            session_id: Session ID
            message_id: Message ID containing the tool call

        Returns:
            ConfirmationResult with outcome and optional user_message
        """
        from backend.application.services.notifications.tool_confirmation_service import (
            get_tool_confirmation_service,
            ConfirmationResult,
        )

        confirmation_service = get_tool_confirmation_service()
        if not confirmation_service:
            print(f"[ConfirmationStrategy] Service not available, auto-rejecting {info.tool_name}")
            return ConfirmationResult(outcome="reject", user_message="Confirmation service not available")

        try:
            result = await confirmation_service.request_confirmation(
                session_id=session_id,
                message_id=message_id,
                tool_call_id=info.tool_id,
                tool_name=info.tool_name,
                command=info.command,
                description=info.description,
                confirmation_type=info.confirmation_type,
                file_name=info.file_name,
                file_path=info.file_path,
                file_diff=info.file_diff,
                original_content=info.original_content,
                new_content=info.new_content
            )
            return result

        except Exception as e:
            print(f"[ConfirmationStrategy] Error requesting confirmation: {e}")
            return ConfirmationResult(outcome="reject", user_message=f"Error during confirmation: {str(e)}")
