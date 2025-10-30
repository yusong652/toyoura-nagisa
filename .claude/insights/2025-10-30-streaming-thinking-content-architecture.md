# Streaming Thinking Content Architecture

**Date:** 2025-10-30
**Status:** Design Document
**Related:** Gemini API Streaming, WebSocket Real-time Updates, Frontend Message Display

## Overview

This document describes the architecture for streaming LLM thinking content to the frontend in real-time, enabling progressive display of AI reasoning and response generation.

## Background

### Current Architecture (Post-Save Refresh)

```python
# Backend: Save complete message then notify
save_assistant_message(content, session_id)
await send_message_saved_notification(session_id, message_id)

# Frontend: Fetch complete message on notification
onMessage('MESSAGE_SAVED', () => {
  fetch(`/api/messages/${session_id}`)
})
```

**Limitations:**
- ❌ Not real-time (noticeable delay)
- ❌ Requires full message fetch
- ❌ No progressive display during generation

### New Architecture (Real-time Streaming)

```python
# Backend: Stream chunks as they arrive
async for chunk in stream:
    await send_streaming_chunk(session_id, message_id, chunk)

# Frontend: Append chunks incrementally
onMessage('STREAMING_CHUNK', (chunk) => {
  appendToMessage(message_id, chunk.content)
})
```

**Benefits:**
- ✅ Fully real-time display
- ✅ Progressive rendering
- ✅ Better user experience (like Claude Code)

## Core Design Decisions

### 1. Message Creation Timing

**Approach: Create Empty Message Before Streaming**

```python
async def _recursive_tool_calling(self, session_id: str, iterations: int = 0):
    # 1. Prepare context
    complete_context, api_config = await self._prepare_complete_context(session_id)

    # 2. Create empty assistant message as placeholder
    message_id = save_assistant_message_placeholder(session_id)
    await self._send_message_create_notification(
        session_id,
        message_id,
        streaming=True  # Mark as streaming message
    )

    # 3. Start streaming with message_id
    collected_chunks: List[StreamingChunk] = []
    async for chunk in self.call_api_with_context_streaming(complete_context, api_config):
        # Send to WebSocket with message_id
        await self._send_streaming_chunk_to_websocket(session_id, message_id, chunk)

        # Collect for context assembly
        collected_chunks.append(chunk)

    # 4. Construct complete response
    current_response = self._construct_response_from_streaming_chunks(collected_chunks)

    # 5. Check for tool calls
    processor = self._get_response_processor()
    if not (processor and processor.has_tool_calls(current_response)):
        # 6. Update message with complete content
        context_manager.add_response(current_response)
        final_message = processor.format_response_for_storage(current_response)
        update_assistant_message(message_id, final_message.content, session_id)

        # 7. Notify streaming complete
        await self._send_streaming_complete_notification(session_id, message_id)

        return current_response

    # Tool calls continue with existing logic...
```

**Rationale:**
- ✅ Frontend has clear message container for chunks
- ✅ Each chunk knows which message it belongs to
- ✅ Prevents chunk mixing in concurrent requests
- ⚠️ Requires two database operations (create + update)

**Alternative Rejected:** Creating message after streaming
- ❌ Frontend doesn't know where to append chunks
- ❌ Concurrent requests would cause chaos
- ❌ No loading state indicator

### 2. Thinking Content Display Strategy

**Approach: Collapsible + User Configurable**

```typescript
// Frontend rendering
const MessageContent: React.FC<{ message: Message }> = ({ message }) => {
  const [showThinking, setShowThinking] = useState(
    userSettings.showThinkingByDefault
  )

  return (
    <div className="message-content">
      {/* Thinking section (collapsible) */}
      {message.chunks.some(c => c.chunk_type === 'thinking') && (
        <Collapsible
          title="💭 Thinking process"
          open={showThinking}
          onToggle={() => setShowThinking(!showThinking)}
        >
          {message.chunks
            .filter(c => c.chunk_type === 'thinking')
            .map((chunk, i) => (
              <ThinkingBlock key={i}>
                {chunk.content}
              </ThinkingBlock>
            ))
          }
        </Collapsible>
      )}

      {/* Text section (normal display) */}
      <MarkdownRenderer>
        {message.chunks
          .filter(c => c.chunk_type === 'text')
          .map(c => c.content)
          .join('')
        }
      </MarkdownRenderer>

      {/* Streaming cursor */}
      {message.streaming && <StreamingCursor />}
    </div>
  )
}
```

