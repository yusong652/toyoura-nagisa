# Background Bash Execution Implementation Plan

## Research Findings

### Claude Code Behavior Analysis
Through experimentation with Claude Code, we discovered the following patterns:

1. **Dynamic Tool Availability**:
   - Default state: Only standard `Bash` tool is available
   - When background process starts: `BashOutput` and `KillShell` tools appear dynamically
   - Tools disappear when all background processes complete

2. **Background Process Flow**:
   - `Bash` tool with `run_in_background=true` returns process ID (e.g., `d1af26`)
   - `BashOutput(bash_id)` retrieves output and status from running processes
   - `KillShell(shell_id)` terminates specific background processes
   - Process states: `running` → `completed` (with exit codes)

3. **Output Management**:
   - Real-time output streaming and buffering
   - Separate stdout/stderr tracking
   - Support for regex filtering in BashOutput
   - Incremental output reading (only new content since last check)

## Design Approach for toyoura-nagisa

### Core Philosophy: Static Registration, Dynamic Combination
Instead of dynamic tool registration/deregistration, we'll use static tool registration with conditional tool combination in `tool_manager.py`:

```python
# In get_standardized_tools():
if has_background_processes(session_id):
    # Add BashOutput and KillShell to tool dictionary
    tools_dict.update(get_background_bash_tools())
```

### Architecture Components

#### 1. Background Process Manager
- Session-isolated process tracking
- Process lifecycle management (start, monitor, kill, cleanup)
- Output buffering with incremental reading
- Integration with existing `session_manager.py`

#### 2. Tool Implementations

##### BashOutput Tool
```python
def bash_output(
    bash_id: str,
    filter: Optional[str] = None  # regex filter for output lines
) -> Dict[str, Any]:
    """Retrieve output from background bash process"""
```

##### KillShell Tool
```python
def kill_shell(
    shell_id: str
) -> Dict[str, Any]:
    """Terminate background bash process"""
```

#### 3. Enhanced Bash Tool
- Add background execution support to existing `bash.py`
- Return process ID when `run_in_background=True`
- Maintain compatibility with current synchronous execution

#### 4. Dynamic Tool Integration
- Modify `BaseToolManager.get_standardized_tools()`
- Check for active background processes per session
- Conditionally include BashOutput/KillShell tools

### Implementation Benefits

1. **Simplicity**: No complex MCP tool registration/deregistration
2. **Session Isolation**: Each session manages its own background processes
3. **Clean Architecture**: Leverages existing session management infrastructure
4. **Claude Code Compatibility**: Matches expected tool behavior patterns

### Key Technical Considerations

1. **Process Cleanup**: Ensure all background processes are killed on session end
2. **Output Buffering**: Implement circular buffer for memory efficiency
3. **Error Handling**: Graceful handling of process crashes and timeouts
4. **Security**: Same workspace validation as current bash tool

## Next Steps

1. Design detailed interfaces for BashOutput and KillShell tools
2. Implement BackgroundProcessManager utility class
3. Enhance existing bash tool with background execution
4. Modify tool_manager.py for conditional tool combination
5. Test integrated system with various scenarios

## Expected User Experience

```bash
# Start background process
bash(command="long_running_script.sh", run_in_background=True)
# Returns: "Command running in background with ID: abc123"

# Check output (BashOutput tool now available)
bash_output(bash_id="abc123")
# Returns process status and new output

# Kill if needed (KillShell tool available)
kill_shell(shell_id="abc123")
# Returns: "Successfully killed shell: abc123"
```

This approach provides Claude Code-compatible behavior while maintaining toyoura-nagisa's clean architecture principles.