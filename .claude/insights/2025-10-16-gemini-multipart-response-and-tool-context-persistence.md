# Gemini Multipart Response & Tool Context Persistence Optimization

**Date**: 2025-10-16
**Branch**: `feat/gemini-multipart-text-optimization`
**Status**: Planning Phase
**Impact**: Critical - Fixes text loss and tool context persistence issues

---

## 📋 Executive Summary

This document outlines a comprehensive optimization plan to address two critical issues in aiNagisa's Gemini integration:

1. **Multipart Text Loss**: Current implementation only saves the first text part from Gemini responses, losing subsequent text parts in multimodal/streaming responses
2. **Tool Context Loss**: Server restart causes tool call context loss, breaking multi-turn reasoning chains

### Key Decisions

- ✅ **Multipart Storage**: Store all text parts as separate `{"type": "text"}` blocks (preserves API format)
- ✅ **Thinking Content**: Do NOT persist to local storage (only needed during single-request multi-turn tool calls)
- ✅ **Tool Context**: Persist tool calls and results to conversation history for context restoration
- ✅ **Extraction Logic**: Provide utility functions for text combination (frontend/TTS use)

---

## 🎯 Problem Analysis

### Problem 1: Multipart Text Loss

**Current Code** (`backend/infrastructure/llm/providers/gemini/response_processor.py:102-142`):

```python
# Extract thinking content and main text
thinking_parts = []
main_text = None

# Process all parts from the response
if hasattr(candidate.content, 'parts'):
    for part in candidate.content.parts:
        if hasattr(part, 'text') and part.text:
            if getattr(part, 'thought', False):
                thinking_parts.append(part.text)
            elif main_text is None:  # ⚠️ PROBLEM: Only captures first text part
                main_text = part.text
```

**Issue**: The condition `elif main_text is None` means only the **first** non-thinking text part is saved. Subsequent text parts are silently dropped.

**Impact**:
- Multimodal responses (text → tool_use → text) lose second text part
- Streaming responses with multiple chunks lose content
- API format incompatibility when restoring context

### Problem 2: Tool Context Loss on Server Restart

**Current Behavior**:
1. User sends message with tool call request
2. LLM returns tool_use content
3. Tool executes and returns result
4. LLM generates final response
5. ⚠️ **Only final response is saved to conversation history**
6. Server restart → Tool call context lost → Multi-turn reasoning broken

**Current Storage Format**:
```python
# Only the final assistant message is saved
[
    {"role": "user", "content": "Please analyze this file"},
    {"role": "assistant", "content": [
        {"type": "text", "text": "Analysis complete: ..."}
    ]}
]
# Missing: tool_use and tool_result intermediate steps
```

**Impact**:
- Loss of reasoning chain context
- LLM cannot understand previous tool usage patterns
- Degraded multi-turn conversation quality
- Repeated tool calls for same information

---

## 🏗️ Architecture Analysis