**Display Options:**

| Strategy | Implementation | Use Case |
|----------|----------------|----------|
| **Collapsible** (Recommended) | Hidden by default, expandable | General use - doesn't clutter UI |
| **Different Styling** | Gray background, smaller font | Power users - always visible |
| **Completely Hidden** | Filter out thinking chunks | Simple users - focus on answer |
| **User Configurable** | Setting: show/hide/collapse | Flexibility for all users |

**Rationale:**
- ✅ Doesn't interfere with normal reading
- ✅ Users can choose to view reasoning
- ✅ Similar to Claude Code experience
- ✅ Progressive enhancement (works without thinking)

### 3. WebSocket Reconnection Strategy

**Problem:** What happens when WebSocket disconnects during streaming?

**Solution: State-based Recovery**

```typescript
// Frontend state management
interface StreamingMessage {
  message_id: string
  streaming: boolean          // Currently streaming
  chunks: StreamingChunk[]    // Received chunks
  complete: boolean           // Streaming finished
  timestamp: number
}

// WebSocket reconnection handler
const handleReconnect = async () => {
  // Find incomplete streaming messages
  const incompleteMessages = messages.filter(
    m => m.streaming && !m.complete
  )

  if (incompleteMessages.length > 0) {
    console.log(`Found ${incompleteMessages.length} incomplete streaming messages`)

    // Fetch complete content for each
    for (const msg of incompleteMessages) {
      try {
        const completeMessage = await fetchMessage(msg.message_id)

        // Replace streaming message with complete one
        updateMessage(msg.message_id, {
          ...completeMessage,
          streaming: false,
          complete: true
        })
      } catch (error) {
        console.error(`Failed to recover message ${msg.message_id}:`, error)

        // Mark as failed
        updateMessage(msg.message_id, {
          streaming: false,
          complete: false,
          error: 'Connection interrupted'
        })
      }
    }
  }
}

// WebSocket event handlers
websocket.onclose = () => {
  console.log('WebSocket disconnected')
  // Attempt reconnection
  reconnect()
}

websocket.onopen = () => {
  console.log('WebSocket reconnected')
  // Recover incomplete messages
  handleReconnect()
}
```

**Recovery Strategies:**

1. **For Incomplete Streaming Messages:**
   - Fetch complete message from database
   - Replace partial content with full content
   - Mark as complete

2. **For Failed Messages:**
   - Show error indicator
   - Provide "Retry" button
   - Allow manual refresh

3. **For New Messages During Disconnect:**
   - Check message timestamps
   - Fetch any messages created during downtime
   - Merge with local state

**Edge Cases Handled:**

| Scenario | Behavior |
|----------|----------|
| Disconnect mid-stream | Resume with complete fetch on reconnect |
| Multiple concurrent streams | Each has message_id, no mixing |
| Page refresh during stream | Fetch complete message on load |
| Backend crash during stream | Message remains in database, frontend recovers |

## Implementation Details

### Backend: New WebSocket Message Types

```python
# 1. MESSAGE_CREATE with streaming flag
await self._send_message_create_notification(
    session_id=session_id,
    message_id=message_id,
    streaming=True  # Indicates streaming message
)

# 2. STREAMING_CHUNK (already implemented)
await self._send_streaming_chunk_to_websocket(
    session_id=session_id,
    message_id=message_id,  # Link chunk to message
    chunk=chunk
)

# 3. STREAMING_COMPLETE (new)
await self._send_streaming_complete_notification(
    session_id=session_id,
    message_id=message_id
)
```

