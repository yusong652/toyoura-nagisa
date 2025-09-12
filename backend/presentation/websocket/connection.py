from typing import Dict, Optional, Set
from datetime import datetime
import asyncio
from fastapi import WebSocket, WebSocketDisconnect
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """WebSocket connection state enumeration"""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class ConnectionInfo:
    """Connection information wrapper"""
    def __init__(self, websocket: WebSocket, session_id: str):
        self.websocket = websocket
        self.session_id = session_id
        self.state = ConnectionState.CONNECTING
        self.connected_at = datetime.now()
        self.last_heartbeat = datetime.now()
        self.last_activity = datetime.now()
        self.error_count = 0
        self.pending_messages: list = []

    def update_activity(self):
        """Update last activity time"""
        self.last_activity = datetime.now()

    def update_heartbeat(self):
        """Update heartbeat time"""
        self.last_heartbeat = datetime.now()
        self.update_activity()

    def is_stale(self, timeout_seconds: int = 60) -> bool:
        """Check if connection is stale"""
        return (datetime.now() - self.last_heartbeat).total_seconds() > timeout_seconds


class ConnectionManager:
    """Enhanced WebSocket connection manager - supports heartbeat, reconnection, and error recovery"""
    
    def __init__(self):
        self.connections: Dict[str, ConnectionInfo] = {}
        self.heartbeat_interval = 20   # Heartbeat interval (seconds) - WebSocket industry standard
        self.heartbeat_timeout = 35    # Heartbeat timeout (seconds) - buffer time to avoid network delay false alarms
        self._heartbeat_tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, session_id: str) -> bool:
        """Establish WebSocket connection
        
        Args:
            websocket: WebSocket connection instance
            session_id: Session ID
            
        Returns:
            bool: Whether connection was successful
        """
        async with self._lock:
            try:
                # Close existing connection if present
                if session_id in self.connections:
                    await self._close_connection(session_id)
                
                # Accept new connection
                await websocket.accept()
                
                # Create connection info
                conn_info = ConnectionInfo(websocket, session_id)
                conn_info.state = ConnectionState.CONNECTED
                self.connections[session_id] = conn_info
                
                # Start heartbeat task (using standard 20-second interval)
                self._heartbeat_tasks[session_id] = asyncio.create_task(
                    self._heartbeat_loop(session_id)
                )
                print(f"[WebSocket] Connection established with heartbeat (20s interval) for session {session_id}")
                
                # Send connection success message
                await self._send_system_message(session_id, {
                    "type": "CONNECTION_ESTABLISHED",
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat()
                })
                
                # Send any pending messages
                await self._flush_pending_messages(session_id)
                
                logger.info(f"WebSocket connected for session: {session_id}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to establish connection for session {session_id}: {e}")
                if session_id in self.connections:
                    self.connections[session_id].state = ConnectionState.ERROR
                return False

    async def disconnect(self, session_id: str, code: int = 1000, reason: str = ""):
        """Disconnect WebSocket connection
        
        Args:
            session_id: Session ID
            code: Close code
            reason: Close reason
        """
        async with self._lock:
            await self._close_connection(session_id, code, reason)

    async def _close_connection(self, session_id: str, code: int = 1000, reason: str = ""):
        """Internal method: close connection"""
        if session_id not in self.connections:
            return
        
        conn_info = self.connections[session_id]
        conn_info.state = ConnectionState.DISCONNECTING
        
        # Cancel heartbeat task
        if session_id in self._heartbeat_tasks:
            self._heartbeat_tasks[session_id].cancel()
            del self._heartbeat_tasks[session_id]
        
        # Close WebSocket
        try:
            await conn_info.websocket.close(code, reason)
        except Exception as e:
            logger.debug(f"Error closing websocket for session {session_id}: {e}")
        
        # Remove connection
        del self.connections[session_id]
        logger.info(f"WebSocket disconnected for session: {session_id}")

    async def send_json(self, session_id: str, data: dict) -> bool:
        """Send JSON data to specified session
        
        Args:
            session_id: Session ID
            data: Data to send
            
        Returns:
            bool: Whether send was successful
        """
        conn_info = self.connections.get(session_id)
        if not conn_info or conn_info.state != ConnectionState.CONNECTED:
            logger.debug(f"No active connection for session {session_id}")
            # Add non-heartbeat messages to pending queue
            if conn_info and data.get("type") != "HEARTBEAT":
                conn_info.pending_messages.append(data)
            return False
        
        try:
            # Check if WebSocket is still available
            if hasattr(conn_info.websocket, 'client_state') and conn_info.websocket.client_state.name != "CONNECTED":
                logger.debug(f"WebSocket client state is {conn_info.websocket.client_state.name}, skipping send")
                return False
                
            await conn_info.websocket.send_json(data)
            conn_info.update_activity()
            return True
            
        except WebSocketDisconnect:
            logger.warning(f"WebSocket disconnected while sending to session {session_id}")
            await self.disconnect(session_id)
            return False
            
        except Exception as e:
            conn_info.error_count += 1
            logger.error(f"Failed to send message to session {session_id}: {e}")
            
            # Disconnect if too many errors or WebSocket is closed
            if conn_info.error_count >= 3 or "websocket.send" in str(e):
                await self.disconnect(session_id)
            elif data.get("type") != "HEARTBEAT":
                # Add non-heartbeat messages to retry queue
                conn_info.pending_messages.append(data)
            
            return False


    async def _heartbeat_loop(self, session_id: str):
        """Heartbeat loop task - only for detecting connection state, does not actively disconnect"""
        # Initial wait to avoid immediate check on startup
        await asyncio.sleep(self.heartbeat_interval)
        
        while session_id in self.connections:
            try:
                conn_info = self.connections[session_id]
                
                # Check connection response status
                if conn_info.is_stale(self.heartbeat_timeout):
                    logger.warning(f"Connection {session_id} heartbeat timeout ({self.heartbeat_timeout}s)")
                
                # Send heartbeat
                if not await self._send_heartbeat(session_id):
                    logger.info(f"Heartbeat send failed for {session_id}, stopping heartbeat")
                    break
                
                # Wait for next heartbeat
                await asyncio.sleep(self.heartbeat_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop for session {session_id}: {e}")
                await asyncio.sleep(self.heartbeat_interval)

    async def _send_heartbeat(self, session_id: str) -> bool:
        """Send heartbeat message
        
        Returns:
            bool: Whether heartbeat send was successful
        """
        return await self.send_json(session_id, {
            "type": "HEARTBEAT",
            "timestamp": datetime.now().isoformat()
        })

    async def handle_heartbeat_response(self, session_id: str):
        """Handle heartbeat response"""
        if session_id in self.connections:
            self.connections[session_id].update_heartbeat()

    async def _send_system_message(self, session_id: str, data: dict):
        """Send system message"""
        data["is_system"] = True
        await self.send_json(session_id, data)

    async def _flush_pending_messages(self, session_id: str):
        """Send pending messages"""
        conn_info = self.connections.get(session_id)
        if not conn_info or not conn_info.pending_messages:
            return
        
        pending = conn_info.pending_messages.copy()
        conn_info.pending_messages.clear()
        
        for message in pending:
            await self.send_json(session_id, message)

    def get_active_sessions(self) -> list[str]:
        """Get all active session IDs"""
        return list(self.connections.keys())