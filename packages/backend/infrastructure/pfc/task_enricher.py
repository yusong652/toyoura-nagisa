"""PFC task result enricher - injects local metadata into MCP query results.

When the LLM calls pfc_list_tasks or pfc_check_task_status, results come from
pfc-mcp and lack local metadata like git_commit. This module enriches
those results by matching task_ids against the local PfcTaskManager.

Used as a transparent post-hook in ToolExecutor - the executor only calls
``should_enrich`` / ``enrich_pfc_result``; all matching logic lives here.
"""

from __future__ import annotations

import re
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
    payload = _find_structured_payload(result)
    task_id = payload.get("task_id") if payload else None
    if not task_id:
        return
    local = tm.get_task(task_id)
    if not local or not local.git_commit:
        return
    short_hash = local.git_commit[:7]
    payload["git_commit"] = short_hash
    _inject_check_status_text(result, task_id, short_hash)


# ---- list_tasks ----


def _enrich_list_tasks(result: Dict[str, Any], tm: "PfcTaskManager") -> None:
    payload = _find_structured_payload(result)
    tasks = payload.get("tasks") if payload else None
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


def _find_structured_payload(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Locate pfc-mcp payload data inside a ToolResult (envelope + legacy)."""
    data = result.get("data")
    if not isinstance(data, dict):
        return None

    structured = data.get("structuredContent")
    if not isinstance(structured, dict):
        nested = data.get("data")
        if isinstance(nested, dict):
            structured = nested.get("structuredContent")

    if not isinstance(structured, dict):
        return None

    # New envelope format: {"ok": true, "data": {...}}
    if structured.get("ok") is True:
        payload = structured.get("data")
        return payload if isinstance(payload, dict) else None

    # Legacy format: payload is at top-level structuredContent
    if isinstance(structured.get("task_id"), str) or isinstance(structured.get("tasks"), list):
        return structured

    nested = structured.get("data")
    if isinstance(nested, dict):
        if isinstance(nested.get("task_id"), str) or isinstance(nested.get("tasks"), list):
            return nested

    return None


def _inject_check_status_text(result: Dict[str, Any], task_id: str, git_commit: str) -> None:
    """Inject git_commit into human-readable text shown to the model."""
    llm_content = result.get("llm_content")
    if isinstance(llm_content, dict):
        parts = llm_content.get("parts")
        if isinstance(parts, list):
            _inject_git_commit_into_parts(parts, task_id, git_commit)

    # Also patch MCP text content kept in result.data for UI/debug consistency.
    data = result.get("data")
    if isinstance(data, dict):
        content = data.get("content")
        if isinstance(content, list):
            _inject_git_commit_into_parts(content, task_id, git_commit)


def _inject_git_commit_into_parts(parts: list[dict[str, Any]], task_id: str, git_commit: str) -> None:
    for part in parts:
        if not isinstance(part, dict) or part.get("type") != "text":
            continue
        text = part.get("text")
        if not isinstance(text, str):
            continue
        updated = _inject_git_commit_into_text(text, task_id, git_commit)
        if updated != text:
            part["text"] = updated
            return


def _inject_git_commit_into_text(text: str, task_id: str, git_commit: str) -> str:
    if "git_commit" in text.lower():
        return text
    if task_id not in text:
        return text

    lines = text.splitlines()
    task_line_pattern = re.compile(rf"^\s*-\s*task_id:\s*{re.escape(task_id)}\s*$", re.IGNORECASE)
    for idx, line in enumerate(lines):
        if task_line_pattern.match(line):
            lines.insert(idx + 1, f"- git_commit: {git_commit}")
            return "\n".join(lines)

    return f"{text.rstrip()}\n- git_commit: {git_commit}"