### Current Message Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User Input                                               │
│    ├─> UserMessage stored to DB                            │
│    └─> Formatted for Gemini API                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Gemini Response (with tool_use)                         │
│    ├─> response_processor.format_response_for_storage()    │
│    │    └─> Creates AssistantMessage with tool_use content │
│    └─> context_manager.add_response()                      │
│         └─> Adds to working_contents (NOT saved to DB)     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Tool Execution                                           │
│    └─> context_manager.add_tool_result()                   │
│         └─> Adds to working_contents (NOT saved to DB)     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Final Gemini Response                                    │
│    ├─> response_processor.format_response_for_storage()    │
│    │    └─> ⚠️ Only first text part saved                  │
│    ├─> Save to DB via content_processor                    │
│    └─> ⚠️ Tool context discarded after session ends        │
└─────────────────────────────────────────────────────────────┘
```

### Storage Layer Architecture

**Messages Table Structure** (JSON storage):
```python
# backend/infrastructure/storage/session_manager.py
{
    "messages": [
        {
            "role": "user",
            "content": "...",  # Can be str or List[Dict]
            "id": "msg_uuid",
            "timestamp": "2025-10-16T10:00:00"
        },
        {
            "role": "assistant",
            "content": [  # List[Dict] for multimodal content
                {"type": "text", "text": "..."},
                {"type": "tool_use", "id": "...", "name": "...", "input": {...}}
            ],
            "id": "msg_uuid",
            "timestamp": "2025-10-16T10:00:05"
        }
    ]
}
```

**Key Components**:
1. **Message Factory** (`backend/domain/models/message_factory.py`)
   - `message_factory()`: Creates message objects from storage
   - `message_factory_no_thinking()`: Filters thinking for API calls
   - `extract_text_from_message()`: Extracts text for search/memory

2. **Response Processor** (`backend/infrastructure/llm/providers/gemini/response_processor.py`)
   - `format_response_for_storage()`: Converts API response → AssistantMessage
   - **Current Issue**: Only saves first text part (line 116)

3. **Context Manager** (`backend/infrastructure/llm/providers/gemini/context_manager.py`)
   - `add_response()`: Adds response to working context
   - `add_tool_result()`: Adds tool result to working context
   - **Current Issue**: Tool context only lives in memory during request

4. **Message Formatter** (`backend/infrastructure/llm/providers/gemini/message_formatter.py`)
   - `format_messages()`: Converts BaseMessage → Gemini API format
   - **Handles**: Skips thinking content (line 50), processes multimodal

---

## 💡 Proposed Solution

### Design Principle: Separation of Concerns

```
┌──────────────────────────────────────────────────────────────────┐
│ Storage Layer (Persistence)                                      │
│ ├─ Store COMPLETE API format (all text parts, tool_use, etc.)   │
│ ├─ Exclude thinking content (transient, single-request only)    │
│ └─ Include tool context (for multi-turn reasoning)              │
└──────────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────────┐
│ Extraction Layer (Consumption)                                   │
│ ├─ Frontend: Combine text parts for rendering                   │
│ ├─ TTS: Extract & combine text for speech synthesis             │
│ └─ Memory: Extract text for semantic search                     │
└──────────────────────────────────────────────────────────────────┘
```

### Solution 1: Multipart Text Storage

**New Storage Format** (Method A - Recommended):

```python
# Store all text parts as separate blocks
content = [
    # Thinking content NOT saved (transient)
    {"type": "text", "text": "First text part"},
    {"type": "tool_use", "id": "call_1", "name": "read_file", "input": {"path": "..."}},
    {"type": "text", "text": "Second text part"},
    {"type": "text", "text": "Third text part"}
]
```

**Benefits**:
- ✅ Preserves original Gemini API structure
- ✅ Supports text/tool_use interleaving
- ✅ API format compatible for context restoration
- ✅ Clear semantic separation

**Trade-off**:
- ⚠️ Requires extraction logic for frontend/TTS (acceptable, provides utility functions)

### Solution 2: Tool Context Persistence

**New Message Flow**:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User Input                                               │
│    └─> Save to DB immediately                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Gemini Response (with tool_use)                         │
│    ├─> format_response_for_storage() [NEW: multi-part]     │
│    ├─> ✅ Save AssistantMessage with tool_use to DB        │
│    └─> add_response() to working context                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Tool Execution                                           │
│    ├─> add_tool_result() to working context                │
│    └─> ✅ Save tool result as UserMessage to DB [NEW]      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Final Gemini Response                                    │
│    ├─> format_response_for_storage() [NEW: all text parts] │
│    └─> ✅ Save complete AssistantMessage to DB             │
└─────────────────────────────────────────────────────────────┘
```

**New Conversation History Format**:

```python
[
    # User request
    {"role": "user", "content": "Please analyze this file", "id": "msg_1"},

    # LLM decides to use tool
    {"role": "assistant", "content": [
        {"type": "text", "text": "I'll read the file first."},
        {"type": "tool_use", "id": "call_1", "name": "read_file", "input": {"path": "file.py"}}
    ], "id": "msg_2"},

    # Tool execution result
    {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "call_1", "content": "file content..."}
    ], "id": "msg_3"},

    # Final LLM response
    {"role": "assistant", "content": [
        {"type": "text", "text": "Analysis complete: ..."}
    ], "id": "msg_4"}
]
```

**Benefits**:
- ✅ Complete reasoning chain preserved
- ✅ Tool context available after restart
- ✅ Multi-turn conversation quality maintained
- ✅ Debugging and analysis capabilities

### Solution 3: Thinking Content Handling

**Decision**: Do NOT persist thinking content to local storage.

**Rationale**:
1. **Transient Nature**: Thinking is only relevant during single-request multi-turn tool calls
2. **Token Efficiency**: No need to send thinking back to API in future requests
3. **Privacy**: Thinking may contain sensitive reasoning that shouldn't be logged
4. **Existing Filter**: `message_factory_no_thinking()` already removes thinking for API calls

**Implementation**:
- Current behavior is correct: thinking excluded by `message_formatter.py:50-51`
- Keep `format_response_for_storage()` NOT saving thinking blocks
- Maintain `_filter_thinking_blocks()` in message_factory.py

---

## 🔧 Implementation Plan

### Phase 1: Multipart Text Storage (Priority: High)

**File**: `backend/infrastructure/llm/providers/gemini/response_processor.py`

**Modification 1**: Update `format_response_for_storage()` method

```python
# OLD CODE (lines 102-142)
thinking_parts = []
main_text = None  # ⚠️ Only stores first text part

for part in candidate.content.parts:
    if hasattr(part, 'text') and part.text:
        if getattr(part, 'thought', False):
            thinking_parts.append(part.text)
        elif main_text is None:  # ⚠️ Drops subsequent parts
            main_text = part.text

# Add main text content - ONLY first part
if main_text:
    content.append({"type": "text", "text": main_text})
```

```python
# NEW CODE
thinking_parts = []
text_parts = []  # ✅ Collect ALL text parts

for part in candidate.content.parts:
    if hasattr(part, 'text') and part.text:
        if getattr(part, 'thought', False):
            thinking_parts.append(part.text)
        else:
            # ✅ Collect ALL non-thinking text parts
            text_parts.append(part.text)
    elif hasattr(part, 'function_call') and part.function_call:
        # Add tool_use block BEFORE adding next text part
        # This preserves interleaving order
        func_call = part.function_call
        content.append({
            "type": "tool_use",
            "id": getattr(func_call, 'id', f"call_{len(content)}"),
            "name": func_call.name,
            "input": dict(func_call.args) if hasattr(func_call, 'args') else {}
        })

# ✅ Add each text part as separate block (preserves order and API format)
for text_part in text_parts:
    if text_part.strip():  # Only add non-empty parts
        content.append({
            "type": "text",
            "text": text_part
        })
```

**Modification 2**: Add utility function for text extraction

```python
@staticmethod
def extract_combined_text_from_content(content: List[Dict]) -> str:
    """
    Extract and combine all text parts from content array.

    Used by frontend rendering and TTS processing to get complete text.
    Skips thinking, tool_use, and tool_result blocks.

    Args:
        content: Message content array with multiple parts

    Returns:
        str: Combined text from all text parts

    Example:
        >>> content = [
        ...     {"type": "text", "text": "Part 1"},
        ...     {"type": "tool_use", "name": "read"},
        ...     {"type": "text", "text": "Part 2"}
        ... ]
        >>> extract_combined_text_from_content(content)
        'Part 1Part 2'
    """
    text_parts = []
    for item in content:
        if isinstance(item, dict) and item.get('type') == 'text':
            text_parts.append(item.get('text', ''))
    return ''.join(text_parts)
```

### Phase 2: Tool Context Persistence (Priority: Critical)

**Problem**: Current implementation only saves final response, tool context lost on restart.

