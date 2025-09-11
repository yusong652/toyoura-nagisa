# aiNagisa Tool Confirmation Architecture Refactoring Plan

## 1. Current Architecture Analysis

### Tool Invocation Flow
```
User → Frontend → WebSocket → LLM Handler → LLM Client → Tool Manager → MCP Server → Tool
                                                                                     ↓
User ← Frontend ← WebSocket ← LLM Handler ← LLM Client ← Tool Manager ← MCP Server ← Result
```

### Key Components
- **MCP Server** (`smart_mcp_server.py`): FastMCP server managing all tools
- **Tool Manager** (`base/tool_manager.py`): Handles tool discovery and execution
- **LLM Client**: Provider-specific implementations (Gemini, Anthropic, etc.)
- **WebSocket**: Real-time communication between frontend and backend
- **Tool Execution**: Direct synchronous execution without user intervention

### Current Issues
1. **No User Confirmation**: Tools execute immediately without user approval
2. **Synchronous Execution**: Tool execution blocks until completion
3. **No Frontend Visibility**: Frontend only sees final results, not execution requests
4. **Security Risk**: Dangerous commands execute without user awareness

## 2. Proposed Architecture

### Enhanced Tool Invocation Flow with Confirmation
```
User → Frontend → WebSocket → LLM Handler → LLM Client → Tool Manager
                                                              ↓
                                                    [Tool Confirmation Check]
                                                              ↓
                                                    Needs Confirmation?
                                                    /                \
                                                  Yes                No
                                                   ↓                 ↓
                                          Send Confirmation    Execute Tool
                                              Request               ↓
                                                ↓                Return Result
Frontend ← WebSocket ← [BASH_CONFIRMATION_REQUEST]
    ↓
User Approves/Rejects
    ↓
Frontend → WebSocket → [BASH_CONFIRMATION_RESPONSE]
                               ↓
                        Tool Manager receives response
                               ↓
                     Approved?  No → Return error
                        ↓ Yes
                    Execute Tool
                        ↓
                   Return Result
```

### Key Design Principles
1. **Non-Breaking**: Existing tools continue to work without modification
2. **Selective Confirmation**: Only specific tools require confirmation
3. **Async Communication**: WebSocket maintains real-time responsiveness
4. **Session Isolation**: Confirmations are session-specific
5. **Timeout Handling**: Auto-reject after timeout to prevent hanging

## 3. Implementation Strategy

### Phase 1: WebSocket Infrastructure (Current Focus)
1. ✅ Add WebSocket message types for confirmation
2. ✅ Create confirmation request/response message structures
3. ⏳ Implement WebSocket handler for confirmation flow

### Phase 2: Tool Manager Enhancement
1. Modify `_execute_mcp_tool` to check if tool needs confirmation
2. Add confirmation logic before tool execution
3. Implement async waiting for user response
4. Handle timeout and rejection cases

### Phase 3: Frontend Components
1. Create confirmation dialog component
2. Handle WebSocket confirmation messages
3. Display command details clearly
4. Implement approve/reject actions

### Phase 4: Bash Tool Integration
1. Mark bash tool as requiring confirmation
2. Pass WebSocket connection to tool execution context
3. Test with various bash commands

## 4. Detailed Implementation Plan

### 4.1 WebSocket Communication Layer

#### Message Types (✅ Completed)
```python
# backend/presentation/models/websocket_messages.py
BASH_CONFIRMATION_REQUEST = "BASH_CONFIRMATION_REQUEST"
BASH_CONFIRMATION_RESPONSE = "BASH_CONFIRMATION_RESPONSE"

class BashConfirmationRequestMessage:
    confirmation_id: str      # Unique request ID
    command: str             # Bash command to execute
    description: Optional[str] # Command description

class BashConfirmationResponseMessage:
    confirmation_id: str     # Matching request ID
    approved: bool          # User decision
```

### 4.2 Tool Manager Modifications

#### Required Changes in `base/tool_manager.py`

