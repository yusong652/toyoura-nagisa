"""
BaseToolManager - Abstract base class for all LLM client Tool Managers.

Designed for aiNagisa's multi-LLM architecture as a unified tool management interface.
Defines core methods that all Tool Managers must implement to ensure consistency and extensibility.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from fastmcp import Client as MCPClient
from mcp.types import CallToolRequestParams, CallToolRequest, ClientRequest, CallToolResult
from pydantic import ValidationError

from backend.infrastructure.mcp.utils import extract_tool_result_from_mcp
from backend.infrastructure.llm.shared.utils.tool_schema import ToolSchema
from backend.infrastructure.mcp.tool_profile_manager import ToolProfileManager, AgentProfile
from backend.config.llm import get_llm_settings
# Security imports removed - all tools now require session ID


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

        # MCP client will be retrieved from app state when needed
        self._mcp_client = None

        # Track files read per session (for edit prerequisite validation)
        # Not affected by context window truncation - real-time tracking
        self._session_read_files: Dict[str, set] = {}  # {session_id: {normalized_paths}}
    
    def get_mcp_client(self) -> MCPClient:
        """
        Return the shared MCP client from app state. FastMCP handles session isolation per request
        through the _meta.client_id parameter in tool calls.

        Returns:
            MCPClient: Shared client instance from app state
        """
        if self._mcp_client is None:
            from backend.shared.utils.app_context import get_mcp_client
            self._mcp_client = get_mcp_client()
        return self._mcp_client

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

        llm_settings = get_llm_settings()
        if llm_settings.debug:
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

        llm_settings = get_llm_settings()
        if llm_settings.debug:
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

            llm_settings = get_llm_settings()
            if llm_settings.debug:
                print(f"[BaseToolManager] Cleared read file tracking for session {session_id}")

    async def get_standardized_tools(self, session_id: str, agent_profile: str = 'general') -> Dict[str, ToolSchema]:
        """
        Get standardized ToolSchema objects based on agent profile.

        Args:
            session_id: Session ID (required for future session-specific tool filtering)
            agent_profile: Agent profile name ("coding", "lifestyle", "general", "pfc", "disabled")

        Returns:
            Dict[str, ToolSchema]: Tool name -> ToolSchema mapping
        """
        _ = session_id  # Reserved for future session-specific tool filtering

        tools_dict: Dict[str, ToolSchema] = {}

        try:
            llm_settings = get_llm_settings()
            mcp_client = self.get_mcp_client()
            async with mcp_client as mcp_async_client:
                # Get all MCP tools - list_tools() always returns a list
                mcp_tools = await mcp_async_client.list_tools()

                # Get tools for the specified profile
                profile_enum = AgentProfile(agent_profile)
                allowed_tools = set(ToolProfileManager.get_tools_for_profile(profile_enum))

                # Add tools to dictionary
                for mcp_tool in mcp_tools:
                    # Only load permitted tools
                    if mcp_tool.name not in allowed_tools:
                        continue

                    tool_schema = ToolSchema.from_mcp_tool(mcp_tool)
                    tools_dict[tool_schema.name] = tool_schema

                return tools_dict

        except Exception as e:
            llm_settings = get_llm_settings()
            if llm_settings.debug:
                print(f"[DEBUG] Error getting standardized tools: {e}")
            return {}

    @abstractmethod
    async def get_function_call_schemas(self, session_id: str, agent_profile: str = 'general') -> Any:
        """
        Get tool schemas formatted for the specific LLM provider.
        Uses get_standardized_tools() internally, then converts to provider format.

        Args:
            session_id: Session ID (required)
            agent_profile: Agent profile name ("coding", "lifestyle", "general", "pfc", "disabled")

        Returns:
            Tool schema list adapted for target LLM format (format varies by client)
        """
        pass

    async def _execute_mcp_tool(self, tool_name: str, tool_args: Dict[str, Any],
                               session_id: str) -> CallToolResult:
        """
        Unified method for executing MCP tool calls with mandatory session injection.
        Pure tool execution logic - confirmation should be handled by caller.

        Args:
            tool_name: Tool name
            tool_args: Tool arguments
            session_id: Session ID for dependency injection (required for all tools)

        Returns:
            CallToolResult: MCP tool execution result containing content, structuredContent, and isError fields
        """
        # All tools now require session ID for dependency injection


        mcp_client = self.get_mcp_client()
        async with mcp_client as mcp_async_client:
            # Session isolation is handled by FastMCP per request via _meta.client_id
            # Create params with _meta as dict (FastMCP will handle conversion)
            params = CallToolRequestParams(
                name=tool_name,
                arguments=tool_args,
                _meta={"client_id": session_id}  # type: ignore
            )
            call_req = ClientRequest(CallToolRequest(method="tools/call", params=params))
            return await mcp_async_client.session.send_request(call_req, CallToolResult)

    async def handle_multiple_function_calls(
        self,
        function_calls: List[dict],
        session_id: str,
        message_id: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Handle multiple function calls serially with intelligent cascade blocking.

        Executes tools one by one, stopping subsequent tools if:
        1. User rejects a tool → block all remaining tools
        2. PFC tool fails → block remaining PFC tools only (stateful dependency chain)
        3. Any tool fails when pfc_execute_script is in queue → block all remaining tools
           (pfc_execute_script depends on preparatory tools like file creation, data processing)

        This implements Claude Code's intelligent cascade pattern with contextual
        error messages to help LLM understand why each tool was blocked.

        Args:
            function_calls: List of function call dictionaries, each containing:
                - name: str - Tool name to execute
                - arguments: Dict[str, Any] - Tool arguments (optional)
                - id: str - Tool call ID for tracking (optional)
            session_id: Session ID for context-aware tools and dependency injection
            message_id: ID of the message containing these tool calls (for unique identification)

        Returns:
            List[Dict[str, Any]]: List of ToolResult dictionaries with structure:
                - status: Literal["success", "error"] - Operation outcome
                - message: str - User-facing summary
                - llm_content: Dict with parts structure
                - data: Optional[Dict[str, Any]] - Tool-specific data
                - user_rejected: Optional[bool] - True if directly rejected by user
                - cascade_blocked: Optional[bool] - True if blocked due to earlier failure

        Note:
            PFC tools are stateful (model state persists across commands).
            If one PFC tool fails, subsequent PFC tools will likely fail too
            (e.g., "ball generate" requires successful "model new").

            pfc_execute_script is special: it often depends on preparatory tools
            (file creation, data processing). If queue contains pfc_execute_script,
            any tool failure blocks all subsequent tools.

            Other tools (read, write, bash) are stateless and independent,
            so they continue executing even if PFC tools fail (unless pfc_execute_script
            is in the queue).
        """
        # Check if queue contains pfc_execute_script (triggers strict dependency mode)
        has_pfc_execute_script = any(
            call.get("name") == "pfc_execute_script"
            for call in function_calls
        )

        results = []
        user_rejected_tool = None  # Track which tool was rejected by user
        failed_pfc_tool = None  # Track which PFC tool failed
        failed_tool = None  # Track any failed tool (when pfc_execute_script present)

        for function_call in function_calls:
            tool_name = function_call.get("name", "unknown")
            is_pfc_tool = tool_name.startswith("pfc_")

            # Cascade blocking check 1: User rejection (blocks all remaining tools)
            if user_rejected_tool is not None:
                from backend.infrastructure.mcp.utils.tool_result import success_response

                cascade_message = f"The user doesn't want to take this action right now. Skipping {tool_name} due to previous rejection."
                cascade_result = success_response(
                    cascade_message,
                    llm_content={
                        "parts": [{"type": "text", "text": cascade_message}]
                    }
                )
                cascade_result["cascade_blocked"] = True
                results.append(cascade_result)

                llm_settings = get_llm_settings()
                if llm_settings.debug:
                    print(f"[BaseToolManager] Cascade blocking {tool_name} due to rejection of {user_rejected_tool}")
                continue

            # Cascade blocking check 2: PFC tool failure (blocks remaining PFC tools only)
            if failed_pfc_tool is not None and is_pfc_tool:
                from backend.infrastructure.mcp.utils.tool_result import error_response

                cascade_message = (
                    f"Cannot execute {tool_name}: Previous PFC tool failed ({failed_pfc_tool}). "
                    f"PFC tools are stateful - fix the error before executing dependent PFC operations."
                )
                cascade_result = error_response(
                    cascade_message,
                    llm_content={
                        "parts": [{"type": "text", "text": cascade_message}]
                    }
                )
                cascade_result["cascade_blocked"] = True
                results.append(cascade_result)

                llm_settings = get_llm_settings()
                if llm_settings.debug:
                    print(f"[BaseToolManager] Cascade blocking PFC tool {tool_name} due to failure of {failed_pfc_tool}")
                continue

            # Cascade blocking check 3: Any tool failure when pfc_execute_script in queue (blocks all)
            if has_pfc_execute_script and failed_tool is not None:
                from backend.infrastructure.mcp.utils.tool_result import error_response

                cascade_message = (
                    f"Cannot execute {tool_name}: Previous tool failed ({failed_tool}). "
                    f"Stopping all subsequent tools because pfc_execute_script in queue depends on preparatory tools. "
                    f"Fix the error before executing PFC script."
                )
                cascade_result = error_response(
                    cascade_message,
                    llm_content={
                        "parts": [{"type": "text", "text": cascade_message}]
                    }
                )
                cascade_result["cascade_blocked"] = True
                results.append(cascade_result)

                llm_settings = get_llm_settings()
                if llm_settings.debug:
                    print(f"[BaseToolManager] Cascade blocking {tool_name} due to failure of {failed_tool} (pfc_execute_script dependency mode)")
                continue

            # Execute tool normally
            result = await self.handle_function_call(function_call, session_id, message_id)
            results.append(result)

            # Check cascade triggers after execution
            # Trigger 1: User rejection (blocks all)
            if result.get('user_rejected', False):
                user_rejected_tool = tool_name
                llm_settings = get_llm_settings()
                if llm_settings.debug:
                    print(f"[BaseToolManager] User rejected {tool_name}, will cascade block remaining tools")

            # Trigger 2: PFC tool error (blocks PFC chain only)
            # Note: status="pending" (background tasks) is not considered failure
            if is_pfc_tool and result.get('status') == 'error':
                failed_pfc_tool = tool_name
                llm_settings = get_llm_settings()
                if llm_settings.debug:
                    print(f"[BaseToolManager] PFC tool {tool_name} failed, will cascade block remaining PFC tools")

            # Trigger 3: Any tool error when pfc_execute_script in queue (blocks all)
            # Note: status="pending" (background tasks) is not considered failure
            if has_pfc_execute_script and result.get('status') == 'error':
                failed_tool = tool_name
                llm_settings = get_llm_settings()
                if llm_settings.debug:
                    print(f"[BaseToolManager] Tool {tool_name} failed (pfc_execute_script dependency mode), will cascade block remaining tools")

        return results

    async def handle_function_call(self, function_call: dict, session_id: str, message_id: str = "") -> Dict[str, Any]:
        """
        Handle LLM-generated function_call requests.

        Args:
            function_call: Function call dictionary containing:
                - name: str - Tool name to execute
                - arguments: Dict[str, Any] - Tool arguments (optional, defaults to {})
                - id: str - Tool call ID for tracking (optional, defaults to "")
            session_id: Session ID for context-aware tools and dependency injection (required)
            message_id: ID of the message containing this tool call (for unique identification)

        Returns:
            Dict[str, Any]: ToolResult dictionary with structure:
                - status: Literal["success", "error"] - Operation outcome
                - message: str - User-facing summary
                - llm_content: Dict with parts structure
                - data: Optional[Dict[str, Any]] - Tool-specific data
                - user_rejected: Optional[bool] - True if user rejected the tool

        Raises:
            RuntimeError: When tool execution fails due to infrastructure errors
            ValueError: When required session_id is not provided
        """
        tool_name = function_call.get("name", "")
        tool_args = function_call.get("arguments", {})
        tool_id = function_call.get("id", "")

        # tool_id is used for:
        # 1. LLM context managers to properly format tool results in conversation history
        # 2. User confirmation matching (frontend uses it to match confirmation requests to tool blocks)

        try:
            # Step 0: Validate edit prerequisite (must read file before editing)
            if tool_name == "edit":
                file_path = tool_args.get("file_path", "")
                if file_path:
                    from backend.infrastructure.mcp.utils.tool_result import error_response

                    # Note: Path security check is handled by edit tool itself using dynamic workspace
                    # We only check the read policy here

                    # Policy check: Has the file been read in this session?
                    if not self._has_read_file(session_id, file_path):
                        error_message = (
                            f"File has not been read yet. Read it first before editing.\n\n"
                            f"You must use the Read tool to read {file_path} before editing it. "
                            f"This ensures you have the current file content and correct line numbers."
                        )

                        llm_settings = get_llm_settings()
                        if llm_settings.debug:
                            print(f"[BaseToolManager] Edit blocked: {file_path} not read yet in session {session_id}")

                        return error_response(
                            error_message,
                            llm_content={
                                "parts": [{
                                    "type": "text",
                                    "text": error_message
                                }]
                            }
                        )

            # Step 1: Handle user confirmation if required
            if self._requires_user_confirmation(tool_name, tool_args):
                rejection_result = await self._handle_user_confirmation(tool_name, tool_args, tool_id, session_id, message_id)
                if rejection_result is not None:
                    # User rejected - return rejection result (already in ToolResult format)
                    return rejection_result

            # Step 2: Execute the tool (user approved or no confirmation needed)
            call_tool_result = await self._execute_mcp_tool(tool_name, tool_args, session_id)
            tool_result = extract_tool_result_from_mcp(call_tool_result)

            # Step 2.5: Track successful read operations for edit prerequisite validation
            if tool_name == "read" and tool_result.get("status") == "success":
                file_path = tool_args.get("path", "")
                if file_path:
                    self._track_read_file(session_id, file_path)

            # Step 2.6: Track successful write operations as "read" for edit prerequisite
            # This allows edit tool to modify files that were just written
            if tool_name == "write" and tool_result.get("status") == "success":
                file_path = tool_args.get("file_path", "")
                if file_path:
                    self._track_read_file(session_id, file_path)

            # Step 3: Return tool result directly (already in standardized ToolResult format)
            return tool_result

        except ValidationError as e:
            # Pydantic validation error - format for LLM understanding
            llm_settings = get_llm_settings()
            if llm_settings.debug:
                print(f"[BaseToolManager] Validation error for tool {tool_name}: {e}")

            # Format validation errors for LLM
            error_details = []
            for error in e.errors():
                field = ".".join(str(loc) for loc in error["loc"])
                error_type = error["type"]
                message = error["msg"]

                # Format based on error type
                if error_type == "unexpected_keyword_argument":
                    error_details.append(
                        f"  • Parameter '{field}': Not defined in tool schema (unexpected argument)"
                    )
                elif error_type == "missing":
                    error_details.append(
                        f"  • Parameter '{field}': Required but not provided"
                    )
                elif error_type in ["type_error", "value_error"]:
                    error_details.append(
                        f"  • Parameter '{field}': {message}"
                    )
                else:
                    error_details.append(
                        f"  • Parameter '{field}': {message} (type: {error_type})"
                    )

            formatted_errors = "\n".join(error_details)
            error_message = (
                f"Tool '{tool_name}' parameter validation failed.\n\n"
                f"Validation errors:\n{formatted_errors}\n\n"
                f"Please check the tool schema and correct the parameters."
            )

            from backend.infrastructure.mcp.utils.tool_result import error_response
            return error_response(
                error_message,
                llm_content={
                    "parts": [{
                        "type": "text",
                        "text": error_message
                    }]
                }
            )

        except Exception as e:
            # System/infrastructure errors - re-raise for upper layer handling
            llm_settings = get_llm_settings()
            if llm_settings.debug:
                print(f"Error calling tool {tool_name}: {str(e)}")
            raise RuntimeError(f"Tool '{tool_name}' execution failed: {str(e)}") from e

    async def _handle_user_confirmation(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        tool_id: str,
        session_id: str,
        message_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Handle user confirmation for tool execution.

        Args:
            tool_name: Name of the tool requiring confirmation
            tool_args: Tool arguments
            tool_id: Tool call ID for matching with frontend
            session_id: Session ID for confirmation (required)
            message_id: ID of the message containing this tool call

        Returns:
            None if approved, rejection response dict if rejected
        """

        approved, user_message = await self._request_user_confirmation(
            tool_name, tool_args, tool_id, session_id, message_id
        )

        if not approved:
            # User rejected - format and return rejection response
            llm_settings = get_llm_settings()
            if llm_settings.debug:
                print(f"[BaseToolManager] User rejected {tool_name}")

            from backend.infrastructure.mcp.utils.tool_result import user_rejected_response
            rejection_result = user_rejected_response(
                user_message=user_message or f"User rejected {tool_name}"
            )

            # Add user_rejected flag for interruption detection
            rejection_result["user_rejected"] = True
            return rejection_result

        # User approved - return None to continue execution
        return None

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
            "bash": True,              # All bash commands require confirmation
            "edit": True,              # All file edits require confirmation
            "write": True,             # All file writes require confirmation
            "pfc_execute_script": True,  # PFC script execution requires confirmation
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

    async def _request_user_confirmation(self, tool_name: str, tool_args: Dict[str, Any], tool_id: str, session_id: str, message_id: str) -> tuple[bool, Optional[str]]:
        """
        Request user confirmation for tool execution.

        Args:
            tool_name: Name of the tool to execute
            tool_args: Arguments for the tool
            tool_id: Tool call ID for matching with frontend
            session_id: Session ID for the confirmation request
            message_id: ID of the message containing this tool call

        Returns:
            tuple[bool, Optional[str]]: (approved, user_message) - True if user approved,
                                      False if rejected or timed out. user_message contains
                                      optional feedback from user when rejecting
        """
        try:
            from backend.application.services.notifications.tool_confirmation_service import get_tool_confirmation_service

            llm_settings = get_llm_settings()
            confirmation_service = get_tool_confirmation_service()
            if not confirmation_service:
                if llm_settings.debug:
                    print(f"[BaseToolManager] Tool confirmation service not available, auto-rejecting {tool_name}")
                return (False, "Confirmation service not available")

            # Extract command from tool arguments based on tool type
            if tool_name == "bash":
                command = tool_args.get("command", "")
                description = tool_args.get("description", None)
                if not description:
                    description = f"Execute bash command: {command}"
            elif tool_name == "edit":
                file_path = tool_args.get("file_path", "unknown")
                command = f"Edit file: {file_path}"
                description = tool_args.get("description", None)
            elif tool_name == "write":
                file_path = tool_args.get("file_path", "unknown")
                command = f"Write file: {file_path}"
                description = tool_args.get("description", None)
            elif tool_name == "pfc_execute_script":
                script_path = tool_args.get("script_path", "unknown")
                run_in_background = tool_args.get("run_in_background", True)
                bg_info = " (background)" if run_in_background else " (foreground)"
                command = f"Execute PFC script{bg_info}: {script_path}"
                description = tool_args.get("description", None)
            else:
                command = f"{tool_name} operation"
                description = tool_args.get("description", None)

            if llm_settings.debug:
                print(f"[BaseToolManager] Requesting user confirmation for {tool_name} (tool_id={tool_id}): {command}")

            # Request confirmation (no timeout - wait indefinitely)
            approved, user_message = await confirmation_service.request_confirmation(
                session_id=session_id,
                message_id=message_id,
                tool_call_id=tool_id,
                tool_name=tool_name,
                command=command,
                description=description
            )

            if llm_settings.debug:
                if approved:
                    print(f"[BaseToolManager] User approved {tool_name} execution")
                else:
                    print(f"[BaseToolManager] User rejected {tool_name} execution")
                    if user_message:
                        print(f"[BaseToolManager] User message: {user_message}")

            return (approved, user_message)

        except Exception as e:
            llm_settings = get_llm_settings()
            if llm_settings.debug:
                print(f"[BaseToolManager] Error requesting user confirmation for {tool_name}: {e}")
            # On error, default to rejecting for security
            return (False, f"Error during confirmation: {str(e)}")