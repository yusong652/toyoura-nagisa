"""todo_write tool - persistent task tracking with cross-session awareness.

This tool implements Claude Code-compatible TodoWrite functionality, enabling LLMs to:
- Plan and track multi-step workflows
- Maintain task continuity across sessions
- Provide visibility into current progress
- Demonstrate thoroughness to users

Inspired by PFC task tracking's notified flag pattern for cross-session notifications.
"""

import logging
from typing import List, Dict, Any, Literal
from pydantic import BaseModel, Field
from fastmcp import FastMCP
from fastmcp.server.context import Context

from backend.infrastructure.mcp.utils.tool_result import ToolResult, success_response, error_response
from backend.infrastructure.storage.todo_storage import get_todo_storage
from backend.shared.utils.workspace import get_workspace_for_session_sync

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
        description="The updated todo list"
    )
) -> Dict[str, Any]:
    """Use this tool to create and manage a structured task list for your current coding session. This helps you track progress, organize complex tasks, and demonstrate thoroughness to the user.
It also helps the user understand the progress of the task and overall progress of their requests.

## When to Use This Tool
Use this tool proactively in these scenarios:

1. Complex multi-step tasks - When a task requires 3 or more distinct steps or actions
2. Non-trivial and complex tasks - Tasks that require careful planning or multiple operations
3. User explicitly requests todo list - When the user directly asks you to use the todo list
4. User provides multiple tasks - When users provide a list of things to be done (numbered or comma-separated)
5. After receiving new instructions - Immediately capture user requirements as todos
6. When you start working on a task - Mark it as in_progress BEFORE beginning work. Ideally you should only have one todo as in_progress at a time
7. After completing a task - Mark it as completed and add any new follow-up tasks discovered during implementation

## When NOT to Use This Tool

Skip using this tool when:
1. There is only a single, straightforward task
2. The task is trivial and tracking it provides no organizational benefit
3. The task can be completed in less than 3 trivial steps
4. The task is purely conversational or informational

NOTE that you should not use this tool if there is only one trivial task to do. In this case you are better off just doing the task directly.

## Examples of When to Use the Todo List

<example>
User: I want to add a dark mode toggle to the application settings. Make sure you run the tests and build when you're done!
Assistant: I'll help add a dark mode toggle to your application settings. Let me create a todo list to track this implementation.
*Creates todo list with the following items:*
1. Creating dark mode toggle component in Settings page
2. Adding dark mode state management (context/store)
3. Implementing CSS-in-JS styles for dark theme
4. Updating existing components to support theme switching
5. Running tests and build process, addressing any failures or errors that occur
*Begins working on the first task*

<reasoning>
The assistant used the todo list because:
1. Adding dark mode is a multi-step feature requiring UI, state management, and styling changes
2. The user explicitly requested tests and build be run afterward
3. The assistant inferred that tests and build need to pass by adding "Ensure tests and build succeed" as the final task
</reasoning>
</example>

<example>
User: Help me rename the function getCwd to getCurrentWorkingDirectory across my project
Assistant: Let me first search through your codebase to find all occurrences of 'getCwd'.
*Uses grep or search tools to locate all instances of getCwd in the codebase*
Assistant: I've found 15 instances of 'getCwd' across 8 different files. Let me create a todo list to track these changes.
*Creates todo list with specific items for each file that needs updating*

<reasoning>
The assistant used the todo list because:
1. First, the assistant searched to understand the scope of the task
2. Upon finding multiple occurrences across different files, it determined this was a complex task with multiple steps
3. The todo list helps ensure every instance is tracked and updated systematically
4. This approach prevents missing any occurrences and maintains code consistency
</reasoning>
</example>


<example>
User: I need to implement these features for my e-commerce site: user registration, product catalog, shopping cart, and checkout flow.
Assistant: I'll help implement these features. First, let's add all the features to the todo list.
*Creates a todo list breaking down each feature into specific tasks based on the project architecture*
Assistant: Let's start with user registration. This will involve creating database models, API endpoints, and frontend forms that integrate with your existing authentication system.

<reasoning>
The assistant used the todo list because:
1. The user provided multiple complex features to implement in a comma separated list
2. The todo list helps organize these large features into manageable tasks
3. This approach allows for tracking progress across the entire implementation
</reasoning>
</example>

## Examples of When NOT to Use the Todo List

<example>
User: How do I print 'Hello World' in Python?
Assistant: In Python, you can print "Hello World" with this simple code:

python
print("Hello World")

This will output the text "Hello World" to the console when executed.</assistant>

<reasoning>
The assistant did not use the todo list because this is a single, trivial task that can be completed in one step. There's no need to track multiple tasks or steps for such a straightforward request.
</reasoning>
</example>

<example>
User: What does the git status command do?
Assistant: The git status command shows the current state of your working directory and staging area. It displays which changes have been staged, which haven't, and which files aren't being tracked by Git. This is a fundamental command for understanding the current state of your repository before making commits.

<reasoning>
The assistant did not use the todo list because this is an informational request with no actual coding task to complete. The user is simply asking for an explanation, not for the assistant to perform multiple steps or tasks.
</reasoning>
</example>

<example>
User: Can you add a comment to the calculateTotal function to explain what it does?
Assistant: Sure, let me add a comment to the calculateTotal function to explain what it does.
* Uses the Edit tool to add a comment to the calculateTotal function *

<reasoning>
The assistant did not use the todo list because this is a single, straightforward task confined to one location in the code. Adding a comment doesn't require tracking multiple steps or systematic organization.
</reasoning>
</example>

<example>
User: Run npm install for me and tell me what happens.
Assistant: I'll run the npm install command for you.

*Executes: npm install*

The command completed successfully. Here's the output:
[Output of npm install command]

All dependencies have been installed according to your package.json file.

<reasoning>
The assistant did not use the todo list because this is a single command execution with immediate results. There are no multiple steps to track or organize, making the todo list unnecessary for this straightforward task.
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
    session_id = context.client_id
    if not session_id:
        # Infrastructure error - raise exception for system-level handling
        # This should never happen in normal operation (backend configuration issue)
        raise RuntimeError("Session ID not found in context - backend configuration error")

    try:

        # Get workspace directory for this session
        workspace = get_workspace_for_session_sync(session_id)

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

        # Save todos (full replacement pattern - same as Claude Code)
        storage = get_todo_storage()
        storage.save_todos(workspace, session_id, todos_dict)

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
            llm_content=f"Todo list updated successfully ({summary}). Ensure that you continue to use the todo list to track your progress. Please proceed with the current tasks if applicable.",
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
