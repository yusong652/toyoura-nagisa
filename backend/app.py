from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from backend.infrastructure.llm.base.factory import initialize_factory
from backend.infrastructure.tts.tts_factory import get_tts_engine
from backend.infrastructure.mcp.smart_mcp_server import mcp
from fastmcp import Client
from backend.presentation.api import images
from backend.presentation.api import videos
from backend.presentation.api import agent_profiles  
from backend.presentation.api import sessions
from backend.presentation.api import messages
from backend.presentation.api import content
from backend.presentation.api import settings
from backend.presentation.api import chat
from backend.presentation.websocket.connection import ConnectionManager
from backend.presentation.websocket.routes import register_websocket_routes
from backend.presentation.exceptions import register_exception_handlers
import threading


# Load environment variables
load_dotenv()
# Initialize MCP client
mcp_client = Client(mcp)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle events."""
    print("[INIT] Starting application initialization...")
    try:
        # Initialize WebSocket connection manager
        connection_manager = ConnectionManager()
        app.state.connection_manager = connection_manager

        # Initialize TTS Engine
        tts_engine = get_tts_engine()
        await tts_engine.initialize()
        app.state.tts_engine = tts_engine
        print("[INIT] TTS Engine initialized successfully")
        
        # Initialize LLM Factory
        llm_factory = initialize_factory()
        llm_client = llm_factory.create_client()
        app.state.llm_client = llm_client
        app.state.llm_factory = llm_factory
        print(f"[INIT] LLM Factory initialized successfully")
        print(f"[INIT] LLM Client initialized: {type(llm_client).__name__}")
        
        # Initialize MCP server
        app.state.mcp = mcp
        mcp.app = app
        app.state.mcp_client = mcp_client
        
        mcp_thread = threading.Thread(target=lambda: mcp.run(transport="sse", port=9000), daemon=True)
        mcp_thread.start()
        print("[INIT] MCP Server started on SSE port 9000")
        
        # Validate LLM configuration
        from backend.shared.utils.config_validator import validate_llm_configuration
        await validate_llm_configuration()
        
        print("[INIT] All services initialized successfully")
        yield
        
    except Exception as e:
        print(f"[ERROR] Application initialization failed: {e}")
        raise
    finally:
        # Shutdown
        try:
            print("[SHUTDOWN] Starting graceful shutdown...")
            await app.state.tts_engine.shutdown()
            print("[SHUTDOWN] TTS Engine shutdown complete")
        except Exception as e:
            print(f"[ERROR] Shutdown error: {e}")

app = FastAPI(lifespan=lifespan)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(images.router)
app.include_router(videos.router)
app.include_router(agent_profiles.router)
app.include_router(sessions.router, prefix="/api")
app.include_router(messages.router, prefix="/api")
app.include_router(content.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(chat.router, prefix="/api")

# Register WebSocket routes (cannot use include_router for WebSocket)
register_websocket_routes(app)

# Register global exception handlers
register_exception_handlers(app)

