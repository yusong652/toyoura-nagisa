"""PFC task result enricher — injects local metadata into MCP query results.

When the LLM calls pfc_list_tasks or pfc_check_task_status, results come from
pfc-mcp and lack local metadata like git_commit.  This module enriches
those results by matching task_ids against the local PfcTaskManager.

Used as a transparent post-hook in ToolExecutor — the executor only calls
``should_enrich`` / ``enrich_pfc_result``; all matching logic lives here.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

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
    _append_display_line(result, f"- git_commit: {short_hash}", after_pattern=r"^- checked:")


# ---- list_tasks ----


def _enrich_list_tasks(result: Dict[str, Any], tm: "PfcTaskManager") -> None:
    structured = _find_structured_content(result)
    tasks = structured.get("tasks") if structured else None
    if not isinstance(tasks, list):
        return
    additions: List[Tuple[str, str]] = []
    for task in tasks:
        tid = task.get("task_id")
        if not tid:
            continue
        local = tm.get_task(tid)
        if local and local.git_commit:
            short_hash = local.git_commit[:7]
            task["git_commit"] = short_hash
            additions.append((tid, short_hash))
    if additions:
        _enrich_list_display(result, additions)


# ---- display helpers ----


def _append_display_line(result: Dict[str, Any], line: str, after_pattern: str) -> None:
    """Insert *line* after the first display line matching *after_pattern*."""
    text = _get_display_text(result)
    if not text:
        return
    lines = text.split("\n")
    for i, existing in enumerate(lines):
        if re.match(after_pattern, existing.strip()):
            lines.insert(i + 1, line)
            _set_display_text(result, "\n".join(lines))
            return
    lines.append(line)
    _set_display_text(result, "\n".join(lines))


def _enrich_list_display(result: Dict[str, Any], additions: List[Tuple[str, str]]) -> None:
    """Append git_commit line after each matching task's description line."""
    text = _get_display_text(result)
    if not text:
        return
    tid_to_hash = dict(additions)
    lines = text.split("\n")
    enriched: List[str] = []
    pending_hash: Optional[str] = None
    for line in lines:
        enriched.append(line)
        # Detect task header line: "- task_id=xxx ..."
        stripped = line.strip()
        if stripped.startswith("- task_id="):
            tid = stripped.split()[0].split("=", 1)[1] if "=" in stripped else None
            pending_hash = tid_to_hash.get(tid) if tid else None
        # Insert after description= line
        elif pending_hash and stripped.startswith("description="):
            enriched.append(f"  git_commit={pending_hash}")
            pending_hash = None
    _set_display_text(result, "\n".join(enriched))


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


def _get_display_text(result: Dict[str, Any]) -> Optional[str]:
    """Get display text, preferring structured display over llm_content."""
    structured = _find_structured_content(result)
    if isinstance(structured, dict):
        display = structured.get("display")
        if isinstance(display, str) and display:
            return display

    llm = result.get("llm_content")
    if isinstance(llm, dict):
        parts = llm.get("parts")
        if isinstance(parts, list) and parts:
            return parts[0].get("text")
    return None


def _set_display_text(result: Dict[str, Any], text: str) -> None:
    """Set display text in structured payload and mirror it to llm_content."""
    structured = _find_structured_content(result)
    if isinstance(structured, dict):
        structured["display"] = text

    llm = result.get("llm_content")
    if isinstance(llm, dict):
        parts = llm.get("parts")
        if isinstance(parts, list):
            if parts:
                parts[0]["text"] = text
            else:
                parts.append({"type": "text", "text": text})
    else:
        result["llm_content"] = {"parts": [{"type": "text", "text": text}]}
