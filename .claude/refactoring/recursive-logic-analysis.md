# Recursive Tool Calling Logic Analysis

## Current Location
`backend/infrastructure/llm/base/client.py:246-534` - `_recursive_tool_calling()`

## Responsibilities Analysis

### ✅ Infrastructure Responsibilities (Keep in LLMClient)
1. **API Context Preparation**: `_prepare_complete_context()` - Provider-specific context formatting
2. **LLM API Call**: `call_api_with_context_streaming()` - Actual API invocation
3. **Response Construction**: `_construct_response_from_streaming_chunks()` - Provider-native format
4. **Response Processing**: `_get_response_processor()` - Provider-specific processor

### ❌ Application Responsibilities (Move to ChatOrchestrator)
1. **Message Persistence**:
   - `save_assistant_message()` - Create placeholder message
   - `update_assistant_message()` - Update message content
   - `save_tool_result_message()` - Save tool execution results

2. **Notification Service**:
   - `WebSocketNotificationService.send_message_create()`
   - `WebSocketNotificationService.send_streaming_update()`
   - `WebSocketNotificationService.send_message_saved()`

3. **Business Logic**:
   - Streaming content buffering (`thinking_buffer`, `text_buffer`)
   - Content block assembly for WebSocket
   - User interruption detection and handling
   - Iteration limit enforcement (`MAX_ITERATIONS = 64`)
   - Tool call detection and extraction

4. **Business Orchestration**:
   - Context manager state management
   - Tool execution coordination via `tool_manager`
   - Tool rejection detection and handling
   - Recursive control flow

5. **Error Handling**:
   - Graceful degradation for storage failures
   - Logging and exception management

## Dependencies to Inject

### External Services:
- `StorageService`: Message and tool result persistence
- `NotificationService`: WebSocket communication
- `ContextManager`: Session state management
- `ToolManager`: Tool execution coordination

### Domain Models:
- `StreamingChunk`: Streaming data structure
- `UserRejectionInterruption`: Domain exception

### Constants:
- `MAX_ITERATIONS`: Business rule (64)

## Proposed Architecture

```
┌────────────────────────────────────────────────────────┐
│ Presentation Layer                                     │
│  - llm_response_handler.process_chat_request()        │
└─────────────────┬──────────────────────────────────────┘
                  │ orchestrator.execute_conversation_turn()
┌─────────────────▼──────────────────────────────────────┐
│ Application Layer - ChatOrchestrator                   │
│  + execute_conversation_turn(session_id)               │
│  - _recursive_tool_calling(session_id, iterations)     │
│                                                         │
│  Dependencies:                                          │
│    - llm_client: LLMClientBase                         │
│    - storage_service: StorageService                   │
│    - notification_service: NotificationService         │
│    - context_manager_factory: ContextManagerFactory    │
│    - tool_manager: BaseToolManager                     │
└─────┬─────┬─────┬─────┬──────────────────────────────┘
      │     │     │     │
      ▼     ▼     ▼     ▼
┌──────┐ ┌────┐ ┌────┐ ┌─────┐
│ LLM  │ │Stor│ │Noti│ │Tool │
│Client│ │age │ │fier│ │ Mgr │
└──────┘ └────┘ └────┘ └─────┘
```

## Refactoring Strategy

### Phase 1: Create Service Layer Structure
1. Create `backend/application/services/conversation/`
2. Define `ChatOrchestrator` interface
3. Define dependency interfaces

### Phase 2: Implement ChatOrchestrator
1. Move business orchestration logic
2. Inject required services
3. Keep LLM API calls delegated to `llm_client`

### Phase 3: Simplify LLMClient
1. Remove business logic from `_recursive_tool_calling`
2. Keep only API interaction methods
3. Update abstract methods if needed

### Phase 4: Update Call Sites
1. Update `llm_response_handler.py`
2. Update dependency injection in `app.py`
3. Handle backward compatibility if needed

### Phase 5: Testing
1. Unit tests for ChatOrchestrator
2. Integration tests for full flow
3. Manual testing with real conversations

## Benefits After Refactoring

1. **Clean Architecture Compliance**: Proper dependency direction
2. **Testability**: Business logic separated from infrastructure
3. **Maintainability**: Clear separation of concerns
4. **Flexibility**: Easy to add new orchestration strategies
5. **Title Generation**: Natural integration point in service layer