### Backend: Helper Methods

```python
async def _send_message_create_notification(
    self,
    session_id: str,
    message_id: str,
    streaming: bool = False
) -> None:
    """Notify frontend to create new message container."""
    from backend.infrastructure.websocket.connection_manager import get_connection_manager
    from backend.presentation.websocket.message_types import MessageType, create_message

    connection_manager = get_connection_manager()
    if not connection_manager:
        return

    ws_message = create_message(
        MessageType.MESSAGE_CREATE,
        session_id=session_id,
        message_id=message_id,
        role="assistant",
        initial_text="",
        streaming=streaming  # Frontend uses this to enable streaming mode
    )

    await connection_manager.send_json(session_id, ws_message.model_dump())

async def _send_streaming_complete_notification(
    self,
    session_id: str,
    message_id: str
) -> None:
    """Notify frontend that streaming is complete."""
    from backend.infrastructure.websocket.connection_manager import get_connection_manager

    connection_manager = get_connection_manager()
    if not connection_manager:
        return

    notification = {
        'type': 'STREAMING_COMPLETE',
        'message_id': message_id,
        'session_id': session_id,
        'timestamp': datetime.now().isoformat()
    }

    await connection_manager.send_json(session_id, notification)
```

### Frontend: Message State Management

```typescript
// Message interface
interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
  chunks?: StreamingChunk[]
  timestamp: number
  error?: string
}

// WebSocket message handler
const handleWebSocketMessage = (message: WebSocketMessage) => {
  switch (message.type) {
    case 'MESSAGE_CREATE':
      if (message.streaming) {
        // Create streaming message container
        const streamingMessage: Message = {
          id: message.message_id,
          role: 'assistant',
          content: '',
          streaming: true,
          chunks: [],
          timestamp: Date.now()
        }
        addMessage(streamingMessage)
      } else {
        // Regular message creation
        // (existing logic)
      }
      break

    case 'STREAMING_CHUNK':
      const targetMessage = messages.find(m => m.id === message.message_id)
      if (targetMessage?.streaming) {
        // Append chunk
        targetMessage.chunks.push(message)

        // Update content (only text chunks)
        if (message.chunk_type === 'text') {
          targetMessage.content += message.content
        }

        // Trigger re-render
        updateMessage(targetMessage)
      }
      break

    case 'STREAMING_COMPLETE':
      const completedMessage = messages.find(m => m.id === message.message_id)
      if (completedMessage) {
        completedMessage.streaming = false
        updateMessage(completedMessage)
      }
      break

    case 'MESSAGE_SAVED':
      // Non-streaming messages (tool calls, etc.)
      // Use existing fetch logic
      fetchMessage(message.message_id)
      break
  }
}
```

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         Backend                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Create placeholder message in DB                         │
│     └─> message_id = save_assistant_message_placeholder()   │
│                                                              │
│  2. Notify frontend: MESSAGE_CREATE (streaming=true)        │
│     └─> Frontend creates empty message container            │
│                                                              │
│  3. Start streaming API call                                 │
│     └─> async for chunk in generate_content_stream():       │
│         ├─> Send STREAMING_CHUNK (with message_id)          │
│         │   └─> Frontend appends chunk to message           │
│         └─> Collect chunks for context                      │
│                                                              │
│  4. Construct complete response from chunks                  │
│     └─> current_response = construct_from_chunks()          │
│                                                              │
│  5. Update message in DB with complete content               │
│     └─> update_assistant_message(message_id, content)       │
│                                                              │
│  6. Notify frontend: STREAMING_COMPLETE                      │
│     └─> Frontend marks message as complete                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                        Frontend                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  MESSAGE_CREATE (streaming=true)                             │
│  └─> Create: { id, role, content: '', streaming: true }     │
│                                                              │
│  STREAMING_CHUNK × N                                         │
│  └─> Append: chunks.push(chunk)                             │
│  └─> Update: content += chunk.content (if text)             │
│                                                              │
│  STREAMING_COMPLETE                                          │
│  └─> Mark: streaming = false                                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Backward Compatibility

