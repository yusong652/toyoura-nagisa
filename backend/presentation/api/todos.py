"""
Todo API - Endpoints for todo status retrieval.

Provides read-only access to todo status for frontend display.
"""

from fastapi import APIRouter, Query
from typing import Dict, Any, Optional

from backend.application.services.todo_service import get_todo_service

router = APIRouter(prefix="/api/todos", tags=["todos"])


@router.get("/current")
async def get_current_todo(
    session_id: str = Query(..., description="Session identifier")
) -> Dict[str, Any]:
    """
    Get the currently in-progress todo for display.

    This endpoint retrieves the first todo with status="in_progress" from
    the session's workspace, which is displayed in the frontend to show
    what the agent is currently working on.

    Args:
        session_id: Session identifier

    Returns:
        {
            "success": bool,
            "todo": {
                "todo_id": str,
                "content": str,          # Imperative form
                "activeForm": str,       # Present continuous form (for display)
                "status": str,
                "session_id": str,
                "created_at": float,
                "updated_at": float,
                "metadata": dict
            } | None,
            "message": str
        }
    """
    try:
        service = get_todo_service()
        todo = await service.get_current_todo(session_id)

        return {
            "success": True,
            "todo": todo,
            "message": "Current todo retrieved successfully" if todo else "No active todo"
        }

    except Exception as e:
        return {
            "success": False,
            "todo": None,
            "error": f"Failed to get current todo: {str(e)}"
        }


@router.get("/all")
async def get_all_todos(
    session_id: str = Query(..., description="Session identifier")
) -> Dict[str, Any]:
    """
    Get all todos for the session's workspace.

    Args:
        session_id: Session identifier

    Returns:
        {
            "success": bool,
            "todos": List[Dict],
            "count": int,
            "message": str
        }
    """
    try:
        service = get_todo_service()
        todos = await service.get_all_todos(session_id)

        return {
            "success": True,
            "todos": todos,
            "count": len(todos),
            "message": f"Retrieved {len(todos)} todo(s)"
        }

    except Exception as e:
        return {
            "success": False,
            "todos": [],
            "count": 0,
            "error": f"Failed to get todos: {str(e)}"
        }


@router.get("/pending")
async def get_pending_todos(
    session_id: str = Query(..., description="Session identifier"),
    limit: Optional[int] = Query(None, description="Maximum number of todos to return")
) -> Dict[str, Any]:
    """
    Get pending and in_progress todos.

    Args:
        session_id: Session identifier
        limit: Maximum number of todos to return

    Returns:
        {
            "success": bool,
            "todos": List[Dict],
            "count": int,
            "message": str
        }
    """
    try:
        service = get_todo_service()
        todos = await service.get_pending_todos(session_id, limit)

        return {
            "success": True,
            "todos": todos,
            "count": len(todos),
            "message": f"Retrieved {len(todos)} pending todo(s)"
        }

    except Exception as e:
        return {
            "success": False,
            "todos": [],
            "count": 0,
            "error": f"Failed to get pending todos: {str(e)}"
        }