**Files to Modify**:
1. `backend/application/services/chat_service.py` - Add tool message saving
2. `backend/infrastructure/llm/providers/gemini/context_manager.py` - Track tool messages
3. `backend/shared/utils/helpers.py` - Add `save_tool_message()` helper

**Implementation Strategy**:

#### Step 2.1: Define Tool Result Message Format

**File**: `backend/domain/models/messages.py`

Add support for tool result messages (already supports `List[Dict]` content):

```python
# Tool result stored as UserMessage with special content format
{
    "role": "user",
    "content": [
        {
            "type": "tool_result",
            "tool_use_id": "call_1",
            "content": "Tool execution result...",
            "is_error": False  # Optional error flag
        }
    ],
    "id": "msg_uuid",
    "timestamp": "2025-10-16T10:00:05"
}
```

**No new message type needed** - reuse existing `UserMessage` with structured content.

#### Step 2.2: Save Tool Call Messages

**File**: `backend/application/services/chat_service.py`

Current flow:
```python
async def send_message_stream():
    # ... user message handling ...

    # Tool call loop
    async for response in llm_client.chat_stream(...):
        if has_tool_calls:
            # Execute tools
            tool_results = execute_tools(...)
            # ⚠️ Tool context only in working_contents (memory)
            context_manager.add_tool_result(...)
        else:
            # Final response
            final_message = format_response_for_storage(response)
            # ⚠️ Only final message saved
            save_assistant_message(final_message, session_id)
```

New flow:
```python
async def send_message_stream():
    # ... user message handling ...

    # Tool call loop
    async for response in llm_client.chat_stream(...):
        if has_tool_calls:
            # ✅ Save assistant message with tool_use
            tool_call_message = format_response_for_storage(response)
            save_assistant_message(tool_call_message, session_id)

            # Execute tools
            tool_results = execute_tools(...)

            # ✅ Save tool results as user messages
            for tool_result in tool_results:
                save_tool_result_message(tool_result, session_id)

            # Add to working context (for current request)
            context_manager.add_tool_result(...)
        else:
            # Final response
            final_message = format_response_for_storage(response)
            save_assistant_message(final_message, session_id)
```

#### Step 2.3: Add Save Helper Functions

**File**: `backend/shared/utils/helpers.py`

```python
def save_tool_result_message(
    tool_call_id: str,
    tool_name: str,
    tool_result: Dict[str, Any],
    session_id: str
) -> str:
    """
    Save tool execution result as a user message.

    Tool results are stored as UserMessage with tool_result content type,
    allowing LLM to understand tool execution context after server restart.

    Args:
        tool_call_id: ID of the tool call this result corresponds to
        tool_name: Name of the executed tool
        tool_result: Tool execution result (ToolResult format)
        session_id: Current session ID

    Returns:
        str: Generated message ID

    Example:
        >>> tool_result = {
        ...     "status": "success",
        ...     "message": "File read successfully",
        ...     "llm_content": {"parts": [{"type": "text", "text": "content..."}]},
        ...     "data": {"file_path": "example.py"}
        ... }
        >>> save_tool_result_message("call_1", "read_file", tool_result, session_id)
        'msg_uuid_123'
    """
    from backend.infrastructure.storage import get_session_manager
    from backend.domain.models.messages import UserMessage
    import uuid
    from datetime import datetime

    # Extract content from tool result
    llm_content = tool_result.get("llm_content", {})

    # Build tool_result content block
    tool_result_content = {
        "type": "tool_result",
        "tool_use_id": tool_call_id,
        "tool_name": tool_name,
        "content": llm_content,  # Use llm_content from ToolResult
        "is_error": tool_result.get("status") == "error"
    }

    # Create user message with tool result
    message = UserMessage(
        content=[tool_result_content],
        id=str(uuid.uuid4()),
        timestamp=datetime.now()
    )

    # Save to session
    session_manager = get_session_manager()
    session_manager.add_message(session_id, message.to_dict())

    return message.id
```

