"""MCP client manager for multiple server connections."""

from __future__ import annotations

import logging
from typing import Any

from .mcp_client import MCPClient
from .models import MCPServerConfig, MCPTool

logger = logging.getLogger(__name__)


class MCPClientManager:
    """Manager for multiple MCP server connections."""

    def __init__(self):
        self._clients: dict[str, MCPClient] = {}
        self._tool_to_server: dict[str, str] = {}

    async def add_server(self, config: MCPServerConfig) -> bool:
        if config.name in self._clients:
            logger.warning(f"[{config.name}] Server already registered")
            return True

        client = MCPClient(config)
        success = await client.connect()

        if success:
            self._clients[config.name] = client
            for tool_name in client.get_tools():
                self._tool_to_server[tool_name] = config.name
            return True
        return False

    async def remove_server(self, name: str) -> None:
        if name in self._clients:
            client = self._clients[name]
            for tool_name in client.get_tools():
                self._tool_to_server.pop(tool_name, None)
            await client.disconnect()
            del self._clients[name]

    async def shutdown(self) -> None:
        for name in list(self._clients.keys()):
            await self.remove_server(name)

    def get_all_tools(self) -> dict[str, MCPTool]:
        tools: dict[str, MCPTool] = {}
        for client in self._clients.values():
            tools.update(client.get_tools())
        return tools

    def get_tool(self, name: str) -> MCPTool | None:
        server_name = self._tool_to_server.get(name)
        if server_name and server_name in self._clients:
            return self._clients[server_name].get_tool(name)
        return None

    def has_tool(self, name: str) -> bool:
        return name in self._tool_to_server

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
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
        return list(self._clients.keys())

    def get_server_info(self) -> list[dict[str, Any]]:
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


_mcp_client_manager: MCPClientManager | None = None


def get_mcp_client_manager() -> MCPClientManager:
    """Get the global MCP client manager instance."""
    global _mcp_client_manager
    if _mcp_client_manager is None:
        _mcp_client_manager = MCPClientManager()
    return _mcp_client_manager


async def initialize_mcp_clients(configs: list[MCPServerConfig]) -> None:
    """Initialize connections to MCP servers based on configuration."""
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
