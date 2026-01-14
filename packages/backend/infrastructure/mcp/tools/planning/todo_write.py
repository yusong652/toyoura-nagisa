"""todo_write tool - persistent task tracking with cross-session sharing.

This tool implements Claude Code-compatible TodoWrite functionality, enabling LLMs to:
- Plan and track multi-step workflows
- Share todo lists across all sessions in the workspace
- Provide visibility into current progress across sessions
- Demonstrate thoroughness to users

All sessions in the same workspace share the same todo list for better continuity.
"""

import logging
from typing import List, Dict, Any, Literal, cast
from pydantic import BaseModel, Field
from fastmcp import FastMCP
from fastmcp.server.context import Context

from backend.infrastructure.mcp.utils.tool_result import ToolResult, success_response, error_response
from backend.infrastructure.storage.todo_storage import get_todo_storage
from backend.shared.utils.workspace import get_workspace_for_profile

logger = logging.getLogger(__name__)

__all__ = ["todo_write", "register_todo_write_tool", "TodoItem"]


# -----------------------------------------------------------------------------
# TodoItem Model - Pydantic schema for JSON Schema generation
# -----------------------------------------------------------------------------

class TodoItem(BaseModel):
    """Single todo item in a task list.

    Defines the schema for individual todo items with strict validation,
    ensuring LLMs receive clear parameter requirements via JSON Schema.
    """
    content: str = Field(
        min_length=1,
        description="Task description in imperative form (e.g., 'Run tests', 'Build the project')"
    )
    activeForm: str = Field(
        min_length=1,
        description="Task description in present continuous form (e.g., 'Running tests', 'Building the project')"
    )
    status: Literal["pending", "in_progress", "completed"] = Field(
        description="Current task status: pending (not started), in_progress (currently working), completed (finished)"
    )


