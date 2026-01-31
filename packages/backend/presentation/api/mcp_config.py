"""
MCP Configuration API.

Provides endpoints for managing MCP server configuration per session.
Global defaults are defined in config/mcp_servers.yaml.
Session overrides are stored in session metadata.

Routes:
    GET /api/mcp-config - Get MCP configuration for a session
    POST /api/mcp-config - Update MCP server enabled state for a session
    GET /api/mcp-config/servers - Get available MCP servers (global view)
"""

from typing import List
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from backend.presentation.models.api_models import ApiResponse
from backend.presentation.exceptions import BadRequestError, InternalServerError
from backend.infrastructure.storage.session_manager import (
    get_session_mcp_config,
    update_session_mcp_server,
    get_session_metadata,
)
from backend.infrastructure.mcp.client import (
    get_mcp_client_manager,
    load_mcp_configs_from_yaml,
)

router = APIRouter(prefix="/api/mcp-config", tags=["mcp-config"])


# =====================
# Request/Response Models
# =====================
class MCPServerStatus(BaseModel):
    """Status of an MCP server for a session."""

    name: str = Field(..., description="Server identifier")
    description: str = Field(..., description="Server description")
    enabled: bool = Field(..., description="Whether enabled for this session")
    connected: bool = Field(..., description="Whether server is currently connected globally")
    tools: List[str] = Field(default_factory=list, description="Available tools from this server")


class MCPConfigData(BaseModel):
    """MCP configuration data for a session."""

    servers: List[MCPServerStatus] = Field(..., description="List of MCP servers with their status")


class MCPServerUpdateRequest(BaseModel):
    """Request to update an MCP server's enabled state."""

    server_name: str = Field(..., description="Server identifier to update")
    enabled: bool = Field(..., description="Whether to enable this server for the session")


# =====================
# API Endpoints
# =====================
@router.get("/", response_model=ApiResponse[MCPConfigData])
async def get_mcp_config(
    session_id: str = Query(..., description="Session ID to get configuration for"),
) -> ApiResponse[MCPConfigData]:
    """
    Get MCP configuration for a session.

    Returns the list of available MCP servers with their:
    - enabled state (session-specific, falls back to global default)
    - connection status (global)
    - available tools
    """
    try:
        # Verify session exists
        if not get_session_metadata(session_id):
            raise BadRequestError(message=f"Session not found: {session_id}")

        # Get global configs (includes all servers)
        global_configs = load_mcp_configs_from_yaml()

        # Get session-specific overrides
        session_mcp_config = get_session_mcp_config(session_id) or {"servers": {}}
        session_servers = session_mcp_config.get("servers", {})

        # Get connected server info
        mcp_manager = get_mcp_client_manager()
        connected_info = {info["name"]: info for info in mcp_manager.get_server_info()}

        # Build response
        servers = []
        for config in global_configs:
            # Determine enabled state: session override > global default
            if config.name in session_servers:
                enabled = session_servers[config.name].get("enabled", config.enabled)
            else:
                enabled = config.enabled

            # Get connection info
            conn_info = connected_info.get(config.name, {})
            connected = conn_info.get("connected", False)
            tools = conn_info.get("tools", [])

            servers.append(
                MCPServerStatus(
                    name=config.name,
                    description=config.description,
                    enabled=enabled,
                    connected=connected,
                    tools=tools,
                )
            )

        return ApiResponse(
            success=True,
            message="Retrieved MCP configuration for session",
            data=MCPConfigData(servers=servers),
        )

    except BadRequestError:
        raise
    except Exception as e:
        raise InternalServerError(message=f"Failed to get MCP configuration: {str(e)}")


@router.post("/", response_model=ApiResponse[MCPServerStatus])
async def update_mcp_server(
    request: MCPServerUpdateRequest,
    session_id: str = Query(..., description="Session ID to update"),
) -> ApiResponse[MCPServerStatus]:
    """
    Update an MCP server's enabled state for a session.

    This controls whether the server's tools are available during chat for this session.
    The global connection state is not affected - servers remain connected but their
    tools are filtered based on session settings.
    """
    try:
        # Verify session exists
        if not get_session_metadata(session_id):
            raise BadRequestError(message=f"Session not found: {session_id}")

        # Verify server exists
        global_configs = load_mcp_configs_from_yaml()
        server_config = None
        for config in global_configs:
            if config.name == request.server_name:
                server_config = config
                break

        if not server_config:
            raise BadRequestError(message=f"MCP server not found: {request.server_name}")

        # Update session config
        success = update_session_mcp_server(session_id, request.server_name, request.enabled)
        if not success:
            raise InternalServerError(message="Failed to update MCP configuration")

        # Get current connection status for response
        mcp_manager = get_mcp_client_manager()
        connected_info = {info["name"]: info for info in mcp_manager.get_server_info()}
        conn_info = connected_info.get(request.server_name, {})

        return ApiResponse(
            success=True,
            message=f"MCP server '{request.server_name}' {'enabled' if request.enabled else 'disabled'} for session",
            data=MCPServerStatus(
                name=request.server_name,
                description=server_config.description,
                enabled=request.enabled,
                connected=conn_info.get("connected", False),
                tools=conn_info.get("tools", []),
            ),
        )

    except BadRequestError:
        raise
    except Exception as e:
        raise InternalServerError(message=f"Failed to update MCP configuration: {str(e)}")


@router.get("/servers", response_model=ApiResponse[MCPConfigData])
async def get_available_servers() -> ApiResponse[MCPConfigData]:
    """
    Get list of available MCP servers (global view).

    Returns all configured MCP servers regardless of session.
    Useful for admin views or when no session context is available.
    """
    try:
        global_configs = load_mcp_configs_from_yaml()
        mcp_manager = get_mcp_client_manager()
        connected_info = {info["name"]: info for info in mcp_manager.get_server_info()}

        servers = []
        for config in global_configs:
            conn_info = connected_info.get(config.name, {})
            servers.append(
                MCPServerStatus(
                    name=config.name,
                    description=config.description,
                    enabled=config.enabled,  # Global default
                    connected=conn_info.get("connected", False),
                    tools=conn_info.get("tools", []),
                )
            )

        return ApiResponse(
            success=True,
            message=f"Retrieved {len(servers)} MCP servers",
            data=MCPConfigData(servers=servers),
        )

    except Exception as e:
        raise InternalServerError(message=f"Failed to get MCP servers: {str(e)}")
