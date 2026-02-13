"""
MCP Client for connecting to MCP servers.

This module provides a client for connecting to MCP servers
(like context7, blender-mcp, pfc-mcp, etc.) via stdio transport.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.infrastructure.llm.shared.utils.tool_schema import ToolSchema

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)
ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")
NAGISA_CONFIG_DIR = ".nagisa"
MCP_CONFIG_FILENAME = "mcp_servers.json"


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server.

    Attributes:
        name: Unique identifier for the server
        command: Command to launch the server (e.g., "npx", "uvx", "python")
        args: List of arguments for the command
        env: Optional environment variables
        enabled: Default session-level setting for new sessions.
                 If True, tools from this server are available by default.
                 If False, users must enable via /mcps command.
                 Note: Server is always connected regardless of this flag.
        description: Human-readable description
        missing_env_vars: Missing env vars required by args/env templates
    """

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None
    enabled: bool = True
    description: str = ""
    missing_env_vars: list[str] = field(default_factory=list)


@dataclass
class MCPTool:
    """Representation of a tool from an MCP server."""

    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str

    # Alias for compatibility with ToolSchema.from_mcp_tool()
    @property
    def inputSchema(self) -> dict[str, Any]:
        """Alias for input_schema (MCP protocol uses camelCase)."""
        return self.input_schema

    def to_llm_schema(self) -> dict[str, Any]:
        """Convert to LLM function calling format."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.input_schema,
        }

    def to_tool_schema(self) -> "ToolSchema":
        """Convert to ToolSchema for LLM integration."""
        from backend.infrastructure.llm.shared.utils.tool_schema import ToolSchema

        return ToolSchema.from_mcp_tool(self)


class MCPClient:
    """
    Client for connecting to and interacting with MCP servers.

    Manages connections to MCP servers via stdio transport,
    allowing toyoura-nagisa to use tools from services like
    context7, blender-mcp, pfc-mcp, etc.
    """

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._session: ClientSession | None = None
        self._read_stream: Any = None
        self._write_stream: Any = None
        self._tools: dict[str, MCPTool] = {}
        self._connected = False
        self._stdio_context: Any = None
        self._session_context: Any = None

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> bool:
        """
        Connect to the MCP server.

        Returns:
            True if connection successful, False otherwise.
        """
        if self._connected:
            logger.warning(f"[{self.name}] Already connected")
            return True

        last_error: Exception | None = None
        max_attempts = 2

        for attempt in range(1, max_attempts + 1):
            try:
                server_params = StdioServerParameters(
                    command=self.config.command,
                    args=self.config.args,
                    env={**os.environ, **self.config.env} if self.config.env else None,
                    encoding="utf-8",
                    encoding_error_handler="replace",
                )

                # Create stdio client connection
                # Note: We need to manage the context manually for long-lived connections
                self._stdio_context = stdio_client(server_params)
                self._read_stream, self._write_stream = await self._stdio_context.__aenter__()

                # Create session
                self._session_context = ClientSession(self._read_stream, self._write_stream)
                self._session = await self._session_context.__aenter__()

                # Initialize the connection
                await self._session.initialize()

                # Load available tools
                await self._load_tools()

                self._connected = True
                logger.info(f"[{self.name}] Connected successfully, {len(self._tools)} tools available")
                return True

            except Exception as e:
                last_error = e
                logger.warning(f"[{self.name}] Connection attempt {attempt}/{max_attempts} failed: {e}")
                await self.disconnect()
                if attempt < max_attempts:
                    await asyncio.sleep(0.3)

        logger.error(f"[{self.name}] Connection failed: {last_error}")
        return False

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        try:
            if self._session_context:
                await self._session_context.__aexit__(None, None, None)
            if self._stdio_context:
                await self._stdio_context.__aexit__(None, None, None)
        except Exception as e:
            logger.warning(f"[{self.name}] Disconnect error: {e}")
        finally:
            self._session = None
            self._read_stream = None
            self._write_stream = None
            self._connected = False
            self._tools.clear()

    async def _load_tools(self) -> None:
        """Load available tools from the MCP server."""
        if not self._session:
            return

        try:
            result = await self._session.list_tools()
            self._tools.clear()

            for tool in result.tools:
                mcp_tool = MCPTool(
                    name=tool.name,
                    description=tool.description or "",
                    input_schema=tool.inputSchema if hasattr(tool, "inputSchema") else {},
                    server_name=self.name,
                )
                self._tools[tool.name] = mcp_tool

            logger.debug(f"[{self.name}] Loaded tools: {list(self._tools.keys())}")

        except Exception as e:
            logger.error(f"[{self.name}] Failed to load tools: {e}")

    def get_tools(self) -> dict[str, MCPTool]:
        """Get all available tools from this server."""
        return self._tools.copy()

    def get_tool(self, name: str) -> MCPTool | None:
        """Get a specific tool by name."""
        return self._tools.get(name)

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Call a tool on the MCP server.

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool

        Returns:
            Tool execution result as a dictionary
        """
        if not self._connected or not self._session:
            return {
                "status": "error",
                "message": f"Not connected to {self.name}",
            }

        if tool_name not in self._tools:
            return {
                "status": "error",
                "message": f"Tool '{tool_name}' not found on {self.name}",
            }

        try:
            result = await self._session.call_tool(tool_name, arguments)
            is_error = bool(getattr(result, "isError", False))

            # Extract content from result
            content_parts = []
            for content in result.content:
                if isinstance(content, types.TextContent):
                    content_parts.append({"type": "text", "text": content.text})
                elif isinstance(content, types.ImageContent):
                    content_parts.append(
                        {
                            "type": "image",
                            "data": content.data,
                            "mimeType": content.mimeType,
                        }
                    )
                elif isinstance(content, types.EmbeddedResource):
                    content_parts.append(
                        {
                            "type": "resource",
                            "uri": str(content.resource.uri),
                        }
                    )

            error_message = None
            if is_error:
                for part in content_parts:
                    if part.get("type") == "text":
                        error_message = part.get("text", "")
                        if error_message:
                            break
                if not error_message:
                    error_message = f"MCP tool '{tool_name}' returned error"

            return {
                "status": "error" if is_error else "success",
                "server": self.name,
                "tool": tool_name,
                "message": error_message,
                "content": content_parts,
                "structuredContent": result.structuredContent if hasattr(result, "structuredContent") else None,
            }

        except Exception as e:
            logger.error(f"[{self.name}] Tool call failed: {tool_name} - {e}")
            return {
                "status": "error",
                "message": f"Tool execution failed: {e}",
            }


