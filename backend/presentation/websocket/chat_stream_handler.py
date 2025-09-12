"""
WebSocket-based chat streaming implementation.

This module provides WebSocket streaming capabilities to replace SSE-based
chat responses, offering better real-time performance and unified protocol management.
"""
import asyncio
import logging
from typing import AsyncGenerator, Optional, Dict, Any, List
from datetime import datetime

from backend.presentation.websocket.message_types import MessageType, create_message
from backend.presentation.websocket.connection import ConnectionManager
from backend.infrastructure.llm import LLMClientBase
from backend.infrastructure.tts.base import BaseTTS
from backend.domain.models.messages import BaseMessage
from backend.domain.models.message_factory import message_factory_no_thinking
from backend.infrastructure.storage.session_manager import load_history

logger = logging.getLogger(__name__)


class WebSocketChatStreamer:
    """
    WebSocket-based chat streaming service.
    
    Replaces SSE-based streaming with WebSocket for unified real-time communication,
    providing better error handling, connection management, and extensibility.
    """
    
    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager
    
    async def stream_chat_response(
        self,
        session_id: str,
        message: str,
        llm_client: LLMClientBase,
        tts_engine: Optional[BaseTTS] = None,
        user_id: Optional[str] = None,
        enable_memory: bool = True,
        agent_profile: str = "general",
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Stream chat response through WebSocket.
        
        Args:
            session_id: WebSocket session ID
            message: User message to process
            llm_client: LLM client instance
            tts_engine: Optional TTS engine for audio response
            user_id: User ID for memory operations
            enable_memory: Whether to enable memory injection
            agent_profile: Agent profile for tool selection
            context: Additional context data
            
        Returns:
            bool: Whether streaming was successful
        """
        try:
            # Send stream start notification
            await self._send_stream_start(session_id, message)
            
            # Load conversation history
            try:
                chat_history = load_history(session_id)
                logger.debug(f"Loaded {len(chat_history)} messages from history for session {session_id}")
            except Exception as e:
                logger.warning(f"Failed to load chat history for session {session_id}: {e}")
                chat_history = []
            
            # Add user message to history
            user_msg = message_factory_no_thinking(message, "user")
            chat_history.append(user_msg)
            
            # Generate streaming response
            await self._process_llm_stream(
                session_id=session_id,
                chat_history=chat_history,
                llm_client=llm_client,
                tts_engine=tts_engine,
                user_id=user_id,
                enable_memory=enable_memory,
                agent_profile=agent_profile,
                context=context
            )
            
            # Send stream end notification
            await self._send_stream_end(session_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error in WebSocket chat streaming for session {session_id}: {e}")
            await self._send_stream_error(session_id, str(e))
            return False
    
    async def _send_stream_start(self, session_id: str, user_message: str):
        """Send stream start notification"""
        start_msg = create_message(
            MessageType.CHAT_STREAM_START,
            session_id=session_id,
            data={
                "user_message": user_message,
                "timestamp": datetime.now().isoformat()
            }
        )
        await self.connection_manager.send_json(session_id, start_msg.model_dump())
        logger.debug(f"Sent stream start notification for session {session_id}")
    
    async def _send_stream_end(self, session_id: str):
        """Send stream end notification"""
        end_msg = create_message(
            MessageType.CHAT_STREAM_END,
            session_id=session_id,
            data={"timestamp": datetime.now().isoformat()}
        )
        await self.connection_manager.send_json(session_id, end_msg.model_dump())
        logger.debug(f"Sent stream end notification for session {session_id}")
    
    async def _send_stream_error(self, session_id: str, error_message: str):
        """Send stream error notification"""
        error_msg = create_message(
            MessageType.ERROR,
            session_id=session_id,
            error_code="CHAT_STREAM_ERROR",
            error_message=error_message,
            data={"timestamp": datetime.now().isoformat()}
        )
        await self.connection_manager.send_json(session_id, error_msg.model_dump())
        logger.error(f"Sent stream error for session {session_id}: {error_message}")
    
    async def _process_llm_stream(
        self,
        session_id: str,
        chat_history: List[BaseMessage],
        llm_client: LLMClientBase,
        tts_engine: Optional[BaseTTS],
        user_id: Optional[str],
        enable_memory: bool,
        agent_profile: str,
        context: Optional[Dict[str, Any]]
    ):
        """
        Process LLM streaming response and send chunks via WebSocket.
        
        This method integrates with the existing LLM streaming infrastructure
        while adapting the output for WebSocket delivery.
        """
        try:
            # TODO: Integrate with existing chat stream generator
            # For now, implement basic streaming functionality
            
            # Send status update
            await self._send_status_update(session_id, "processing", "Generating response...")
            
            # Mock streaming response for demonstration
            # This will be replaced with actual LLM integration
            demo_response = self._generate_demo_response()
            
            accumulated_content = ""
            for chunk in demo_response:
                # Send chunk via WebSocket
                chunk_msg = create_message(
                    MessageType.CHAT_STREAM_CHUNK,
                    session_id=session_id,
                    content=chunk,
                    chunk_type="text",
                    data={
                        "accumulated_length": len(accumulated_content + chunk),
                        "timestamp": datetime.now().isoformat()
                    }
                )
                
                await self.connection_manager.send_json(session_id, chunk_msg.model_dump())
                accumulated_content += chunk
                
                # Simulate streaming delay
                await asyncio.sleep(0.05)
            
            # Send final status
            await self._send_status_update(session_id, "completed", f"Response completed ({len(accumulated_content)} characters)")
            
        except Exception as e:
            logger.error(f"Error processing LLM stream for session {session_id}: {e}")
            raise
    
    async def _send_status_update(self, session_id: str, status: str, message: str):
        """Send status update message"""
        status_msg = create_message(
            MessageType.STATUS_UPDATE,
            session_id=session_id,
            status=status,
            data={
                "message": message,
                "timestamp": datetime.now().isoformat()
            }
        )
        await self.connection_manager.send_json(session_id, status_msg.model_dump())
    
    def _generate_demo_response(self) -> List[str]:
        """Generate demo streaming response (will be replaced with LLM integration)"""
        demo_text = """Hello! This is a demonstration of the new WebSocket-based chat streaming system. 
        
The key improvements include:

1. **Unified Protocol**: No more SSE/WebSocket switching - everything uses WebSocket
2. **Better Error Handling**: Real-time error notifications and recovery
3. **Type Safety**: Pydantic-based message validation
4. **Extensibility**: Easy to add new message types and handlers
5. **Performance**: Lower latency and better connection management

This streaming response is currently mocked, but the infrastructure is ready for LLM integration. 
The system supports all the features of the original SSE implementation while providing 
better real-time capabilities and unified message handling.

Next steps include integrating with the existing chat service and LLM providers for 
complete functionality replacement."""
        
        # Split into chunks for streaming simulation
        words = demo_text.split()
        chunks = []
        current_chunk = ""
        
        for word in words:
            if len(current_chunk + " " + word) > 50:  # Chunk size
                chunks.append(current_chunk + " ")
                current_chunk = word
            else:
                current_chunk += " " + word if current_chunk else word
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    async def send_tool_result_stream(self, session_id: str, tool_name: str, tool_result: Dict[str, Any]):
        """
        Stream tool execution results via WebSocket.
        
        Args:
            session_id: WebSocket session ID
            tool_name: Name of executed tool
            tool_result: Tool execution result data
        """
        try:
            # Send tool result as stream chunk
            tool_chunk = create_message(
                MessageType.CHAT_STREAM_CHUNK,
                session_id=session_id,
                content=f"Tool '{tool_name}' executed successfully",
                chunk_type="tool_result",
                data={
                    "tool_name": tool_name,
                    "result": tool_result,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            await self.connection_manager.send_json(session_id, tool_chunk.model_dump())
            logger.debug(f"Sent tool result stream for {tool_name} to session {session_id}")
            
        except Exception as e:
            logger.error(f"Error sending tool result stream to session {session_id}: {e}")
    
    async def send_memory_context_stream(self, session_id: str, memory_context: List[str]):
        """
        Stream memory context information via WebSocket.
        
        Args:
            session_id: WebSocket session ID
            memory_context: List of relevant memory context strings
        """
        try:
            memory_chunk = create_message(
                MessageType.CHAT_STREAM_CHUNK,
                session_id=session_id,
                content="Retrieved relevant context from memory",
                chunk_type="memory_context",
                data={
                    "context_count": len(memory_context),
                    "context": memory_context[:3],  # Send first 3 for preview
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            await self.connection_manager.send_json(session_id, memory_chunk.model_dump())
            logger.debug(f"Sent memory context stream to session {session_id}")
            
        except Exception as e:
            logger.error(f"Error sending memory context stream to session {session_id}: {e}")


class WebSocketChatIntegration:
    """
    Integration layer for WebSocket chat with existing infrastructure.
    
    This class provides compatibility with existing chat services while
    routing output through WebSocket instead of SSE.
    """
    
    def __init__(self, connection_manager: ConnectionManager):
        self.streamer = WebSocketChatStreamer(connection_manager)
        self.connection_manager = connection_manager
    
    async def handle_chat_request(
        self,
        session_id: str,
        message: str,
        llm_client: LLMClientBase,
        tts_engine: Optional[BaseTTS] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Handle chat request with WebSocket streaming.
        
        This method provides a drop-in replacement for SSE-based chat endpoints,
        maintaining API compatibility while using WebSocket for transport.
        
        Args:
            session_id: Session ID
            message: User message
            llm_client: LLM client instance
            tts_engine: Optional TTS engine
            **kwargs: Additional parameters
            
        Returns:
            Dict with request status and metadata
        """
        success = await self.streamer.stream_chat_response(
            session_id=session_id,
            message=message,
            llm_client=llm_client,
            tts_engine=tts_engine,
            **kwargs
        )
        
        return {
            "success": success,
            "transport": "websocket",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "message_length": len(message)
        }
    
    def is_session_connected(self, session_id: str) -> bool:
        """Check if session has active WebSocket connection"""
        return session_id in self.connection_manager.get_active_sessions()
    
    async def send_system_notification(self, session_id: str, notification: str):
        """Send system notification to session"""
        await self.streamer._send_status_update(session_id, "system", notification)