#### Step 2.4: Update Message Formatter for Tool Results

**File**: `backend/infrastructure/llm/providers/gemini/message_formatter.py`

Add handling for tool_result content type:

```python
@staticmethod
def format_messages(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
    """Convert aiNagisa BaseMessage objects to Gemini API format."""
    from google.genai import types

    contents = []

    for msg in messages:
        if msg is None:
            continue

        parts = []

        # Handle message content based on format
        if isinstance(msg.content, list):
            for item in msg.content:
                if isinstance(item, dict):
                    # Skip thinking content
                    if item.get("type") in ["thinking", "redacted_thinking"]:
                        continue

                    # Handle text parts
                    if item.get("type") == "text" and item.get("text"):
                        parts.append(types.Part(text=item["text"]))

                    # ✅ NEW: Handle tool_result parts
                    elif item.get("type") == "tool_result":
                        tool_result_content = item.get("content", {})

                        # Extract text from tool result content
                        if isinstance(tool_result_content, dict) and "parts" in tool_result_content:
                            for part in tool_result_content["parts"]:
                                if part.get("type") == "text":
                                    response_text = part.get("text", "")
                                    break
                        else:
                            response_text = str(tool_result_content)

                        # Create FunctionResponse
                        function_response = types.FunctionResponse(
                            name=item.get("tool_name", "unknown"),
                            response={
                                "status": "error" if item.get("is_error") else "success",
                                "content": response_text
                            }
                        )
                        parts.append(types.Part(function_response=function_response))

                    # ✅ NEW: Handle tool_use parts (for assistant messages with tool calls)
                    elif item.get("type") == "tool_use":
                        function_call = types.FunctionCall(
                            name=item.get("name"),
                            args=item.get("input", {})
                        )
                        parts.append(types.Part(function_call=function_call))

                    # Handle image content
                    elif item.get("type") == "image" and "inline_data" in item:
                        blob = GeminiMessageFormatter._process_inline_data(item['inline_data'])
                        if blob:
                            parts.append(types.Part(inline_data=blob))
        else:
            # Simple text message
            parts.append(types.Part(text=str(msg.content)))

        # Map role and add to contents if we have parts
        if parts:
            mapped_role = GeminiMessageFormatter._map_role(msg.role)
            contents.append({"role": mapped_role, "parts": parts})

    return contents
```

### Phase 3: Extraction Layer Updates (Priority: Medium)

**File**: `backend/presentation/streaming/content_processor.py`

Current code (lines 42-45) already handles multiple text parts correctly:

```python
# Extract text content for keyword parsing and TTS (excluding thinking blocks)
text_content = ""
for item in content:
    if isinstance(item, dict) and item.get('type') == 'text':
        text_content += item.get('text', '')  # ✅ Already combines all parts
```

**No changes needed** - existing logic is correct!

### Phase 4: Frontend Compatibility (Priority: Low)

**Current Frontend Behavior**:

`frontend/src/components/Message/renderers/BotMessageRenderer.tsx` expects a `text` field:

```typescript
const { files, isLoading, streaming, text } = message
const displayText = text || ''
```

**Question**: Where does `message.text` come from?

**Investigation needed**:
1. WebSocket message format sent to frontend
2. Whether backend already combines text parts before sending
3. If we need frontend changes to handle content array

**Potential Solutions**:

**Option A**: Backend combines text before sending to frontend (recommended)
```python
# In WebSocket handler
websocket_message = {
    "message_id": msg_id,
    "text": extract_combined_text_from_content(msg.content),  # Combined
    "content": msg.content,  # Original structure (for debugging)
    "files": files,
    ...
}
```

**Option B**: Frontend extracts text from content array
```typescript
// In BotMessageRenderer.tsx
const displayText = message.text || extractTextFromContent(message.content) || ''

function extractTextFromContent(content: any[]): string {
  if (!content || !Array.isArray(content)) return ''
  return content
    .filter(item => item.type === 'text')
    .map(item => item.text)
    .join('')
}
```