async def todo_write(
    context: Context,
    todos: List[TodoItem] = Field(
        ...,
        description="Array of todo objects. Each object MUST have: content (imperative form, e.g. 'Run tests'), activeForm (present continuous, e.g. 'Running tests'), status ('pending'|'in_progress'|'completed')"
    )
) -> Dict[str, Any]:
    """Use this tool to create and manage a structured task list for your current coding session. This helps you track progress, organize complex tasks, and demonstrate thoroughness to the user.
It also helps the user understand the progress of the task and overall progress of their requests.

## Parameter Format
The `todos` parameter is an array of objects, NOT strings. Each object requires three fields:
```json
{
  "todos": [
    {"content": "Run tests", "activeForm": "Running tests", "status": "pending"},
    {"content": "Fix bug", "activeForm": "Fixing bug", "status": "in_progress"}
  ]
}
```

## When to Use This Tool
Use this tool proactively in these scenarios:

1. **PFC Simulation Workflows** - When executing the mandatory script-only workflow (Query → Test → Production → Monitor)
2. **Multi-stage Simulations** - Tasks involving initialization, equilibration, loading, and analysis phases
3. **Documentation-Driven Development** - When multiple documentation queries are needed before script writing
4. **Error Debugging Workflows** - Following the error escalation strategy (Docs → API → Web → User)
5. **Long-Running Tasks** - Simulations requiring background execution and periodic monitoring
6. **Multi-File Operations** - Workflows spanning test scripts, production scripts, analysis scripts, and data files
7. **Complex multi-step tasks** - When a task requires 3 or more distinct steps or actions
8. **User provides multiple tasks** - When users provide a list of things to be done (numbered or comma-separated)
9. **After receiving new instructions** - Immediately capture user requirements as todos
10. **When you start working on a task** - Mark it as in_progress BEFORE beginning work. Ideally you should only have one todo as in_progress at a time
11. **After completing a task** - Mark it as completed and add any new follow-up tasks discovered during implementation

## When NOT to Use This Tool

Skip using this tool when:
1. **Single documentation queries** - Quick reference lookups with immediate answers
2. **Simple status checks** - Monitoring running tasks with `pfc_check_task_status`
3. **Trivial script edits** - Single syntax corrections or parameter adjustments
4. **Informational questions** - Explaining PFC concepts or command differences
5. **Single, straightforward tasks** - Operations that can be completed in 1-2 simple steps
6. **Purely conversational interactions** - Answering questions without executing operations

NOTE that you should not use this tool if there is only one trivial task to do. In this case you are better off just doing the task directly.

## Examples of When to Use the Todo List

<example>
User: Create a ball settling simulation with 1000 balls and linear contact model
Assistant: I'll help create a ball settling simulation. Let me create a todo list to track this PFC workflow.
*Calls todo_write with:*
```json
{"todos": [
  {"content": "Query PFC docs for ball generation", "activeForm": "Querying ball generation docs", "status": "in_progress"},
  {"content": "Query PFC docs for contact model", "activeForm": "Querying contact model docs", "status": "pending"},
  {"content": "Write test script (10 balls)", "activeForm": "Writing test script", "status": "pending"},
  {"content": "Execute and validate test", "activeForm": "Executing test script", "status": "pending"},
  {"content": "Write production script", "activeForm": "Writing production script", "status": "pending"},
  {"content": "Execute production in background", "activeForm": "Executing production script", "status": "pending"},
  {"content": "Monitor simulation progress", "activeForm": "Monitoring simulation", "status": "pending"}
]}
```
*Begins working on the first task*

<reasoning>
The assistant used the todo list because:
1. PFC simulations require multi-stage workflow (query → test → production → monitor)
2. Each stage has clear success criteria that need tracking
3. Documentation queries must be completed before script writing
4. Test validation prevents syntax errors in long-running production runs
5. The mandatory workflow pattern requires systematic task tracking
</reasoning>
</example>

<example>
User: Run a triaxial compression test on a soil sample with strain-controlled loading
Assistant: This is a complex multi-stage simulation. Let me create a todo list.
*Calls todo_write with todos array containing objects like:*
```json
{"content": "Query docs for domain/ball setup", "activeForm": "Querying documentation", "status": "in_progress"}
```
*Each todo object follows the same format as the first example*

<reasoning>
Complex simulations require systematic tracking of: query → test → production → monitor stages.
</reasoning>
</example>

<example>
User: Help me debug the contact model setup - my simulation shows unexpected results
Assistant: I'll systematically debug this. Let me create a todo list.
*Calls todo_write with todos array - each item as an object with content/activeForm/status fields*

<reasoning>
Debugging requires systematic investigation with documentation queries, test scripts, and validation steps.
</reasoning>
</example>

## Examples of When NOT to Use the Todo List

<example>
User: What is the difference between ball generate and ball create commands?
Assistant: The `ball generate` command creates multiple balls at once with specified distributions (e.g., `ball generate number 100 radius 0.1`), while `ball create` creates a single ball at a specific position (e.g., `ball create position (1,2,3) radius 0.1`).

Use `ball generate` for bulk particle creation in random or regular patterns, and `ball create` when you need precise control over individual particle placement.

<reasoning>
The assistant did not use the todo list because this is a pure informational request explaining PFC command differences. No scripts need to be written, no documentation needs to be queried, and no simulation needs to be executed. This is a simple conceptual explanation.
</reasoning>
</example>

<example>
User: Check the status of my running simulation task
Assistant: Let me check the task status for you.

*Executes: pfc_check_task_status(task_id)*

Your simulation is currently running at cycle 5000/10000 (50% complete). The average velocity is 0.023 m/s and the equilibrium ratio is 0.15. The simulation is progressing normally.

<reasoning>
The assistant did not use the todo list because this is a single status query operation with immediate results. Task monitoring doesn't require multi-step planning or systematic organization - it's a simple query-and-report operation.
</reasoning>
</example>

<example>
User: Show me the current ball count in the simulation
Assistant: Let me query the PFC documentation for the ball count method.

*Executes: pfc_query_python_api("ball count")*

According to the documentation, you can get the ball count using `itasca.ball.count()`. Let me write a quick script to check your current simulation:

*Writes and executes simple query script*

Your simulation currently contains 1000 balls.

<reasoning>
The assistant did not use the todo list because this is a straightforward query operation. Although it involves documentation lookup and script execution, these are single-purpose steps with immediate results. The workflow is linear (query → script → result) without branching or complex dependencies.
</reasoning>
</example>

<example>
User: Fix the syntax error in my test script - I'm getting "unknown parameter 'count'"
Assistant: Let me read your test script first.

*Reads the test script*

I see the issue - you're using `ball generate count 100` but the correct parameter name is `number`. Let me fix this for you.

*Edits the script to replace 'count' with 'number'*

Fixed! The corrected syntax is `ball generate number 100 radius 0.1`. This should resolve the error.

<reasoning>
The assistant did not use the todo list because this is a single syntax correction task. The issue is already identified (wrong parameter name), the fix is straightforward (replace 'count' with 'number'), and no testing or validation workflow is required. This is a direct edit operation.
</reasoning>
</example>

## Task States and Management

1. **Task States**: Use these states to track progress:
   - pending: Task not yet started
   - in_progress: Currently working on (limit to ONE task at a time)
   - completed: Task finished successfully

   **IMPORTANT**: Task descriptions must have two forms:
   - content: The imperative form describing what needs to be done (e.g., "Run tests", "Build the project")
   - activeForm: The present continuous form shown during execution (e.g., "Running tests", "Building the project")

2. **Task Management**:
   - Update task status in real-time as you work
   - Mark tasks complete IMMEDIATELY after finishing (don't batch completions)
   - Exactly ONE task must be in_progress at any time (not less, not more)
   - Complete current tasks before starting new ones
   - Remove tasks that are no longer relevant from the list entirely

3. **Task Completion Requirements**:
   - ONLY mark a task as completed when you have FULLY accomplished it
   - If you encounter errors, blockers, or cannot finish, keep the task as in_progress
   - When blocked, create a new task describing what needs to be resolved
   - Never mark a task as completed if:
     - Tests are failing
     - Implementation is partial
     - You encountered unresolved errors
     - You couldn't find necessary files or dependencies

4. **Task Breakdown**:
   - Create specific, actionable items
   - Break complex tasks into smaller, manageable steps
   - Use clear, descriptive task names
   - Always provide both forms:
     - content: "Fix authentication bug"
     - activeForm: "Fixing authentication bug"

When in doubt, use this tool. Being proactive with task management demonstrates attentiveness and ensures you complete all requirements successfully.
    """
    # Extract session ID from context (client_id is the session ID in MCP)
    # Architecture guarantee: tool_manager.py always injects _meta.client_id
    session_id = cast(str, context.client_id)

    try:
        # Get agent_profile from context_manager (set by Agent before tool execution)
        from backend.shared.utils.app_context import get_llm_client
        llm_client = get_llm_client()
        context_manager = llm_client.get_or_create_context_manager(session_id)
        agent_profile = getattr(context_manager, 'agent_profile', 'general')

        # Determine persistent flag based on agent_profile
        # SubAgents (pfc_explorer) use in-memory storage, MainAgents use local file storage
        persistent = agent_profile != 'pfc_explorer'

        # Get workspace directory based on agent profile
        workspace = await get_workspace_for_profile(agent_profile, session_id)

        # Validate "only one in_progress" rule (enforced at runtime)
        in_progress_count = sum(1 for todo in todos if todo.status == "in_progress")
        if in_progress_count > 1:
            return error_response(
                f"Only ONE task can be in_progress at a time (found {in_progress_count}). Please ensure exactly one task is marked as in_progress.",
                in_progress_count=in_progress_count
            )

        # Note: Pydantic automatically validates required fields (content, activeForm, status)
        # and status enum values. No need for manual validation.

        # Convert Pydantic models to dicts for storage (backward compatibility)
        todos_dict = [todo.model_dump() for todo in todos]

        # Auto-clear logic (Claude Code compatible):
        # If all todos are completed, automatically clear the list
        if todos_dict and all(todo.get("status") == "completed" for todo in todos_dict):
            logger.info(f"All {len(todos_dict)} todos completed - auto-clearing shared workspace list")
            todos_dict = []

        # Save todos to workspace (persistent) or memory (non-persistent)
        # MainAgent: persistent=True -> local file storage
        # SubAgent: persistent=False -> in-memory storage
        storage = get_todo_storage()
        storage.save_todos(workspace, session_id, todos_dict, persistent=persistent)

        # Build summary
        status_counts = {}
        for todo in todos:
            status = todo.status
            status_counts[status] = status_counts.get(status, 0) + 1

        summary_parts = []
        if status_counts.get("pending", 0) > 0:
            summary_parts.append(f"{status_counts['pending']} pending")
        if status_counts.get("in_progress", 0) > 0:
            summary_parts.append(f"{status_counts['in_progress']} in progress")
        if status_counts.get("completed", 0) > 0:
            summary_parts.append(f"{status_counts['completed']} completed")

        summary = ", ".join(summary_parts) if summary_parts else "no todos"

        # Return success response (Claude Code compatible)
        # Note: session_id and workspace are stored in data for debugging only,
        # they are NOT included in llm_content (LLM doesn't need internal details)
        return success_response(
            message=f"Todos have been modified successfully. Ensure that you continue to use the todo list to track your progress. Please proceed with the current tasks if applicable",
            llm_content={
                "parts": [{
                    "type": "text",
                    "text": f"Todo list updated successfully ({summary}). Ensure that you continue to use the todo list to track your progress. Please proceed with the current tasks if applicable."
                }]
            },
            todo_count=len(todos),
            status_breakdown=status_counts
        )

    except Exception as e:
        logger.error(f"Failed to save todos: {e}", exc_info=True)
        # Return generic error to LLM (detailed error logged for debugging)
        # Don't expose internal paths, session IDs, or implementation details
        return error_response(
            "Failed to save todo list due to an internal error. Please try again or contact support if the issue persists."
        )


# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_todo_write_tool(mcp: FastMCP):
    """Register the todo_write tool with comprehensive metadata."""
    mcp.tool(
        tags={"planning", "task-management", "todo", "workflow", "cross-session"},
        annotations={
            "category": "planning",
            "tags": ["planning", "task-management", "todo", "workflow", "cross-session"],
            "primary_use": "Create and manage structured task lists for multi-step workflows",
            "prompt_optimization": "Claude Code-compatible interface with cross-session persistence",
            "persistence": "Workspace-based storage with notified flag pattern for cross-session tracking"
        }
    )(todo_write)
