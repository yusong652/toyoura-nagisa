"""
WebSocket Router - Simple WebSocket endpoint handling.

This module provides a simple WebSocket router for handling real-time
communication needs like location requests and heartbeat messages.
"""
import json
import asyncio
from datetime import datetime
from typing import Dict, Any
from fastapi import WebSocket, WebSocketDisconnect
from backend.infrastructure.websocket.connection_manager import ConnectionManager
import logging

logger = logging.getLogger(__name__)

# Location response events storage - non-blocking event mechanism
# Format: {session_id: {"location_data": {...}, "timestamp": timestamp, "event": asyncio.Event}}
_location_response_events: Dict[str, Dict[str, Any]] = {}




async def websocket_endpoint(websocket: WebSocket, session_id: str, connection_manager: ConnectionManager):
    """
    Handle WebSocket connections for real-time communication.
    
    This function manages WebSocket connections and processes incoming messages
    including location responses and heartbeat acknowledgments.
    
    Args:
        websocket: WebSocket connection instance
        session_id: Session UUID for connection context
        connection_manager: WebSocket connection manager for lifecycle
        
    Note:
        Handles connection lifecycle, message routing, and error recovery.
        Maintains compatibility with existing location request system.
    """
    await connection_manager.connect(websocket, session_id)
    
    try:
        while True:
            # Receive and process messages from frontend
            data = await websocket.receive_text()
            await _process_websocket_message(data, session_id, connection_manager)
            
    except WebSocketDisconnect:
        await connection_manager.disconnect(session_id)
        logger.info(f"WebSocket disconnected for session: {session_id}")


async def _process_websocket_message(data: str, session_id: str, connection_manager: ConnectionManager):
    """
    Process incoming WebSocket messages.
    
    Routes different message types to appropriate handlers while maintaining
    simple processing logic for the current use cases.
    
    Args:
        data: Raw message data from WebSocket
        session_id: Session UUID for message context
        connection_manager: Connection manager for responses
    """
    try:
        message = json.loads(data)
        message_type = message.get("type")
        
        if message_type == "HEARTBEAT_ACK":
            await _handle_heartbeat_response(session_id, connection_manager)
            
        elif message_type == "LOCATION_RESPONSE":
            await _handle_location_response(session_id, message)
            
        else:
            logger.debug(f"Unknown message type '{message_type}' from session {session_id}")
            
    except json.JSONDecodeError:
        logger.debug(f"Received non-JSON message from {session_id}: {data}")
    except Exception as e:
        logger.error(f"Error processing WebSocket message for {session_id}: {e}")


async def _handle_heartbeat_response(session_id: str, connection_manager: ConnectionManager):
    """
    Handle heartbeat acknowledgment from client.
    
    Updates connection manager with heartbeat response to maintain
    connection health monitoring and prevent timeout disconnections.
    
    Args:
        session_id: Session UUID for heartbeat tracking
        connection_manager: Connection manager to update heartbeat status
    """
    await connection_manager.handle_heartbeat_response(session_id)
    logger.debug(f"Processed heartbeat response for session {session_id}")


async def _handle_location_response(session_id: str, message: Dict[str, Any]):
    """
    Handle location response from browser client.
    
    Processes location data from browser geolocation API and triggers
    waiting events for tools that requested location information.
    
    Args:
        session_id: Session UUID for location request correlation
        message: Location message with structure:
            - type: "LOCATION_RESPONSE"
            - location_data: Optional[Dict] - GPS coordinates if successful
            - error: Optional[str] - Error message if failed
            - timestamp: Optional[int] - Client timestamp
    
    Note:
        Coordinates with location request tools via shared event storage.
        Maintains backward compatibility with existing location system.
    """
    logger.debug(f"Received location response for session {session_id}: {message}")
    
    # Store location data and trigger event for waiting tools
    if session_id in _location_response_events:
        event_info = _location_response_events[session_id]
        
        # Store location data or error
        if "location_data" in message:
            event_info["location_data"] = message["location_data"]
            event_info["timestamp"] = message.get("timestamp", int(datetime.now().timestamp()))
            event_info["success"] = True
        else:
            event_info["error"] = message.get("error", "Unknown error")
            event_info["success"] = False
        
        # Trigger event to notify waiting tools
        event_info["event"].set()
        logger.debug(f"Location event triggered for session {session_id}")
    else:
        logger.debug(f"No location request pending for session {session_id}")