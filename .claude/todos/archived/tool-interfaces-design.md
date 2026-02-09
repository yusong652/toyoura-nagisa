# BashOutput and KillShell Tool Interface Design

## BashOutput Tool Interface

### Function Signature
```python
def bash_output(
    bash_id: str = Field(
        ...,
        description="The ID of the background shell to retrieve output from"
    ),
    filter: Optional[str] = Field(
        None,
        description="Optional regular expression to filter the output lines. Only lines matching this regex will be included in the result. Any lines that do not match will no longer be available to read."
    )
) -> Dict[str, Any]:
```

### Expected Return Structure
Based on Claude Code behavior:
```python
{
    "status": "success",
    "message": "Retrieved output from background process",
    "llm_content": "<status>running</status>\n\n<timestamp>2025-09-28T15:51:05.244Z</timestamp>",
    "data": {
        "process_id": "abc123",
        "status": "running" | "completed" | "killed",
        "exit_code": Optional[int],  # Only present when status="completed"
        "stdout": str,               # New output since last check
        "stderr": str,               # New error output since last check
        "timestamp": str,            # ISO format
        "command": str,              # Original command for reference
        "has_more_output": bool      # Whether there might be more output coming
    }
}
```

### Tool Description
```
Retrieves output from a running or completed background bash shell.

- Takes a shell_id parameter identifying the shell
- Always returns only new output since the last check
- Returns stdout and stderr output along with shell status
- Supports optional regex filtering to show only lines matching a pattern
- Use this tool when you need to monitor or check the output of a long-running shell
- Shell IDs can be found from previous bash tool calls with run_in_background=True
```

## KillShell Tool Interface

### Function Signature
```python
def kill_shell(
    shell_id: str = Field(
        ...,
        description="The ID of the background shell to kill"
    )
) -> Dict[str, Any]:
```

### Expected Return Structure
```python
{
    "status": "success",
    "message": "Successfully killed shell: abc123 (command_here)",
    "llm_content": '{"message":"Successfully killed shell: abc123 (command_here)","shell_id":"abc123"}',
    "data": {
        "shell_id": str,
        "command": str,              # Original command that was killed
        "kill_successful": bool,
        "final_output": str,         # Any remaining output before kill
        "timestamp": str             # When the kill occurred
    }
}
```

### Tool Description
```
Kills a running background bash shell by its ID.

- Takes a shell_id parameter identifying the shell to kill
- Returns a success or failure status
- Use this tool when you need to terminate a long-running shell
- Shell IDs can be found from previous bash tool calls with run_in_background=True
- Terminated processes cannot be restarted - you'll need to start a new background process
```

## Background Process Data Structure

### Process Registry Entry
```python
@dataclass
class BackgroundProcess:
    process_id: str
    session_id: str
    command: str
    description: Optional[str]
    process: subprocess.Popen
    start_time: datetime
    status: Literal["running", "completed", "killed"]
    exit_code: Optional[int] = None

    # Output management
    stdout_buffer: List[str] = field(default_factory=list)
    stderr_buffer: List[str] = field(default_factory=list)
    last_stdout_position: int = 0
    last_stderr_position: int = 0

    # Metadata
    last_accessed: datetime = field(default_factory=datetime.now)
    working_directory: str = ""
```

### Process Manager Interface
```python
class BackgroundProcessManager:
    def __init__(self):
        self.processes: Dict[str, BackgroundProcess] = {}
        self.session_processes: Dict[str, Set[str]] = {}  # session_id -> process_ids

    def start_process(self, session_id: str, command: str, description: Optional[str],
                     cwd: str) -> str:
        """Start a background process and return process ID"""

    def get_process_output(self, process_id: str, filter_regex: Optional[str] = None) -> Dict[str, Any]:
        """Get new output since last check"""

    def kill_process(self, process_id: str) -> Dict[str, Any]:
        """Kill a specific background process"""

    def has_active_processes(self, session_id: str) -> bool:
        """Check if session has any running processes"""

    def cleanup_session(self, session_id: str) -> None:
        """Kill all processes for a session"""

    def cleanup_completed_processes(self) -> None:
        """Remove old completed processes to prevent memory leaks"""
```

## Integration Points

### 1. Session Manager Integration
- Add background process cleanup to session deletion
- Track active processes per session
- Auto-cleanup on session timeout

### 2. Tool Manager Dynamic Loading
```python
# In BaseToolManager.get_standardized_tools()
async def get_standardized_tools(self, session_id: str, agent_profile: Optional[str] = 'general') -> Dict[str, ToolSchema]:
    # ... existing logic ...

    # Check for background processes and add dynamic tools
    from backend.infrastructure.mcp.tools.coding.utils.background_process_manager import get_process_manager
    process_manager = get_process_manager()

    if process_manager.has_active_processes(session_id):
        # Add BashOutput tool
        bash_output_schema = ToolSchema.from_function(bash_output)
        tools_dict["bash_output"] = bash_output_schema

        # Add KillShell tool
        kill_shell_schema = ToolSchema.from_function(kill_shell)
        tools_dict["kill_shell"] = kill_shell_schema

    return tools_dict
```

### 3. Enhanced Bash Tool Return
When `run_in_background=True`:
```python
return success_response(
    message=f"Command running in background with ID: {process_id}",
    llm_content=f"Command running in background with ID: {process_id}",
    process_id=process_id,
    command=command,
    background=True
)
```

## Security Considerations

1. **Session Isolation**: Processes strictly isolated by session_id
2. **Process Limits**: Maximum 5 background processes per session
3. **Timeout Management**: Auto-kill processes after 2 hours
4. **Resource Monitoring**: Track memory usage and CPU consumption
5. **Workspace Validation**: Same security as existing bash tool

## Error Handling Patterns

1. **Process Not Found**: Clear error message with available process IDs
2. **Process Already Completed**: Return final output and status
3. **Permission Errors**: Handle gracefully with user-friendly messages
4. **Resource Exhaustion**: Implement process limits and cleanup
