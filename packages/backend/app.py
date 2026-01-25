import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import Client

from backend.config.cors import get_cors_config, get_cors_middleware_kwargs
from backend.infrastructure.llm.base.factory import initialize_factory
from backend.infrastructure.mcp.mcp_server import mcp
from backend.infrastructure.mcp.tool_registry_loader import load_tool_registry
from backend.presentation.api import (
    content,
    file_search,
    llm_config,
    messages,
    pfc_console,
    sessions,
    shell,
    todos,
)
from backend.presentation.exceptions import register_exception_handlers
from backend.presentation.websocket.routes import register_websocket_routes
from backend.presentation.websocket.websocket_handler import create_websocket_handler
from backend.shared.utils.app_context import set_app
from backend.shared.utils.process_utils import kill_process_on_port
from backend.shared.utils.startup_banner import (
    log_error,
    log_warning,
    print_banner,
    print_shutdown_complete,
    print_shutdown_message,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle events."""
    try:
        # Create and store WebSocket handler in app state
        app.state.websocket_handler = create_websocket_handler()

        # Initialize LLM Factory
        llm_factory = initialize_factory()
        app.state.llm_factory = llm_factory

        # Initialize MCP server and client
        app.state.mcp = mcp
        mcp.app = app  # type: ignore # Set app reference for MCP tools to access FastAPI state
        mcp_client = Client(mcp)
        app.state.mcp_client = mcp_client

        # Populate internal tool registry without FastMCP
        await load_tool_registry()

        # Clean up any stale MCP server process before starting
        kill_process_on_port(9000)

        # Start MCP server in daemon thread (will be killed when main process exits)
        mcp_thread = threading.Thread(target=lambda: mcp.run(transport="sse", port=9000), daemon=True)
        mcp_thread.start()

        # Validate LLM configuration
        from backend.shared.utils.config_validator import validate_llm_configuration

        await validate_llm_configuration()

        # Get configuration for banner
        from backend.config.dev import DevelopmentConfig

        dev_config = DevelopmentConfig()
        cors_config = get_cors_config()
        environment = os.getenv("ENVIRONMENT", "development")

        # Print beautiful startup banner
        print_banner(
            environment=environment,
            host=dev_config.host,
            port=dev_config.port,
            cors_origins=cors_config.allow_origins,
            mcp_port=9000,
            version="0.1.0",
        )

        yield

    except Exception as e:
        log_error(f"Application initialization failed: {e}")
        raise
    finally:
        # Shutdown
        try:
            print_shutdown_message()

            # Cleanup background processes
            try:
                from backend.infrastructure.shell.background_process_manager import shutdown_all_processes

                shutdown_all_processes()
            except Exception as e:
                log_warning(f"Background process cleanup error: {e}")

            print_shutdown_complete()

        except Exception as e:
            log_error(f"Shutdown error: {e}")


app = FastAPI(lifespan=lifespan)

# Set global app instance for context access
set_app(app)

# CORS middleware configuration - environment-aware security settings
app.add_middleware(CORSMiddleware, **get_cors_middleware_kwargs())

app.include_router(sessions.router, prefix="/api")
app.include_router(messages.router, prefix="/api")
app.include_router(content.router, prefix="/api")
# app.include_router(chat.router, prefix="/api")  # Deprecated: Moved to WebSocket
app.include_router(file_search.router, prefix="/api")
app.include_router(todos.router)
app.include_router(shell.router)
app.include_router(pfc_console.router)
app.include_router(llm_config.router)

# Register WebSocket routes (cannot use include_router for WebSocket)
register_websocket_routes(app)

# Register global exception handlers
register_exception_handlers(app)
