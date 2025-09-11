"""
WebSocket Routes - Centralized WebSocket endpoint definitions.

This module provides WebSocket routes in a structure similar to API modules,
though WebSocket routes must be registered directly on the FastAPI app.
"""
from fastapi import FastAPI, WebSocket
from backend.presentation.websocket.connection import ConnectionManager
from backend.presentation.websocket.router import websocket_endpoint


def register_websocket_routes(app: FastAPI):
    """
    Register all WebSocket routes with the FastAPI application.
    
    This function centralizes WebSocket route registration to provide
    a clean separation similar to API router includes, even though
    WebSocket routes must be registered directly on the app.
    
    Args:
        app: FastAPI application instance to register routes on
        
    Note:
        Unlike REST API routes, WebSocket routes cannot use include_router()
        and must be registered directly on the FastAPI app instance.
    """
    
    @app.websocket("/ws/{session_id}")
    async def websocket_session_endpoint(websocket: WebSocket, session_id: str):
        """
        WebSocket endpoint for session-based real-time communication.
        
        Handles WebSocket connections for individual user sessions, providing
        real-time bidirectional communication for location requests, heartbeat
        monitoring, and other interactive features.
        
        Args:
            websocket: WebSocket connection instance
            session_id: Session UUID for connection context
            
        Note:
            Delegates actual message handling to the websocket router module
            while maintaining clean separation of concerns.
        """
        print(f"[WebSocket] Connection attempt for session: {session_id}")
        try:
            connection_manager: ConnectionManager = websocket.app.state.connection_manager
            await websocket_endpoint(websocket, session_id, connection_manager)
        except Exception as e:
            print(f"[WebSocket] Error in endpoint: {e}")
            raise


def get_websocket_info() -> dict:
    """
    Get information about registered WebSocket routes.
    
    Provides metadata about available WebSocket endpoints for
    documentation and debugging purposes.
    
    Returns:
        dict: WebSocket route information with structure:
            - routes: List of WebSocket route definitions
            - total_routes: int - Number of registered routes
            - supported_features: List of supported WebSocket features
    
    Example:
        info = get_websocket_info()
        print(f"WebSocket routes: {info['total_routes']}")
    """
    return {
        "routes": [
            {
                "path": "/ws/{session_id}",
                "description": "Session-based real-time communication",
                "parameters": ["session_id"],
                "supported_messages": ["HEARTBEAT_ACK", "LOCATION_RESPONSE"]
            }
        ],
        "total_routes": 1,
        "supported_features": [
            "heartbeat_monitoring",
            "location_requests", 
            "session_management",
            "connection_recovery"
        ]
    }