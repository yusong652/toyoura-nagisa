"""
Todo API (2025 Standard).

Provides read-only access to todo status for frontend display.
All endpoints require explicit agent_profile parameter for workspace resolution.

Routes:
    GET /api/todos/current  - Get current in-progress todo
    GET /api/todos          - List all todos
    GET /api/todos/pending  - List pending/in-progress todos
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from backend.presentation.models.api_models import ApiResponse
from backend.presentation.exceptions import InternalServerError
from backend.application.todo.service import get_todo_service

router = APIRouter(prefix="/api/todos", tags=["todos"])


# =====================
# Response Data Models
# =====================
class TodoItem(BaseModel):
    """Todo item structure."""
    todo_id: Optional[str] = Field(default=None, description="Todo identifier")
    content: str = Field(..., description="Imperative form of the task")
    activeForm: str = Field(..., description="Present continuous form (for display)")
    status: str = Field(..., description="Todo status: pending, in_progress, completed")
    session_id: Optional[str] = Field(default=None, description="Session identifier")
    created_at: Optional[float] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[float] = Field(default=None, description="Last update timestamp")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class CurrentTodoData(BaseModel):
    """Response data for current todo."""
    todo: Optional[TodoItem] = Field(default=None, description="Current in-progress todo")


class TodoListData(BaseModel):
    """Response data for todo list."""
    todos: List[TodoItem] = Field(..., description="List of todos")
    count: int = Field(..., description="Total count")


# =====================
# API Endpoints
# =====================
@router.get("/current", response_model=ApiResponse[CurrentTodoData])
async def get_current_todo(
    agent_profile: str = Query(..., description="Agent profile for workspace resolution"),
    session_id: Optional[str] = Query(default=None, description="Session identifier")
) -> ApiResponse[CurrentTodoData]:
    """Get the currently in-progress todo for display.

    Retrieves the first todo with status="in_progress" from the workspace,
    displayed in the frontend to show what the agent is currently working on.
    """
    try:
        service = get_todo_service()
        todo_dict = await service.get_current_todo(agent_profile, session_id)

        todo = TodoItem(**todo_dict) if todo_dict else None

        return ApiResponse(
            success=True,
            message="Current todo retrieved" if todo else "No active todo",
            data=CurrentTodoData(todo=todo)
        )
    except Exception as e:
        raise InternalServerError(
            message=f"Failed to get current todo: {str(e)}"
        )


@router.get("", response_model=ApiResponse[TodoListData])
async def get_all_todos(
    agent_profile: str = Query(..., description="Agent profile for workspace resolution"),
    session_id: Optional[str] = Query(default=None, description="Session identifier")
) -> ApiResponse[TodoListData]:
    """Get all todos for the workspace."""
    try:
        service = get_todo_service()
        todo_dicts = await service.get_all_todos(agent_profile, session_id)

        todos = [TodoItem(**t) for t in todo_dicts]

        return ApiResponse(
            success=True,
            message=f"Retrieved {len(todos)} todo(s)",
            data=TodoListData(todos=todos, count=len(todos))
        )
    except Exception as e:
        raise InternalServerError(
            message=f"Failed to get todos: {str(e)}"
        )


@router.get("/pending", response_model=ApiResponse[TodoListData])
async def get_pending_todos(
    agent_profile: str = Query(..., description="Agent profile for workspace resolution"),
    session_id: Optional[str] = Query(default=None, description="Session identifier"),
    limit: Optional[int] = Query(default=None, description="Maximum number of todos")
) -> ApiResponse[TodoListData]:
    """Get pending and in_progress todos."""
    try:
        service = get_todo_service()
        todo_dicts = await service.get_pending_todos(agent_profile, session_id, limit)

        todos = [TodoItem(**t) for t in todo_dicts]

        return ApiResponse(
            success=True,
            message=f"Retrieved {len(todos)} pending todo(s)",
            data=TodoListData(todos=todos, count=len(todos))
        )
    except Exception as e:
        raise InternalServerError(
            message=f"Failed to get pending todos: {str(e)}"
        )


# =====================
# Legacy Routes (deprecated)
# =====================
@router.get("/all", response_model=ApiResponse[TodoListData], deprecated=True)
async def get_all_todos_legacy(
    agent_profile: str = Query(..., description="Agent profile"),
    session_id: Optional[str] = Query(default=None, description="Session identifier")
) -> ApiResponse[TodoListData]:
    """[DEPRECATED] Use GET /api/todos instead."""
    return await get_all_todos(agent_profile, session_id)
