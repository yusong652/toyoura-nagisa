"""PFC task result enricher — injects local metadata into MCP query results.

When the LLM calls pfc_list_tasks or pfc_check_task_status, results come from
pfc-mcp and lack local metadata like git_commit.  This module enriches
those results by matching task_ids against the local PfcTaskManager.

Used as a transparent post-hook in ToolExecutor — the executor only calls
``should_enrich`` / ``enrich_pfc_result``; all matching logic lives here.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.infrastructure.pfc.task_manager import PfcTaskManager

_ENRICHABLE_TOOLS = frozenset({"pfc_list_tasks", "pfc_check_task_status"})


def should_enrich(tool_name: str) -> bool:
    return tool_name in _ENRICHABLE_TOOLS


def enrich_pfc_result(tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Inject git_commit from local PfcTask into MCP query results."""
    from backend.infrastructure.pfc.task_manager import get_pfc_task_manager

    task_manager = get_pfc_task_manager()
    if not task_manager.tasks:
        return result

    if tool_name == "pfc_check_task_status":
        _enrich_check_status(result, task_manager)
    elif tool_name == "pfc_list_tasks":
        _enrich_list_tasks(result, task_manager)
    return result


# ---- check_task_status ----


def _enrich_check_status(result: Dict[str, Any], tm: "PfcTaskManager") -> None:
    structured = _find_structured_content(result)
    task_id = structured.get("task_id") if structured else None
    if not task_id:
        return
    local = tm.get_task(task_id)
    if not local or not local.git_commit:
        return
    short_hash = local.git_commit[:7]
    if structured:
        structured["git_commit"] = short_hash


# ---- list_tasks ----


def _enrich_list_tasks(result: Dict[str, Any], tm: "PfcTaskManager") -> None:
    structured = _find_structured_content(result)
    tasks = structured.get("tasks") if structured else None
    if not isinstance(tasks, list):
        return
    for task in tasks:
        tid = task.get("task_id")
        if not tid:
            continue
        local = tm.get_task(tid)
        if local and local.git_commit:
            task["git_commit"] = local.git_commit[:7]


# ---- structured content navigation ----


def _find_structured_content(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Locate the structuredContent dict inside a ToolResult."""
    data = result.get("data")
    if not isinstance(data, dict):
        return None
    sc = data.get("structuredContent")
    if isinstance(sc, dict):
        return sc
    nested = data.get("data")
    if isinstance(nested, dict):
        sc = nested.get("structuredContent")
        if isinstance(sc, dict):
            return sc
    return None