class MCPClientManager:
    """
    Manager for multiple MCP server connections.

    Handles lifecycle management, tool aggregation, and routing
    for all configured MCP servers.
    """

    def __init__(self):
        self._clients: dict[str, MCPClient] = {}
        self._tool_to_server: dict[str, str] = {}  # tool_name -> server_name

    async def add_server(self, config: MCPServerConfig) -> bool:
        """
        Add and connect to an MCP server.

        All configured servers are connected regardless of 'enabled' flag.
        The 'enabled' flag only controls the default session-level setting
        (whether tools from this server are available by default for new sessions).

        Args:
            config: Server configuration

        Returns:
            True if server added and connected successfully
        """
        if config.name in self._clients:
            logger.warning(f"[{config.name}] Server already registered")
            return True

        client = MCPClient(config)
        success = await client.connect()

        if success:
            self._clients[config.name] = client
            # Register tools for routing
            for tool_name in client.get_tools():
                self._tool_to_server[tool_name] = config.name
            return True

        return False

    async def remove_server(self, name: str) -> None:
        """Remove and disconnect from an MCP server."""
        if name in self._clients:
            client = self._clients[name]
            # Remove tool mappings
            for tool_name in client.get_tools():
                self._tool_to_server.pop(tool_name, None)
            await client.disconnect()
            del self._clients[name]

    async def shutdown(self) -> None:
        """Disconnect from all MCP servers."""
        for name in list(self._clients.keys()):
            await self.remove_server(name)

    def get_all_tools(self) -> dict[str, MCPTool]:
        """Get all tools from all connected servers."""
        tools = {}
        for client in self._clients.values():
            tools.update(client.get_tools())
        return tools

    def get_tool(self, name: str) -> MCPTool | None:
        """Get a specific tool by name."""
        server_name = self._tool_to_server.get(name)
        if server_name and server_name in self._clients:
            return self._clients[server_name].get_tool(name)
        return None

    def has_tool(self, name: str) -> bool:
        """Check if a tool exists on any connected server."""
        return name in self._tool_to_server

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Call a tool, routing to the appropriate server.

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool

        Returns:
            Tool execution result
        """
        server_name = self._tool_to_server.get(tool_name)
        if not server_name:
            return {
                "status": "error",
                "message": f"Tool '{tool_name}' not found on any connected server",
            }

        client = self._clients.get(server_name)
        if not client:
            return {
                "status": "error",
                "message": f"Server '{server_name}' not connected",
            }

        return await client.call_tool(tool_name, arguments)

    def get_connected_servers(self) -> list[str]:
        """Get list of connected server names."""
        return list(self._clients.keys())

    def get_server_info(self) -> list[dict[str, Any]]:
        """Get information about all connected servers."""
        info = []
        for name, client in self._clients.items():
            info.append(
                {
                    "name": name,
                    "connected": client.is_connected,
                    "tools": list(client.get_tools().keys()),
                }
            )
        return info


# Global manager instance
_mcp_client_manager: MCPClientManager | None = None


def get_mcp_client_manager() -> MCPClientManager:
    """Get the global MCP client manager instance."""
    global _mcp_client_manager
    if _mcp_client_manager is None:
        _mcp_client_manager = MCPClientManager()
    return _mcp_client_manager


async def initialize_mcp_clients(configs: list[MCPServerConfig]) -> None:
    """
    Initialize connections to MCP servers based on configuration.

    Args:
        configs: List of server configurations
    """
    manager = get_mcp_client_manager()
    for config in configs:
        if config.missing_env_vars:
            missing_vars = ", ".join(config.missing_env_vars)
            logger.warning(
                f"[{config.name}] Skipping MCP server initialization due to missing environment variables: {missing_vars}"
            )
            continue
        await manager.add_server(config)


async def shutdown_mcp_clients() -> None:
    """Shutdown all MCP client connections."""
    global _mcp_client_manager
    if _mcp_client_manager:
        await _mcp_client_manager.shutdown()
        _mcp_client_manager = None


def _find_missing_env_vars(value: str) -> set[str]:
    """Find env vars referenced by ${VAR_NAME} that are unset or empty."""
    missing_vars: set[str] = set()
    for match in ENV_VAR_PATTERN.finditer(value):
        var_name = match.group(1)
        if not os.getenv(var_name):
            missing_vars.add(var_name)
    return missing_vars


def _expand_env_vars(value: str) -> str:
    """Expand ${VAR_NAME} patterns with environment variables."""

    def replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        return os.getenv(var_name, "")

    return ENV_VAR_PATTERN.sub(replace, value)


def _parse_args(args_raw: Any) -> tuple[list[str], set[str]]:
    """Parse and expand args from raw config value."""
    args_list = args_raw if isinstance(args_raw, list) else []
    missing_env_vars: set[str] = set()

    for arg in args_list:
        if isinstance(arg, str):
            missing_env_vars.update(_find_missing_env_vars(arg))

    args = [_expand_env_vars(arg) for arg in args_list if isinstance(arg, str)]
    args = [arg for arg in args if arg]
    return args, missing_env_vars


def _parse_env(env_raw: Any) -> tuple[dict[str, str] | None, set[str]]:
    """Parse and expand env map from raw config value."""
    env_dict = env_raw if isinstance(env_raw, dict) else {}
    missing_env_vars: set[str] = set()
    env: dict[str, str] = {}

    for key, value in env_dict.items():
        if isinstance(value, str):
            missing_env_vars.update(_find_missing_env_vars(value))
            rendered = _expand_env_vars(value)
            if rendered:
                env[key] = rendered

    return (env or None), missing_env_vars


def _parse_mcp_server(server_name: str, server_data: dict[str, Any]) -> MCPServerConfig:
    """Parse one MCP server entry from JSON mapping format."""
    args, missing_in_args = _parse_args(server_data.get("args", []))
    env, missing_in_env = _parse_env(server_data.get("env", {}))
    missing_env_vars = sorted(missing_in_args | missing_in_env)

    return MCPServerConfig(
        name=server_name,
        command=server_data.get("command", ""),
        args=args,
        env=env,
        enabled=server_data.get("enabled", True),
        description=server_data.get("description", ""),
        missing_env_vars=missing_env_vars,
    )


def _load_mcp_servers_mapping_from_file(config_file_path: Path) -> dict[str, dict[str, Any]]:
    """Load and validate mcpServers mapping from a JSON config file."""
    with config_file_path.open(encoding="utf-8") as f:
        config_data = json.load(f)

    if not isinstance(config_data, dict):
        logger.warning(f"Invalid MCP config format in {config_file_path}: root must be an object")
        return {}

    mcp_servers = config_data.get("mcpServers", {})
    if not isinstance(mcp_servers, dict):
        logger.warning(f"Invalid MCP config format in {config_file_path}: 'mcpServers' must be an object")
        return {}

    normalized: dict[str, dict[str, Any]] = {}
    for server_name, server_data in mcp_servers.items():
        if isinstance(server_name, str) and isinstance(server_data, dict):
            normalized[server_name] = server_data
    return normalized


def _build_default_mcp_config_paths(workspace_root: str | None = None) -> list[Path]:
    """Build MCP config lookup paths in low -> high priority order."""
    project_root = Path(__file__).parent.parent.parent.parent.parent
    builtin_config = project_root / "config" / MCP_CONFIG_FILENAME
    user_config = Path.home() / NAGISA_CONFIG_DIR / MCP_CONFIG_FILENAME

    config_paths = [builtin_config, user_config]

    if workspace_root:
        workspace_path = Path(workspace_root).expanduser()
        if not workspace_path.is_absolute():
            workspace_path = (Path.cwd() / workspace_path).resolve()
        else:
            workspace_path = workspace_path.resolve()
        workspace_config = workspace_path / NAGISA_CONFIG_DIR / MCP_CONFIG_FILENAME
        config_paths.append(workspace_config)

    return config_paths


def load_mcp_configs(
    config_path: str | None = None,
    workspace_root: str | None = None,
) -> list[MCPServerConfig]:
    """
    Load MCP server configurations from JSON config file.

    Supported schema:

    {
      "mcpServers": {
        "server-name": {
          "type": "stdio",
          "command": "uvx",
          "args": ["package-name"],
          "env": {}
        }
      }
    }

    Config priority (low -> high):
        1. Builtin: project/config/mcp_servers.json
        2. User: ~/.nagisa/mcp_servers.json
        3. Workspace: <workspace>/.nagisa/mcp_servers.json

    Args:
        config_path: Optional explicit config path. If provided, only this file is loaded.
        workspace_root: Optional workspace root used to resolve workspace-level config.

    Returns:
        List of MCPServerConfig objects
    """
    config_paths = [Path(config_path)] if config_path else _build_default_mcp_config_paths(workspace_root)

    merged_servers: dict[str, dict[str, Any]] = {}
    loaded_paths: list[Path] = []

    for path in config_paths:
        if not path.exists():
            continue
        try:
            server_mapping = _load_mcp_servers_mapping_from_file(path)
        except Exception as e:
            logger.warning(f"Failed to load MCP config file {path}: {e}")
            continue

        for server_name, server_data in server_mapping.items():
            if server_name in merged_servers:
                logger.info(f"MCP server '{server_name}' overridden by config: {path}")
            merged_servers[server_name] = server_data

        loaded_paths.append(path)

    if not loaded_paths:
        logger.warning("No MCP config files found (checked builtin/user/workspace paths)")
        return []

    configs: list[MCPServerConfig] = []
    for server_name, server_data in merged_servers.items():
        if not isinstance(server_data, dict):
            continue
        if server_data.get("type", "stdio") != "stdio":
            logger.warning(f"[{server_name}] Unsupported MCP transport type: {server_data.get('type')}")
            continue
        configs.append(_parse_mcp_server(server_name, server_data))

    loaded_path_text = ", ".join(str(path) for path in loaded_paths)
    logger.info(f"Loaded {len(configs)} MCP server configs from: {loaded_path_text}")
    return configs


async def ensure_mcp_clients_for_workspace(workspace_root: str | None) -> None:
    """Ensure MCP clients are connected for merged config of a workspace."""
    manager = get_mcp_client_manager()
    loaded_configs = load_mcp_configs(workspace_root=workspace_root)
    connected = set(manager.get_connected_servers())

    for config in loaded_configs:
        if config.name in connected:
            continue
        if config.missing_env_vars:
            missing_vars = ", ".join(config.missing_env_vars)
            logger.warning(
                f"[{config.name}] Skipping MCP server initialization due to missing environment variables: {missing_vars}"
            )
            continue

        success = await manager.add_server(config)
        if success:
            connected.add(config.name)
