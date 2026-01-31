"""
BaseToolManager - Abstract base class for all LLM client Tool Managers.

Designed for toyoura-nagisa's multi-LLM architecture as a unified tool management interface.
Defines core methods that all Tool Managers must implement to ensure consistency and extensibility.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import inspect
from typing import Any, Dict, Optional

from pydantic import ValidationError

from backend.application.tools.schema_builder import build_params_model, get_context_param_name
from backend.infrastructure.llm.shared.utils.tool_schema import ToolSchema
from backend.config.dev import get_dev_config

# Security imports removed - all tools now require session ID
from backend.application.tools.context import ToolContext, ToolRequestMeta, ToolRequestContext


class BaseToolManager(ABC):
    """
    Abstract base class for LLM client tool managers.

    Defines unified interface specifications supporting:
    - MCP client management and session isolation
    - Tool schema retrieval and caching
    - Meta tool processing and result parsing
    - Tool execution and result formatting
    - Client-specific schema formatting
    """

    def __init__(self):
        """Initialize base state."""

        # Track files read per session (for edit prerequisite validation)
        # Not affected by context window truncation - real-time tracking
        self._session_read_files: Dict[str, set] = {}  # {session_id: {normalized_paths}}

        # Track MCP tool sources for execution routing
        # Maps tool_name -> server_name (only for MCP tools)
        self._mcp_tool_mapping: Dict[str, str] = {}

    @staticmethod
    def _build_tool_context(session_id: str, tool_call_id: str) -> ToolContext:
        meta = ToolRequestMeta(client_id=session_id, tool_call_id=tool_call_id)
        return ToolContext(client_id=session_id, request_context=ToolRequestContext(meta=meta))

    def _normalize_file_path(self, file_path: str) -> str:
        """
        Normalize file path for consistent comparison.

        Resolves absolute paths and handles path separators uniformly.

        Args:
            file_path: Raw file path from tool arguments

        Returns:
            str: Normalized absolute path
        """
        from pathlib import Path

        try:
            # Resolve to absolute path for consistent comparison
            return str(Path(file_path).resolve())
        except Exception:
            # If path is invalid, return as-is for error handling elsewhere
            return file_path

    def _track_read_file(self, session_id: str, file_path: str) -> None:
        """
        Track that a file has been read in this session.

        Real-time tracking independent of context window - files remain
        tracked even if read messages are truncated from context.

        Args:
            session_id: Session identifier
            file_path: File path that was successfully read
        """
        if session_id not in self._session_read_files:
            self._session_read_files[session_id] = set()

        normalized_path = self._normalize_file_path(file_path)
        self._session_read_files[session_id].add(normalized_path)

        if get_dev_config().debug_mode:
            print(f"[BaseToolManager] Tracked read file for session {session_id}: {normalized_path}")

    def _has_read_file(self, session_id: str, file_path: str) -> bool:
        """
        Check if a file has been read in this session.

        Args:
            session_id: Session identifier
            file_path: File path to check

        Returns:
            bool: True if file was read in this session, False otherwise
        """
        normalized_path = self._normalize_file_path(file_path)
        has_read = normalized_path in self._session_read_files.get(session_id, set())

        if get_dev_config().debug_mode:
            print(f"[BaseToolManager] Check read file {normalized_path}: {has_read}")

        return has_read

    def clear_session_read_tracking(self, session_id: str) -> None:
        """
        Clear read file tracking for a session.

        Should be called when a session ends to free memory.

        Args:
            session_id: Session identifier to clear
        """
        if session_id in self._session_read_files:
            del self._session_read_files[session_id]

            if get_dev_config().debug_mode:
                print(f"[BaseToolManager] Cleared read file tracking for session {session_id}")

    async def get_standardized_tools(self, session_id: str, agent_profile="pfc_expert") -> Dict[str, ToolSchema]:
        """
        Get standardized ToolSchema objects based on agent profile.

        Includes both internal tools and MCP tools from connected servers.
        MCP tools are filtered based on session-specific server settings.

        Args:
            session_id: Session ID (required for session-specific MCP tool filtering)
            agent_profile: Agent profile name ("coding", "pfc", "disabled")

        Returns:
            Dict[str, ToolSchema]: Tool name -> ToolSchema mapping
        """
        tools_dict: Dict[str, ToolSchema] = {}

        # Step 1: Load internal tools
        try:
            from backend.application.tools.registry import TOOL_REGISTRY

            tool_defs = TOOL_REGISTRY.get_by_agent_profile(agent_profile)
            for tool_def in tool_defs.values():
                tool_schema = ToolSchema.from_tool_definition(tool_def)
                tools_dict[tool_schema.name] = tool_schema

        except Exception as e:
            if get_dev_config().debug_mode:
                print(f"[DEBUG] Error reading tool registry: {e}")

        # Step 2: Load MCP tools from connected servers (filtered by session config)
        try:
            from backend.infrastructure.mcp.client import get_mcp_client_manager
            from backend.infrastructure.storage.session_manager import is_mcp_server_enabled_for_session

            mcp_manager = get_mcp_client_manager()
            mcp_tools = mcp_manager.get_all_tools()

            # Clear and rebuild MCP tool mapping
            self._mcp_tool_mapping.clear()

            for mcp_tool in mcp_tools.values():
                server_name = mcp_tool.server_name

                # Check if this server is enabled for this session
                if not is_mcp_server_enabled_for_session(session_id, server_name):
                    if get_dev_config().debug_mode:
                        print(
                            f"[DEBUG] MCP tool '{mcp_tool.name}' from {server_name} "
                            f"skipped (server disabled for session)"
                        )
                    continue

                # Convert MCPTool to ToolSchema
                tool_schema = mcp_tool.to_tool_schema()

                # Avoid name collision: MCP tools don't override internal tools
                if tool_schema.name not in tools_dict:
                    tools_dict[tool_schema.name] = tool_schema
                    # Track this tool as MCP for execution routing
                    self._mcp_tool_mapping[tool_schema.name] = server_name
                elif get_dev_config().debug_mode:
                    print(
                        f"[DEBUG] MCP tool '{tool_schema.name}' from {server_name} "
                        f"skipped (internal tool exists)"
                    )

        except Exception as e:
            # Always log MCP errors for debugging
            print(f"[MCP] Error loading MCP tools: {e}")

        return tools_dict

    @abstractmethod
    async def get_function_call_schemas(self, session_id: str, agent_profile="pfc_expert") -> Any:
        """
        Get tool schemas formatted for the specific LLM provider.
        Uses get_standardized_tools() internally, then converts to provider format.

        Args:
            session_id: Session ID (required)
            agent_profile: Agent profile name ("coding", "pfc", "disabled")

        Returns:
            Tool schema list adapted for target LLM format (format varies by client)
        """
        pass

    def _check_user_interrupted(self, session_id: str) -> bool:
        """
        Check if user has requested interrupt for this session.

        Args:
            session_id: Session ID to check

        Returns:
            bool: True if user interrupt flag is set
        """
        try:
            from backend.infrastructure.monitoring import get_status_monitor

            status_monitor = get_status_monitor(session_id)
            return status_monitor.is_user_interrupted()
        except Exception:
            return False

    async def _execute_tool(
        self, tool_name: str, tool_args: Dict[str, Any], session_id: str, tool_call_id: str = ""
    ) -> Dict[str, Any]:
        """
        Execute a tool (internal or MCP) with routing based on tool source.

        Args:
            tool_name: Tool name
            tool_args: Tool arguments
            session_id: Session ID for dependency injection
            tool_call_id: LLM-generated tool call ID

        Returns:
            Dict[str, Any]: ToolResult dictionary
        """
        from backend.shared.utils.tool_result import error_response

        # Check if this is an MCP tool
        if tool_name in self._mcp_tool_mapping:
            return await self._execute_mcp_tool(tool_name, tool_args)

        # Execute as internal tool
        return await self._execute_internal_tool(tool_name, tool_args, session_id, tool_call_id)

    async def _execute_internal_tool(
        self, tool_name: str, tool_args: Dict[str, Any], session_id: str, tool_call_id: str = ""
    ) -> Dict[str, Any]:
        """
        Execute an internal tool with manual validation and context injection.

        Args:
            tool_name: Tool name
            tool_args: Tool arguments
            session_id: Session ID for dependency injection
            tool_call_id: LLM-generated tool call ID

        Returns:
            Dict[str, Any]: ToolResult dictionary
        """
        from backend.application.tools.registry import TOOL_REGISTRY
        from backend.shared.utils.tool_result import error_response

        tool_def = TOOL_REGISTRY.get(tool_name)
        if tool_def is None or tool_def.handler is None:
            return error_response(f"Tool not found: {tool_name}")

        params_model = build_params_model(tool_def.handler)
        validated = params_model.model_validate(tool_args)
        tool_context = self._build_tool_context(session_id, tool_call_id)

        context_param = get_context_param_name(tool_def.handler)

        call_args = validated.model_dump()
        if context_param:
            call_args[context_param] = tool_context

        result = tool_def.handler(**call_args)
        if inspect.isawaitable(result):
            result = await result

        return result

    async def _execute_mcp_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an MCP tool via the MCP client manager.

        Args:
            tool_name: Tool name
            tool_args: Tool arguments

        Returns:
            Dict[str, Any]: ToolResult dictionary (converted from MCP result)
        """
        from backend.infrastructure.mcp.client import get_mcp_client_manager
        from backend.shared.utils.tool_result import error_response, success_response

        try:
            mcp_manager = get_mcp_client_manager()
            result = await mcp_manager.call_tool(tool_name, tool_args)

            if result.get("status") == "success":
                # Convert MCP result to internal ToolResult format
                content_parts = result.get("content", [])

                # Extract text content for llm_content
                text_parts = []
                for part in content_parts:
                    if part.get("type") == "text":
                        text_parts.append({"type": "text", "text": part.get("text", "")})

                return success_response(
                    message=f"MCP tool '{tool_name}' executed successfully",
                    llm_content={"parts": text_parts} if text_parts else None,
                    data={
                        "server": result.get("server"),
                        "content": content_parts,
                        "structuredContent": result.get("structuredContent"),
                    },
                )
            else:
                return error_response(
                    result.get("message", f"MCP tool '{tool_name}' failed"),
                    llm_content={"parts": [{"type": "text", "text": result.get("message", "Unknown error")}]},
                )

        except Exception as e:
            if get_dev_config().debug_mode:
                print(f"[DEBUG] MCP tool execution error: {e}")
            return error_response(
                f"MCP tool '{tool_name}' execution failed: {e}",
                llm_content={"parts": [{"type": "text", "text": str(e)}]},
            )

    async def _execute_tool_with_interrupt_check(
        self, function_call: dict, session_id: str, message_id: str
    ) -> Dict[str, Any]:
        """
        Execute a tool with periodic interrupt checking.

        Wraps handle_function_call with asyncio polling to check for user
        interrupt during long-running tool execution.

        Args:
            function_call: Function call dictionary
            session_id: Session ID
            message_id: Message ID

        Returns:
            Dict[str, Any]: Tool result, or interrupt error if interrupted
        """
        import asyncio

        tool_name = function_call.get("name", "unknown")

        # Create task for tool execution
        tool_task = asyncio.create_task(self.handle_function_call(function_call, session_id, message_id))

        # Poll for interrupt every 100ms while tool is executing
        while not tool_task.done():
            if self._check_user_interrupted(session_id):
                # User interrupted - cancel the task
                tool_task.cancel()
                try:
                    await tool_task
                except asyncio.CancelledError:
                    pass

                if get_dev_config().debug_mode:
                    print(f"[BaseToolManager] Tool {tool_name} interrupted by user")

                # Return interrupt error (matches Claude Code behavior)
                from backend.shared.utils.tool_result import error_response

                interrupt_message = "[Request interrupted by user for tool use]"
                interrupt_result = error_response(
                    interrupt_message, llm_content={"parts": [{"type": "text", "text": interrupt_message}]}
                )
                interrupt_result["user_interrupted"] = True
                return interrupt_result

            # Wait a short time before checking again
            try:
                # Use wait_for with shield to avoid cancelling the actual task
                return await asyncio.wait_for(asyncio.shield(tool_task), timeout=0.1)
            except asyncio.TimeoutError:
                # Timeout just means we should check interrupt again
                continue

        # Task completed normally
        return await tool_task

    async def handle_function_call(self, function_call: dict, session_id: str, _message_id: str = "") -> Dict[str, Any]:
        """
        Handle LLM-generated function_call requests.

        Pure tool execution - confirmation is handled by Agent (application layer).

        Args:
            function_call: Function call dictionary containing:
                - name: str - Tool name to execute
                - arguments: Dict[str, Any] - Tool arguments (optional, defaults to {})
                - id: str - Tool call ID for tracking (optional, defaults to "")
            session_id: Session ID for context-aware tools and dependency injection (required)
            _message_id: Reserved for future use (currently unused after confirmation moved to orchestrator)

        Returns:
            Dict[str, Any]: ToolResult dictionary with structure:
                - status: Literal["success", "error"] - Operation outcome
                - message: str - User-facing summary
                - llm_content: Dict with parts structure
                - data: Optional[Dict[str, Any]] - Tool-specific data

        Raises:
            RuntimeError: When tool execution fails due to infrastructure errors
        """
        tool_name = function_call.get("name", "")
        tool_args = function_call.get("arguments", {})
        tool_call_id = function_call.get("id", "")

        try:
            # Step 0: Validate edit prerequisite (must read file before editing)
            if tool_name == "edit":
                file_path = tool_args.get("file_path", "")
                if file_path:
                    from backend.shared.utils.tool_result import error_response

                    # Note: Path security check is handled by edit tool itself using dynamic workspace
                    # We only check the read policy here

                    # Policy check: Has the file been read in this session?
                    if not self._has_read_file(session_id, file_path):
                        error_message = (
                            f"File has not been read yet. Read it first before editing.\n\n"
                            f"You must use the Read tool to read {file_path} before editing it. "
                            f"This ensures you have the current file content and correct line numbers."
                        )

                        if get_dev_config().debug_mode:
                            print(f"[BaseToolManager] Edit blocked: {file_path} not read yet in session {session_id}")

                        return error_response(
                            error_message, llm_content={"parts": [{"type": "text", "text": error_message}]}
                        )

            # Note: User confirmation is now handled by Agent (application layer)
            # This method only handles pure tool execution

            # Step 1: Execute the tool
            tool_result = await self._execute_tool(tool_name, tool_args, session_id, tool_call_id)

            # Step 2: Track successful read operations for edit prerequisite validation
            if tool_name == "read" and tool_result.get("status") == "success":
                file_path = tool_args.get("path", "")
                if file_path:
                    self._track_read_file(session_id, file_path)

            # Step 3: Track successful write operations as "read" for edit prerequisite
            # This allows edit tool to modify files that were just written
            if tool_name == "write" and tool_result.get("status") == "success":
                file_path = tool_args.get("file_path", "")
                if file_path:
                    self._track_read_file(session_id, file_path)

            # Step 4: Return tool result directly (already in standardized ToolResult format)
            # Note: _subagent_user_rejected marker is handled by tool_executor
            # to ensure results are saved to context before raising exception
            return tool_result

        except ValidationError as e:
            # Pydantic validation error - format for LLM understanding
            if get_dev_config().debug_mode:
                print(f"[BaseToolManager] Validation error for tool {tool_name}: {e}")

            # Format validation errors for LLM
            error_details = []
            for error in e.errors():
                field = ".".join(str(loc) for loc in error["loc"])
                error_type = error["type"]
                message = error["msg"]

                # Format based on error type
                if error_type == "unexpected_keyword_argument":
                    error_details.append(f"  • Parameter '{field}': Not defined in tool schema (unexpected argument)")
                elif error_type == "missing":
                    error_details.append(f"  • Parameter '{field}': Required but not provided")
                elif error_type in ["type_error", "value_error"]:
                    error_details.append(f"  • Parameter '{field}': {message}")
                else:
                    error_details.append(f"  • Parameter '{field}': {message} (type: {error_type})")

            formatted_errors = "\n".join(error_details)
            error_message = (
                f"Tool '{tool_name}' parameter validation failed.\n\n"
                f"Validation errors:\n{formatted_errors}\n\n"
                f"Please check the tool schema and correct the parameters."
            )

            from backend.shared.utils.tool_result import error_response

            return error_response(error_message, llm_content={"parts": [{"type": "text", "text": error_message}]})

        except Exception as e:
            # Let UserRejectionInterruption propagate directly
            # This ensures SubAgent rejection stops MainAgent execution
            from backend.shared.exceptions import UserRejectionInterruption

            if isinstance(e, UserRejectionInterruption):
                raise

            # System/infrastructure errors - re-raise for upper layer handling
            if get_dev_config().debug_mode:
                print(f"Error calling tool {tool_name}: {str(e)}")
            raise RuntimeError(f"Tool '{tool_name}' execution failed: {str(e)}") from e

    def _requires_user_confirmation(self, tool_name: str, tool_args: Dict[str, Any]) -> bool:
        """
        Check if a tool requires user confirmation before execution.

        Args:
            tool_name: Name of the tool to execute
            tool_args: Arguments for the tool (reserved for future command filtering)

        Returns:
            bool: True if user confirmation is required, False otherwise
        """
        _ = tool_args  # Reserved for future command filtering
        # Define tools that require user confirmation
        CONFIRMATION_REQUIRED_TOOLS = {
            "bash": True,  # All bash commands require confirmation
            "edit": True,  # All file edits require confirmation
            "write": True,  # All file writes require confirmation
            "pfc_execute_task": True,  # PFC task execution requires confirmation
            "invoke_agent": True,  # SubAgent invocation - prevents blocking other confirmations
            # Add other tools here as needed
            # "system_command": True,  # Example: other system commands
        }

        # Basic tool-level check
        if CONFIRMATION_REQUIRED_TOOLS.get(tool_name, False):
            # Future enhancement: could check specific commands within _tool_args
            # For example, allow safe commands like 'ls', 'pwd' without confirmation
            # command = _tool_args.get("command", "")
            # safe_commands = ["ls", "pwd", "echo", "date", "whoami"]
            # if any(command.startswith(safe_cmd) for safe_cmd in safe_commands):
            #     return False
            return True

        return False

    async def _generate_edit_diff(self, file_path: str, tool_args: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """
        Generate diff for edit tool confirmation.

        Args:
            file_path: Path to the file being edited
            tool_args: Edit tool arguments containing old_string and new_string

        Returns:
            Dict with 'diff', 'original', 'new' keys or None if diff generation fails
        """
        try:
            import difflib
            from pathlib import Path

            old_string = tool_args.get("old_string", "")
            new_string = tool_args.get("new_string", "")

            # Read current file content
            abs_path = Path(file_path)
            if abs_path.exists():
                original_content = abs_path.read_text(encoding="utf-8")
            else:
                original_content = ""

            # Apply the edit to get new content
            if old_string:
                new_content = original_content.replace(old_string, new_string, 1)
            else:
                # Empty old_string means creating new file
                new_content = new_string

            # Generate unified diff
            # Use splitlines() without keepends to avoid issues with missing newlines,
            # then add linebreak='' to unified_diff for proper line ending handling
            file_name = abs_path.name
            diff_lines = difflib.unified_diff(
                original_content.splitlines(),
                new_content.splitlines(),
                fromfile=f"a/{file_name}",
                tofile=f"b/{file_name}",
                n=3,  # Context lines
                lineterm="",  # Don't add line terminators, we'll join with \n
            )
            file_diff = "\n".join(diff_lines)

            return {"diff": file_diff, "original": original_content, "new": new_content}
        except Exception as e:
            if get_dev_config().debug_mode:
                print(f"[BaseToolManager] Error generating edit diff: {e}")
            return None

    async def _generate_write_diff(self, file_path: str, tool_args: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """
        Generate diff for write tool confirmation.

        Args:
            file_path: Path to the file being written
            tool_args: Write tool arguments containing content

        Returns:
            Dict with 'diff', 'original', 'new' keys or None if diff generation fails
        """
        try:
            import difflib
            from pathlib import Path

            new_content = tool_args.get("content", "")

            # Read current file content if exists
            abs_path = Path(file_path)
            if abs_path.exists():
                original_content = abs_path.read_text(encoding="utf-8")
            else:
                original_content = ""

            # Generate unified diff
            # Use splitlines() without keepends to avoid issues with missing newlines,
            # then use lineterm='' for proper line ending handling
            file_name = abs_path.name
            diff_lines = difflib.unified_diff(
                original_content.splitlines(),
                new_content.splitlines(),
                fromfile=f"a/{file_name}",
                tofile=f"b/{file_name}",
                n=3,  # Context lines
                lineterm="",  # Don't add line terminators, we'll join with \n
            )
            file_diff = "\n".join(diff_lines)

            return {"diff": file_diff, "original": original_content, "new": new_content}
        except Exception as e:
            if get_dev_config().debug_mode:
                print(f"[BaseToolManager] Error generating write diff: {e}")
            return None