---

## 🧪 Testing Strategy

### Test Cases for Multipart Text

1. **Single Text Part** (baseline)
   ```
   Input: One text part response
   Expected: Text saved correctly
   ```

2. **Multiple Text Parts**
   ```
   Input: Response with 3 text parts
   Expected: All 3 parts saved as separate blocks
   ```

3. **Text-Tool-Text Interleaving**
   ```
   Input: text → tool_use → text
   Expected: Order preserved, both texts saved
   ```

4. **Text Extraction**
   ```
   Input: Content array with multiple text parts
   Expected: extract_combined_text returns concatenated text
   ```

### Test Cases for Tool Context

1. **Single Tool Call**
   ```
   User: "Read file.py"
   Expected Storage:
     - UserMessage: "Read file.py"
     - AssistantMessage: [text, tool_use]
     - UserMessage: [tool_result]
     - AssistantMessage: [text] (final)
   ```

2. **Multiple Tool Calls**
   ```
   User: "Compare file1.py and file2.py"
   Expected Storage:
     - UserMessage: request
     - AssistantMessage: [tool_use] (read file1)
     - UserMessage: [tool_result]
     - AssistantMessage: [tool_use] (read file2)
     - UserMessage: [tool_result]
     - AssistantMessage: [text] (comparison)
   ```

3. **Context Restoration After Restart**
   ```
   1. Execute conversation with tools
   2. Restart server
   3. Send follow-up message
   Expected: LLM has access to previous tool calls
   ```

### Test Cases for Thinking Content

1. **Thinking Exclusion from Storage**
   ```
   Response: thinking + text + tool_use
   Expected Storage: text + tool_use (no thinking)
   ```

2. **Thinking Exclusion from API Calls**
   ```
   Load history with thinking
   Expected API format: thinking filtered out
   ```

---

## 📊 Impact Analysis

### Benefits

1. **Data Integrity**
   - ✅ No more text loss in multipart responses
   - ✅ Complete reasoning chain preserved
   - ✅ API format compatibility maintained

2. **Performance**
   - ✅ Tool context restoration enables smarter LLM behavior
   - ✅ Reduced redundant tool calls
   - ✅ Better multi-turn conversation quality

3. **Debugging & Observability**
   - ✅ Full conversation history with tool interactions
   - ✅ Easier debugging of tool call issues
   - ✅ Better analytics on tool usage patterns

### Risks & Mitigation

1. **Storage Size Increase**
   - Risk: More messages stored (tool calls + results)
   - Mitigation: Reasonable - tool messages are small
   - Monitoring: Track database size growth

2. **API Token Usage**
   - Risk: More messages in context = more tokens
   - Mitigation: Existing message limit logic handles this
   - Note: Tool results already counted in current implementation

3. **Backward Compatibility**
   - Risk: Old conversations lack tool context
   - Mitigation: Graceful degradation - system works without tool history
   - Note: New conversations immediately benefit

---

## 🚀 Rollout Plan

### Stage 1: Multipart Text Fix (Week 1)
- Implement `format_response_for_storage()` changes
- Add `extract_combined_text_from_content()` utility
- Test with various response formats
- Deploy to staging

### Stage 2: Tool Context Persistence (Week 2)
- Implement tool message saving logic
- Update message formatter for tool results
- Add helper functions
- Test context restoration after restart
- Deploy to staging

### Stage 3: Integration Testing (Week 3)
- End-to-end testing with real conversations
- Performance monitoring
- Database size analysis
- Frontend compatibility verification

### Stage 4: Production Rollout (Week 4)
- Deploy to production
- Monitor for issues
- Collect user feedback
- Iterate based on findings

---

## 📝 Implementation Checklist

