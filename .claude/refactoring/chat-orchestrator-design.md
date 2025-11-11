# ChatOrchestrator Service Design

## Overview

ChatOrchestrator is an Application layer service responsible for orchestrating conversation turns with recursive tool calling logic.

## Interface Design

```python
class ChatOrchestrator:
    """
    Application layer service for orchestrating chat conversations.

    This service handles the business logic of:
    - Streaming response management
    - Recursive tool calling coordination
    - Message persistence and notifications
    - Business rules (iteration limits, interruptions)
    """

    async def execute_conversation_turn(
        self,
        session_id: str
    ) -> ConversationResult:
        """
        Execute one conversation turn with recursive tool calling.

        Args:
            session_id: Session identifier

        Returns:
            ConversationResult: Contains final message and streaming metadata

        Raises:
            UserRejectionInterruption: When user rejects tool execution
        """
```

## Dependencies

### 1. LLMClientBase (Infrastructure)
- Purpose: LLM API interaction
- Methods needed:
  - `call_api_with_context_streaming()` - Streaming API call
  - `_prepare_complete_context()` - Context preparation
  - `_construct_response_from_streaming_chunks()` - Response construction
  - `_get_response_processor()` - Response processing
  - `get_or_create_context_manager()` - Context management

### 2. StorageService (Infrastructure)
- Purpose: Data persistence
- Methods needed:
  - `save_assistant_message()` - Create placeholder
  - `update_assistant_message()` - Update content
  - `save_tool_result_message()` - Save tool results

### 3. NotificationService (Infrastructure)
- Purpose: WebSocket communication
- Methods needed:
  - `send_message_create()` - Message creation notification
  - `send_streaming_update()` - Streaming content update
  - `send_message_saved()` - Tool result saved notification

### 4. ToolManager (Infrastructure)
- Purpose: Tool execution
- Methods needed:
  - `handle_multiple_function_calls()` - Execute tool calls

## Data Models

### ConversationResult
```python
@dataclass
class ConversationResult:
    """Result of a conversation turn."""
    final_message: BaseMessage
    streaming_message_id: Optional[str]
    interrupted: bool = False
    iteration_count: int = 0
```

### StreamingState
```python
@dataclass
class StreamingState:
    """State during streaming execution."""
    message_id: str
    collected_chunks: List[StreamingChunk]
    thinking_buffer: str
    text_buffer: str
```

## Business Rules

### Constants
```python
MAX_ITERATIONS: int = 64  # Maximum tool calling iterations
```

### Rules
1. **Iteration Limit**: Stop after 64 iterations with informative message
2. **User Interruption**: Check `context_manager.user_interrupted` in loop
3. **Tool Rejection**: Raise `UserRejectionInterruption` on direct rejections
4. **Streaming Updates**: Send accumulated content to WebSocket in real-time
5. **Final Notification**: Mark streaming complete with `streaming=False`

## Method Structure

```python
class ChatOrchestrator:
    def __init__(
        self,
        llm_client: LLMClientBase,
        storage_service: StorageService,
        notification_service: NotificationService,
        tool_manager: BaseToolManager
    ):
        self.llm_client = llm_client
        self.storage = storage_service
        self.notifications = notification_service
        self.tool_manager = tool_manager
        self.MAX_ITERATIONS = 64

    async def execute_conversation_turn(
        self,
        session_id: str
    ) -> ConversationResult:
        """Main entry point."""
        return await self._recursive_tool_calling(session_id, iterations=0)

    async def _recursive_tool_calling(
        self,
        session_id: str,
        iterations: int
    ) -> Any:
        """Core recursive logic."""
        # 1. Prepare context (delegate to llm_client)
        # 2. Create placeholder message (via storage)
        # 3. Send MESSAGE_CREATE notification (via notifications)
        # 4. Stream LLM response (delegate to llm_client)
        # 5. Handle user interruptions
        # 6. Update message storage
        # 7. Check for tool calls
        # 8. Execute tools (via tool_manager)
        # 9. Handle tool rejections
        # 10. Check iteration limit
        # 11. Recurse if needed

    async def _handle_user_interruption(
        self,
        session_id: str,
        state: StreamingState,
        iterations: int
    ) -> Any:
        """Handle user interruption during streaming."""

    async def _handle_iteration_limit(
        self,
        session_id: str,
        tool_calls: List[Dict],
        iterations: int
    ) -> None:
        """Handle iteration limit reached."""

    async def _execute_tool_calls(
        self,
        session_id: str,
        tool_calls: List[Dict]
    ) -> List[Dict]:
        """Execute tool calls and save results."""
```

## Integration Points

### From Presentation Layer
```python
# backend/presentation/streaming/llm_response_handler.py

from backend.application.services.conversation import ChatOrchestrator

async def process_chat_request(session_id: str, user_message_id: str):
    # Get orchestrator instance
    orchestrator = get_chat_orchestrator()

    # Execute conversation turn
    result = await orchestrator.execute_conversation_turn(session_id)

    # Continue with title generation, memory, etc.
```

### Service Factory
```python
# backend/application/services/conversation/__init__.py

def create_chat_orchestrator(
    llm_client: LLMClientBase
) -> ChatOrchestrator:
    """Factory function to create ChatOrchestrator with dependencies."""
    storage = StorageService()
    notifications = NotificationService()
    tool_manager = llm_client.tool_manager

    return ChatOrchestrator(
        llm_client=llm_client,
        storage_service=storage,
        notification_service=notifications,
        tool_manager=tool_manager
    )
```

## Benefits

1. **Clean Architecture**: Proper layer separation
2. **Testability**: Easy to mock dependencies
3. **Single Responsibility**: Each service has clear purpose
4. **Flexibility**: Easy to extend or replace components
5. **Maintainability**: Business logic in one place
