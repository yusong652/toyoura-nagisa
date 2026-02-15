"""Single MCP server client."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

from .models import MCPServerConfig, MCPTool

logger = logging.getLogger(__name__)


class MCPClient:
    """Client for connecting to and interacting with one MCP server."""

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
        """Connect to the MCP server."""
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
                    cwd=self.config.cwd,
                    encoding="utf-8",
                    encoding_error_handler="replace",
                )

                self._stdio_context = stdio_client(server_params)
                self._read_stream, self._write_stream = await self._stdio_context.__aenter__()

                self._session_context = ClientSession(self._read_stream, self._write_stream)
                self._session = await self._session_context.__aenter__()

                await self._session.initialize()
                await self._load_tools()

                self._connected = True
                logger.info(f"[{self.name}] Connected successfully, {len(self._tools)} tools available")
                return True

            except Exception as e:
                last_error = e
                rendered_cmd = " ".join([self.config.command, *self.config.args]).strip()
                logger.warning(
                    f"[{self.name}] Connection attempt {attempt}/{max_attempts} failed: {e} "
                    f"(command='{rendered_cmd}', cwd='{self.config.cwd or ''}')"
                )
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
        return self._tools.copy()

    def get_tool(self, name: str) -> MCPTool | None:
        return self._tools.get(name)

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self._connected or not self._session:
            return {"status": "error", "message": f"Not connected to {self.name}"}

        if tool_name not in self._tools:
            return {"status": "error", "message": f"Tool '{tool_name}' not found on {self.name}"}

        try:
            result = await self._session.call_tool(tool_name, arguments)
            is_error = bool(getattr(result, "isError", False))

            content_parts = []
            for content in result.content:
                if isinstance(content, types.TextContent):
                    content_parts.append({"type": "text", "text": content.text})
                elif isinstance(content, types.ImageContent):
                    content_parts.append({"type": "image", "data": content.data, "mimeType": content.mimeType})
                elif isinstance(content, types.EmbeddedResource):
                    content_parts.append({"type": "resource", "uri": str(content.resource.uri)})

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
            return {"status": "error", "message": f"Tool execution failed: {e}"}
