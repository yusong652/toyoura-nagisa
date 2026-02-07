"""
MCP Client for connecting to MCP servers.

This module provides a client for connecting to MCP servers
(like context7, blender-mcp, pfc-mcp, etc.) via stdio transport.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.infrastructure.llm.shared.utils.tool_schema import ToolSchema

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


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
    """

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None
    enabled: bool = True
    description: str = ""


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

        try:
            server_params = StdioServerParameters(
                command=self.config.command,
                args=self.config.args,
                env=self.config.env,
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
            logger.error(f"[{self.name}] Connection failed: {e}")
            await self.disconnect()
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
        await manager.add_server(config)


async def shutdown_mcp_clients() -> None:
    """Shutdown all MCP client connections."""
    global _mcp_client_manager
    if _mcp_client_manager:
        await _mcp_client_manager.shutdown()
        _mcp_client_manager = None


def load_mcp_configs_from_yaml(yaml_path: str | None = None) -> list[MCPServerConfig]:
    """
    Load MCP server configurations from YAML file.

    Args:
        yaml_path: Path to YAML config file. Defaults to config/mcp_servers.yaml

    Returns:
        List of MCPServerConfig objects
    """
    import os
    import re
    from pathlib import Path

    import yaml

    if yaml_path is None:
        # Default to project root config/mcp_servers.yaml
        project_root = Path(__file__).parent.parent.parent.parent.parent
        yaml_path = str(project_root / "config" / "mcp_servers.yaml")

    if not os.path.exists(yaml_path):
        logger.warning(f"MCP config file not found: {yaml_path}")
        return []

    with open(yaml_path, encoding="utf-8") as f:
        config_data = yaml.safe_load(f)

    if not config_data or "servers" not in config_data:
        return []

    def expand_env_vars(value: str) -> str:
        """Expand ${VAR_NAME} patterns with environment variables."""
        pattern = r"\$\{([^}]+)\}"

        def replace(match: re.Match) -> str:
            var_name = match.group(1)
            return os.getenv(var_name, "")

        return re.sub(pattern, replace, value)

    def expand_in_list(items: list) -> list:
        """Expand env vars in a list of strings."""
        return [expand_env_vars(item) if isinstance(item, str) else item for item in items]

    def expand_in_dict(d: dict) -> dict:
        """Expand env vars in a dict of strings."""
        return {k: expand_env_vars(v) if isinstance(v, str) else v for k, v in d.items()}

    configs = []
    for server in config_data["servers"]:
        # Skip if not a dict (could be a comment placeholder)
        if not isinstance(server, dict):
            continue

        # Expand environment variables in args
        args = server.get("args", [])
        if args:
            args = expand_in_list(args)
            # Filter out empty args (from missing env vars)
            args = [arg for arg in args if arg]

        # Expand environment variables in env dict
        env = server.get("env")
        if env:
            env = expand_in_dict(env)

        config = MCPServerConfig(
            name=server.get("name", ""),
            command=server.get("command", ""),
            args=args,
            env=env,
            enabled=server.get("enabled", True),
            description=server.get("description", ""),
        )
        configs.append(config)

    logger.info(f"Loaded {len(configs)} MCP server configs from {yaml_path}")
    return configs
