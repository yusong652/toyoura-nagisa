from typing import Dict, Optional, Set
from datetime import datetime
import asyncio
from fastapi import WebSocket, WebSocketDisconnect
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """WebSocket连接状态枚举"""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class ConnectionInfo:
    """连接信息封装"""
    def __init__(self, websocket: WebSocket, session_id: str):
        self.websocket = websocket
        self.session_id = session_id
        self.state = ConnectionState.CONNECTING
        self.connected_at = datetime.now()
        self.last_heartbeat = datetime.now()
        self.last_activity = datetime.now()
        self.reconnect_count = 0
        self.error_count = 0
        self.pending_messages: list = []

    def update_activity(self):
        """更新最后活动时间"""
        self.last_activity = datetime.now()

    def update_heartbeat(self):
        """更新心跳时间"""
        self.last_heartbeat = datetime.now()
        self.update_activity()

    def is_stale(self, timeout_seconds: int = 60) -> bool:
        """检查连接是否过期"""
        return (datetime.now() - self.last_heartbeat).total_seconds() > timeout_seconds


class ConnectionManager:
    """增强版WebSocket连接管理器 - 支持心跳、重连、错误恢复"""
    
    def __init__(self):
        self.connections: Dict[str, ConnectionInfo] = {}
        self.heartbeat_interval = 60  # 心跳间隔（秒）- 匹配前端60秒
        self.heartbeat_timeout = 180  # 心跳超时（秒）- 3分钟，适配远程SSH高延迟
        self.max_reconnect_attempts = 10  # 增加重连次数适配远程环境
        self.reconnect_delay = 2  # 重连延迟（秒）- 匹配前端
        self._heartbeat_tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, session_id: str) -> bool:
        """建立WebSocket连接
        
        Args:
            websocket: WebSocket连接实例
            session_id: 会话ID
            
        Returns:
            bool: 连接是否成功
        """
        async with self._lock:
            try:
                # 如果已存在连接，先关闭旧连接
                if session_id in self.connections:
                    await self._close_connection(session_id)
                
                # 接受新连接
                await websocket.accept()
                
                # 创建连接信息
                conn_info = ConnectionInfo(websocket, session_id)
                conn_info.state = ConnectionState.CONNECTED
                self.connections[session_id] = conn_info
                
                # 启动心跳任务
                self._heartbeat_tasks[session_id] = asyncio.create_task(
                    self._heartbeat_loop(session_id)
                )
                
                # 发送连接成功消息
                await self._send_system_message(session_id, {
                    "type": "CONNECTION_ESTABLISHED",
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat()
                })
                
                # 发送任何待处理的消息
                await self._flush_pending_messages(session_id)
                
                logger.info(f"WebSocket connected for session: {session_id}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to establish connection for session {session_id}: {e}")
                if session_id in self.connections:
                    self.connections[session_id].state = ConnectionState.ERROR
                return False

    async def disconnect(self, session_id: str, code: int = 1000, reason: str = ""):
        """断开WebSocket连接
        
        Args:
            session_id: 会话ID
            code: 关闭代码
            reason: 关闭原因
        """
        async with self._lock:
            await self._close_connection(session_id, code, reason)

    async def _close_connection(self, session_id: str, code: int = 1000, reason: str = ""):
        """内部方法：关闭连接"""
        if session_id not in self.connections:
            return
        
        conn_info = self.connections[session_id]
        conn_info.state = ConnectionState.DISCONNECTING
        
        # 取消心跳任务
        if session_id in self._heartbeat_tasks:
            self._heartbeat_tasks[session_id].cancel()
            del self._heartbeat_tasks[session_id]
        
        # 关闭WebSocket
        try:
            await conn_info.websocket.close(code, reason)
        except Exception as e:
            logger.debug(f"Error closing websocket for session {session_id}: {e}")
        
        # 移除连接
        del self.connections[session_id]
        logger.info(f"WebSocket disconnected for session: {session_id}")

    async def send_json(self, session_id: str, data: dict) -> bool:
        """向指定会话发送JSON数据
        
        Args:
            session_id: 会话ID
            data: 要发送的数据
            
        Returns:
            bool: 发送是否成功
        """
        if session_id not in self.connections:
            logger.warning(f"No active WebSocket connection for session: {session_id}")
            return False
        
        conn_info = self.connections[session_id]
        
        # 如果连接不可用，添加到待处理队列（心跳消息除外）
        if conn_info.state != ConnectionState.CONNECTED:
            if data.get("type") != "HEARTBEAT":
                conn_info.pending_messages.append(data)
                logger.debug(f"Queued message for session {session_id} (state: {conn_info.state})")
            return False
        
        try:
            # 双重检查连接状态和WebSocket是否仍然打开
            if conn_info.websocket.client_state.name != "CONNECTED":
                logger.debug(f"WebSocket client state is {conn_info.websocket.client_state.name}, skipping send")
                return False
                
            await conn_info.websocket.send_json(data)
            conn_info.update_activity()
            logger.debug(f"Sent message to session {session_id}")
            return True
            
        except WebSocketDisconnect:
            logger.warning(f"WebSocket disconnected while sending to session {session_id}")
            await self.disconnect(session_id)
            return False
            
        except Exception as e:
            conn_info.error_count += 1
            logger.error(f"Failed to send message to session {session_id}: {e}")
            
            # 如果是ASGI WebSocket错误，立即断开连接
            if "websocket.send" in str(e) and "websocket.close" in str(e):
                logger.warning(f"WebSocket already closed for session {session_id}, cleaning up")
                await self.disconnect(session_id)
                return False
            
            # 如果错误次数过多，断开连接
            if conn_info.error_count >= 3:
                await self.disconnect(session_id)
            else:
                # 心跳消息失败不加入待处理队列
                if data.get("type") != "HEARTBEAT":
                    conn_info.pending_messages.append(data)
            
            return False

    async def broadcast(self, data: dict, exclude: Optional[Set[str]] = None):
        """广播消息给所有连接的客户端
        
        Args:
            data: 要广播的数据
            exclude: 要排除的会话ID集合
        """
        exclude = exclude or set()
        tasks = []
        
        for session_id in self.connections:
            if session_id not in exclude:
                tasks.append(self.send_json(session_id, data))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _heartbeat_loop(self, session_id: str):
        """心跳循环任务"""
        while session_id in self.connections:
            try:
                conn_info = self.connections[session_id]
                
                # 检查连接是否过期
                if conn_info.is_stale(self.heartbeat_timeout):
                    logger.warning(f"Connection {session_id} is stale, disconnecting")
                    await self.disconnect(session_id, 1001, "Heartbeat timeout")
                    break
                
                # 发送心跳
                await self._send_heartbeat(session_id)
                
                # 等待下一次心跳
                await asyncio.sleep(self.heartbeat_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop for session {session_id}: {e}")
                await asyncio.sleep(self.heartbeat_interval)

    async def _send_heartbeat(self, session_id: str):
        """发送心跳消息"""
        await self.send_json(session_id, {
            "type": "HEARTBEAT",
            "timestamp": datetime.now().isoformat()
        })

    async def handle_heartbeat_response(self, session_id: str):
        """处理心跳响应"""
        if session_id in self.connections:
            self.connections[session_id].update_heartbeat()

    async def _send_system_message(self, session_id: str, data: dict):
        """发送系统消息"""
        data["is_system"] = True
        await self.send_json(session_id, data)

    async def _flush_pending_messages(self, session_id: str):
        """发送待处理的消息"""
        if session_id not in self.connections:
            return
        
        conn_info = self.connections[session_id]
        pending = conn_info.pending_messages.copy()
        conn_info.pending_messages.clear()
        
        for message in pending:
            await self.send_json(session_id, message)

    def get_connection_info(self, session_id: str) -> Optional[ConnectionInfo]:
        """获取连接信息"""
        return self.connections.get(session_id)

    def get_active_sessions(self) -> list[str]:
        """获取所有活动会话ID"""
        return list(self.connections.keys())

    def get_connection_stats(self) -> dict:
        """获取连接统计信息"""
        total = len(self.connections)
        by_state = {}
        
        for conn_info in self.connections.values():
            state = conn_info.state.value
            by_state[state] = by_state.get(state, 0) + 1
        
        return {
            "total": total,
            "by_state": by_state,
            "timestamp": datetime.now().isoformat()
        }