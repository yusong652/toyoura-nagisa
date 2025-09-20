# WebSocket Architecture v2.0

## Overview

This document describes the new unified WebSocket architecture for aiNagisa, which replaces the previous mixed SSE/WebSocket approach with a single, extensible real-time communication system.

## Architecture Components

### Core Components

```
backend/presentation/websocket/
├── websocket_handler.py      # Unified connection lifecycle management
├── message_types.py          # Message type definitions and schemas
├── message_handler.py        # Extensible message processing system
├── routes.py                 # Route registration (simplified)
└── README.md                # This documentation

backend/infrastructure/websocket/
├── connection_manager.py     # Low-level connection management
└── services/                # WebSocket notification services
```

### Key Improvements

1. **Unified Protocol**: Single WebSocket connection for all real-time features
2. **Type Safety**: Pydantic-based message validation and schemas
3. **Extensible Handlers**: Plugin-style message handlers for easy feature addition
4. **Better Error Handling**: Real-time error notifications and recovery
5. **Simplified Architecture**: Reduced from 3-layer to 2-layer routing
6. **Performance Optimized**: Heartbeat timing fixes and reduced overhead

## Message Types

### Supported Message Types

| Type | Direction | Description | Handler |
|------|-----------|-------------|---------|
| `HEARTBEAT` | Server→Client | Connection keep-alive | HeartbeatHandler |
| `HEARTBEAT_ACK` | Client→Server | Heartbeat acknowledgment | HeartbeatHandler |
| `LOCATION_REQUEST` | Server→Client | Request user location | LocationHandler |
| `LOCATION_RESPONSE` | Client→Server | Location data response | LocationHandler |
| `CHAT_MESSAGE` | Client→Server | User chat message | ChatHandler |
| `CHAT_STREAM_START` | Server→Client | Start of streaming response | ChatHandler |
| `CHAT_STREAM_CHUNK` | Server→Client | Streaming content chunk | ChatHandler |
| `CHAT_STREAM_END` | Server→Client | End of streaming response | ChatHandler |
| `ERROR` | Server→Client | Error notification | All handlers |
| `STATUS_UPDATE` | Server→Client | Status information | All handlers |

### Message Schema Example

```python
# Chat message request
{
    "type": "CHAT_MESSAGE",
    "session_id": "uuid-string",
    "timestamp": "2024-01-01T12:00:00Z",
    "message": "Hello, AI!",
    "context": {"user_preferences": {...}},
    "stream_response": true
}

# Chat stream chunk
{
    "type": "CHAT_STREAM_CHUNK",
    "session_id": "uuid-string",
    "timestamp": "2024-01-01T12:00:01Z",
    "content": "Hello! How can I help you today?",
    "chunk_type": "text",
    "is_final": false
}
```

## Usage Examples

### Basic WebSocket Connection

```javascript
// Frontend connection
const ws = new WebSocket(`ws://localhost:8000/ws/${sessionId}`);

ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    
    switch (message.type) {
        case 'CHAT_STREAM_CHUNK':
            appendToChatDisplay(message.content);
            break;
        case 'HEARTBEAT':
            ws.send(JSON.stringify({
                type: 'HEARTBEAT_ACK',
                timestamp: Date.now()
            }));
            break;
        case 'ERROR':
            handleError(message.error_message);
            break;
    }
};
```

### Backend Message Sending

```python
# Direct connection manager access (infrastructure layer)
from backend.infrastructure.websocket.connection_manager import get_connection_manager
from backend.presentation.websocket.message_types import create_message, MessageType

connection_manager = get_connection_manager()

# Send message to specific session
message = create_message(
    MessageType.CHAT_STREAM_CHUNK,
    session_id=session_id,
    content="Hello from server!",
    chunk_type="text"
)
await connection_manager.send_json(session_id, message.model_dump())

# For broadcasting, iterate through active sessions
for active_session in connection_manager.get_active_sessions():
    status_message = create_message(
        MessageType.STATUS_UPDATE,
        session_id=active_session,
        status="system_maintenance",
        data={"message": "System will restart in 5 minutes"}
    )
    await connection_manager.send_json(active_session, status_message.model_dump())
```

### Adding New Message Handlers

```python
from backend.presentation.websocket.message_handler import MessageHandler, BaseWebSocketMessage

class CustomFeatureHandler(MessageHandler):
    """Handle custom feature messages"""
    
    async def handle(self, session_id: str, message: BaseWebSocketMessage) -> Optional[BaseWebSocketMessage]:
        if message.type == MessageType.CUSTOM_FEATURE_REQUEST:
            # Process custom feature
            result = await self.process_custom_feature(message)
            
            # Send response
            response = create_message(
                MessageType.CUSTOM_FEATURE_RESPONSE,
                session_id=session_id,
                data=result
            )
            return response
        
        return None
    
    async def process_custom_feature(self, message):
        # Custom feature logic
        return {"status": "processed", "data": "custom_result"}

# Register handler in WebSocketMessageProcessor.__init__
self.handlers[MessageType.CUSTOM_FEATURE_REQUEST] = CustomFeatureHandler(connection_manager)
```

## Migration Guide

### From SSE to WebSocket

#### Before (SSE-based chat)
```python
# Old SSE endpoint
@router.post("/chat/stream/{session_id}")
async def chat_stream(session_id: str, request: ChatRequest):
    return StreamingResponse(
        generate_chat_stream(...),
        media_type="text/plain"
    )
