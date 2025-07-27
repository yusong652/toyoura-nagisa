from typing import Dict
from fastapi import WebSocket


class ConnectionManager:
    """WebSocket连接管理器 - 负责管理客户端连接的生命周期"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        """建立WebSocket连接"""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        print(f"WebSocket connected for session: {session_id}")

    def disconnect(self, session_id: str):
        """断开WebSocket连接"""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            print(f"WebSocket disconnected for session: {session_id}")

    async def send_json(self, session_id: str, data: dict):
        """向指定会话发送JSON数据"""
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_json(data)
                print(f"Sent message to session {session_id}: {data}")
            except Exception as e:
                print(f"Failed to send message to session {session_id}: {e}")
                self.disconnect(session_id)
        else:
            print(f"No active WebSocket connection for session: {session_id}")