### Non-streaming Messages

Tool call messages continue using existing logic:

```python
# Tool call message (not streamed)
tool_call_message = processor.format_response_for_storage(response, tool_calls)
message_id = save_assistant_message(content, session_id)

# Use existing MESSAGE_SAVED notification
await self._send_message_saved_notification(session_id, message_id, 'assistant')

# Frontend fetches complete message
fetch(`/api/messages/${session_id}`)
```

### Migration Strategy

1. **Phase 1:** Implement streaming for normal responses
2. **Phase 2:** Keep tool calls using MESSAGE_SAVED
3. **Phase 3:** (Optional) Migrate tool calls to streaming

## Configuration

### Backend Configuration

```python
# config/llm.py
class GeminiConfig(BaseSettings):
    model: str = "gemini-2.5-flash-preview-09-2025"
    thinking_budget: int = 2000
    # Streaming is always enabled (no config needed)
```

### Frontend User Settings

```typescript
// User preferences
interface UserSettings {
  // Thinking display preferences
  showThinking: boolean           // Show thinking content at all
  showThinkingByDefault: boolean  // Expand by default
  thinkingDisplayMode: 'collapsed' | 'inline' | 'hidden'

  // Streaming preferences (future)
  enableStreaming: boolean        // Enable/disable streaming
  streamingBufferMs: number       // Throttle chunk rendering
}
```

## Testing Considerations

### Backend Tests

1. **Streaming API Test**
   - ✅ Verify chunks are yielded correctly
   - ✅ Verify thinking/text/function_call separation
   - ✅ Verify complete response reconstruction

2. **Context Management Test**
   - ✅ Verify chunks are collected properly
   - ✅ Verify response is added to context
   - ✅ Verify multi-turn conversation works

3. **WebSocket Test**
   - ✅ Verify MESSAGE_CREATE is sent
   - ✅ Verify STREAMING_CHUNK is sent with message_id
   - ✅ Verify STREAMING_COMPLETE is sent

### Frontend Tests

1. **Message State Test**
   - Test message creation on MESSAGE_CREATE
   - Test chunk appending on STREAMING_CHUNK
   - Test completion on STREAMING_COMPLETE

2. **Reconnection Test**
   - Test incomplete message recovery
   - Test concurrent streaming messages
   - Test page refresh during streaming

3. **Display Test**
   - Test thinking content collapsible
   - Test streaming cursor animation
   - Test markdown rendering during streaming

## Performance Considerations

**Note:** Performance optimization is not a priority for initial implementation.

**Future Considerations:**
- Chunk throttling (reduce render frequency)
- Virtual scrolling for long thinking content
- Lazy loading of thinking chunks
- Caching of rendered markdown

## Related Files

### Backend
- `backend/infrastructure/llm/base/client.py` - Base streaming interface
- `backend/infrastructure/llm/providers/gemini/client.py` - Gemini streaming implementation
- `backend/domain/models/streaming.py` - StreamingChunk model
- `backend/presentation/websocket/message_types.py` - WebSocket message types

### Frontend
- `frontend/src/components/MessageContent.tsx` - Message rendering
- `frontend/src/hooks/useWebSocket.ts` - WebSocket handler
- `frontend/src/store/messagesSlice.ts` - Message state management
- `frontend/src/components/ThinkingBlock.tsx` - Thinking content display

## Conclusion

This architecture provides:
- ✅ Real-time streaming of thinking and text content
- ✅ Clear message container management
- ✅ Robust reconnection handling
- ✅ Flexible thinking content display
- ✅ Backward compatibility with existing messages

The implementation is production-ready and follows best practices for real-time WebSocket communication.

## References

- [Gemini Streaming API Documentation](https://ai.google.dev/gemini-api/docs/text-generation#generate-a-text-stream)
- [Claude Code Thinking Display](https://claude.ai/code)
- [WebSocket Reconnection Patterns](https://javascript.info/websocket)