```

#### After (WebSocket-based chat)
```python
# New WebSocket message handling
class ChatHandler(MessageHandler):
    async def handle(self, session_id: str, message: BaseWebSocketMessage):
        if message.type == MessageType.CHAT_MESSAGE:
            # Start streaming response
            streamer = WebSocketChatStreamer(self.connection_manager)
            await streamer.stream_chat_response(session_id, message.message, ...)
```

### Frontend Migration

#### Before (SSE + WebSocket)
```javascript
// Chat via SSE
const eventSource = new EventSource(`/api/chat/stream/${sessionId}`);
eventSource.onmessage = (event) => {
    displayChatChunk(event.data);
};

// Location via WebSocket
const ws = new WebSocket(`ws://localhost:8000/ws/${sessionId}`);
ws.onmessage = (event) => {
    if (data.type === 'LOCATION_REQUEST') {
        // Handle location
    }
};
```

#### After (Unified WebSocket)
```javascript
// Everything via WebSocket
const ws = new WebSocket(`ws://localhost:8000/ws/${sessionId}`);

ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    
    switch (message.type) {
        case 'CHAT_STREAM_CHUNK':
            displayChatChunk(message.content);
            break;
        case 'LOCATION_REQUEST':
            handleLocationRequest(message);
            break;
        case 'HEARTBEAT':
            ws.send(JSON.stringify({type: 'HEARTBEAT_ACK'}));
            break;
    }
};

// Send chat message
ws.send(JSON.stringify({
    type: 'CHAT_MESSAGE',
    message: 'Hello!',
    stream_response: true
}));
```

## Configuration

### Heartbeat Settings
```python
# In connection.py
self.heartbeat_interval = 20   # Send heartbeat every 20 seconds
self.heartbeat_timeout = 35    # Timeout after 35 seconds (includes buffer)
```

### Message Validation
All messages are validated using Pydantic schemas. Invalid messages automatically receive error responses.

### Error Handling
The system provides comprehensive error handling:
- Parse errors for malformed JSON
- Validation errors for invalid message schemas
- Handler errors for processing failures
- Connection errors for network issues

## Performance Considerations

### Optimizations
- **Reduced Heartbeat False Alarms**: Fixed timing issues with 15-second buffer
- **Efficient Message Routing**: Direct handler mapping without nested iterations
- **Connection Pooling**: Single connection per session for all features
- **Type Validation**: Early validation prevents processing invalid messages

### Monitoring
```python
# Get connection statistics
from backend.infrastructure.websocket.connection_manager import get_connection_manager

connection_manager = get_connection_manager()
if connection_manager:
    active_sessions = connection_manager.get_active_sessions()
    print(f"Active connections: {len(active_sessions)}")

# Access message processor through WebSocket handler instance
# Note: This requires access to the FastAPI app instance
from fastapi import FastAPI
app = FastAPI()  # Your app instance
websocket_handler = getattr(app.state, 'websocket_handler', None)
if websocket_handler:
    processor = websocket_handler.get_message_processor()
    print(f"Supported message types: {len(processor.handlers.keys())}")
```

## Testing

### Unit Testing
```python
import pytest
from backend.presentation.websocket.message_types import parse_message, MessageType

def test_message_parsing():
    raw_message = '{"type": "CHAT_MESSAGE", "message": "Hello"}'
    parsed = parse_message(raw_message)
    assert parsed.type == MessageType.CHAT_MESSAGE
    assert parsed.message == "Hello"
```

### Integration Testing
```python
async def test_websocket_chat_flow():
    handler = WebSocketHandler()
    
    # Simulate connection
    await handler.handle_connection(mock_websocket, "test_session")
    
    # Send chat message
    await handler.send_to_session("test_session", {
        "type": "CHAT_MESSAGE",
        "message": "Test message"
    })
    
    # Verify response
    assert mock_websocket.sent_messages[-1]["type"] == "CHAT_STREAM_START"
```

## Troubleshooting

### Common Issues

1. **Heartbeat Warnings**: Ensure frontend sends `HEARTBEAT_ACK` responses
2. **Message Validation Errors**: Check message schema against `message_types.py`
3. **Handler Not Found**: Verify message type is registered in `WebSocketMessageProcessor`
4. **Connection Drops**: Check network stability and heartbeat configuration

### Debug Mode
```python
# Enable debug logging
import logging
logging.getLogger('backend.presentation.websocket').setLevel(logging.DEBUG)
```

## Future Extensions

The architecture is designed for easy extension:

- **Voice Messages**: Add `VOICE_MESSAGE` type and `VoiceHandler`
- **File Transfer**: Add `FILE_UPLOAD_*` types and `FileHandler`
- **Video Calls**: Add `VIDEO_CALL_*` types and `VideoHandler`
- **Collaborative Features**: Add `COLLABORATION_*` types and `CollabHandler`

Each extension follows the same pattern:
1. Define message types in `message_types.py`
2. Create handler class extending `MessageHandler`
3. Register handler in `WebSocketMessageProcessor`
4. Update frontend to handle new message types