```python
class BaseToolManager:
    def __init__(self):
        # ... existing code ...
        self.pending_confirmations = {}  # Track pending confirmations
        self.websocket_manager = None    # Injected WebSocket manager
    
    async def _execute_mcp_tool_with_confirmation(
        self, 
        tool_name: str, 
        tool_args: Dict[str, Any],
        session_id: str
    ) -> CallToolResult:
        """Execute tool with optional confirmation."""
        
        # Check if tool requires confirmation
        if self._requires_confirmation(tool_name):
            # Send confirmation request via WebSocket
            confirmation_id = str(uuid.uuid4())
            await self._send_confirmation_request(
                confirmation_id,
                tool_name,
                tool_args,
                session_id
            )
            
            # Wait for user response
            approved = await self._wait_for_confirmation(
                confirmation_id,
                timeout=30
            )
            
            if not approved:
                # Return error result
                return self._create_rejection_result(tool_name)
        
        # Execute tool normally
        return await self._execute_mcp_tool(
            tool_name, 
            tool_args,
            session_id
        )
```

### 4.3 WebSocket Handler Integration

#### Connection Manager Enhancement

```python
# backend/presentation/websocket/connection.py

class ConnectionManager:
    async def handle_confirmation_response(
        self,
        session_id: str,
        confirmation_data: dict
    ):
        """Handle user confirmation response."""
        confirmation_id = confirmation_data["confirmation_id"]
        approved = confirmation_data["approved"]
        
        # Notify waiting tool execution
        if confirmation_id in self.pending_confirmations:
            self.pending_confirmations[confirmation_id].set_result(approved)
```

### 4.4 Frontend Implementation

#### Confirmation Dialog Component

```typescript
// frontend/src/components/BashConfirmationDialog.tsx

interface BashConfirmationDialogProps {
    confirmationId: string
    command: string
    description?: string
    onApprove: () => void
    onReject: () => void
}

const BashConfirmationDialog: React.FC<BashConfirmationDialogProps> = ({
    confirmationId,
    command,
    description,
    onApprove,
    onReject
}) => {
    return (
        <Dialog open={true}>
            <DialogTitle>Bash Command Confirmation</DialogTitle>
            <DialogContent>
                <Typography>The AI wants to execute:</Typography>
                <code>{command}</code>
                {description && <Typography>{description}</Typography>}
            </DialogContent>
            <DialogActions>
                <Button onClick={onReject}>Reject</Button>
                <Button onClick={onApprove} variant="contained">
                    Approve
                </Button>
            </DialogActions>
        </Dialog>
    )
}
```

## 5. Risk Mitigation

### Security Considerations
1. **Command Sanitization**: Display commands exactly as they will be executed
2. **Risk Levels**: Categorize commands by risk (read-only vs. write operations)
3. **Session Isolation**: Confirmations are strictly session-bound
4. **Timeout Protection**: Auto-reject after 30 seconds to prevent hanging

### Backward Compatibility
1. **Optional Feature**: Confirmation only for specific tools
2. **Graceful Degradation**: If WebSocket unavailable, reject with error
3. **Tool Independence**: Individual tools don't need modification

## 6. Testing Strategy

### Unit Tests
1. Test confirmation message creation and parsing
2. Test timeout handling
3. Test rejection flow

### Integration Tests
1. Test full confirmation flow with mock WebSocket
2. Test multiple concurrent confirmations
3. Test session isolation

### E2E Tests
1. Test user approving bash command
2. Test user rejecting bash command
3. Test timeout scenario

## 7. Future Enhancements

### Phase 5: Advanced Features
1. **Command History**: Track approved/rejected commands
2. **Trust Levels**: Auto-approve safe commands
3. **Batch Confirmation**: Approve multiple commands at once
4. **Conditional Approval**: Approve with modifications

### Phase 6: PFC Integration
1. **PFC-Specific Commands**: Special handling for PFC operations
2. **Simulation Preview**: Show expected outcomes before execution
3. **Parameter Validation**: Validate PFC parameters before execution
4. **Result Visualization**: Display PFC results graphically

## 8. Timeline

- **Week 1**: Complete WebSocket infrastructure and Tool Manager modifications
- **Week 2**: Implement frontend components and integration
- **Week 3**: Testing and refinement
- **Week 4**: PFC-specific enhancements

## 9. Success Metrics

1. **User Control**: 100% of bash commands require confirmation
2. **Response Time**: Confirmation dialog appears within 100ms
3. **Reliability**: No lost confirmations or hanging requests
4. **User Experience**: Clear command display and simple approve/reject flow

## 10. Conclusion

This refactoring introduces a crucial security layer while maintaining system performance and user experience. The modular approach allows incremental implementation and testing, ensuring stability throughout the process.