### Phase 1: Multipart Text Storage
- [ ] Modify `format_response_for_storage()` to collect all text parts
- [ ] Add `extract_combined_text_from_content()` utility function
- [ ] Update unit tests for response processor
- [ ] Test with sample multipart responses
- [ ] Verify TTS and frontend extraction logic compatibility

### Phase 2: Tool Context Persistence
- [ ] Add tool result message format to messages.py
- [ ] Implement `save_tool_result_message()` helper
- [ ] Update `chat_service.py` to save tool messages
- [ ] Modify `message_formatter.py` to handle tool_result content
- [ ] Add unit tests for tool message saving
- [ ] Test context restoration after restart

### Phase 3: Thinking Content Handling
- [ ] Verify thinking exclusion from storage (already implemented)
- [ ] Verify thinking exclusion from API calls (already implemented)
- [ ] Add tests to ensure thinking not persisted
- [ ] Document thinking content lifecycle

### Phase 4: Frontend Integration
- [ ] Investigate WebSocket message format
- [ ] Determine if text combination needed in backend
- [ ] Update frontend if needed for content array handling
- [ ] Test frontend rendering with new format
- [ ] Verify TTS processing works correctly

### Phase 5: Testing & Documentation
- [ ] Write comprehensive unit tests
- [ ] Write integration tests for full conversation flow
- [ ] Test context restoration scenarios
- [ ] Update API documentation
- [ ] Create migration guide for existing sessions

---

## 🔗 Related Files

### Core Implementation Files
- `backend/infrastructure/llm/providers/gemini/response_processor.py` - Response processing
- `backend/infrastructure/llm/providers/gemini/context_manager.py` - Context management
- `backend/infrastructure/llm/providers/gemini/message_formatter.py` - Message formatting
- `backend/domain/models/messages.py` - Message models
- `backend/domain/models/message_factory.py` - Message creation
- `backend/application/services/chat_service.py` - Main chat flow
- `backend/shared/utils/helpers.py` - Helper functions

### Extraction & Processing
- `backend/presentation/streaming/content_processor.py` - Content processing
- `backend/presentation/streaming/tts_processor.py` - TTS processing
- `backend/infrastructure/tts/utils.py` - TTS text utilities

### Frontend
- `frontend/src/components/Message/renderers/BotMessageRenderer.tsx` - Bot message rendering
- `frontend/src/components/Message/content/MessageText.tsx` - Text rendering

### Storage
- `backend/infrastructure/storage/session_manager.py` - Session storage
- `backend/infrastructure/storage/message_storage.py` - Message persistence

---

## 🎓 Key Learnings

1. **API Format Fidelity**
   - Preserving original API format in storage enables better context restoration
   - Separation of storage format vs. extraction format provides flexibility

2. **Tool Context Importance**
   - Tool call history is critical for multi-turn reasoning
   - Current practice of discarding tool context is a major limitation

3. **Thinking Content Lifecycle**
   - Thinking is transient and request-scoped
   - No need to persist beyond single request
   - Existing filtering logic is correct

4. **Multipart Response Handling**
   - Gemini API can return multiple text parts in various patterns
   - Naive "first text only" approach loses data
   - Need to preserve all parts while maintaining order

---

## 📚 References

- Gemini API Documentation: https://ai.google.dev/api
- aiNagisa Message Flow: `CLAUDE.md` - Message Handling section
- Tool Result Format: `backend/infrastructure/mcp/utils/tool_result.py`
- MCP Tool System: `backend/infrastructure/mcp/` directory
- Storage Architecture: `backend/infrastructure/storage/` directory

---

## ✅ Next Steps

1. **Review this document** with the team
2. **Clarify frontend requirements** - investigate WebSocket message format
3. **Implement Phase 1** - Multipart text storage (critical path)
4. **Implement Phase 2** - Tool context persistence (critical path)
5. **Test thoroughly** with various conversation patterns
6. **Deploy to staging** for validation
7. **Monitor production** after rollout

---

**Document Version**: 1.0
**Last Updated**: 2025-10-16
**Next Review**: After Phase 1 implementation
