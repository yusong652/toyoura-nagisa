import importlib
from unittest.mock import AsyncMock

import pytest

from backend.application.tools.context import ToolContext, ToolRequestContext, ToolRequestMeta

grep_module = importlib.import_module("backend.application.tools.coding.grep")
grep = grep_module.grep


def _make_context(session_id: str = "session-1") -> ToolContext:
    return ToolContext(
        client_id=session_id,
        request_context=ToolRequestContext(
            meta=ToolRequestMeta(client_id=session_id, tool_call_id="tool-call-1")
        ),
    )


async def _run_grep(context: ToolContext, **overrides):
    params = {
        "pattern": "needle",
        "path": ".",
        "glob": None,
        "type": None,
        "output_mode": "files_with_matches",
        "case_insensitive": False,
        "show_line_numbers": False,
        "context_after": None,
        "context_before": None,
        "context_both": None,
        "head_limit": None,
    }
    params.update(overrides)
    return await grep(context, **params)


@pytest.mark.asyncio
async def test_grep_defaults_to_workspace_root(monkeypatch, tmp_path):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True)
    top_level = workspace_root / "match.py"
    nested = workspace_root / "src" / "inside.py"
    top_level.write_text("needle = 1\n", encoding="utf-8")
    (workspace_root / "src").mkdir()
    nested.write_text("needle = 2\n", encoding="utf-8")

    monkeypatch.setattr(
        grep_module,
        "get_workspace_root_async",
        AsyncMock(return_value=workspace_root),
    )

    result = await _run_grep(_make_context())

    assert result["status"] == "success"
    assert result["data"]["files"] == [
        str(top_level.resolve()).replace("\\", "/"),
        str(nested.resolve()).replace("\\", "/"),
    ]


@pytest.mark.asyncio
async def test_grep_resolves_relative_paths_from_workspace_root(monkeypatch, tmp_path):
    workspace_root = tmp_path / "workspace"
    nested_dir = workspace_root / "nested"
    nested_dir.mkdir(parents=True)
    (nested_dir / "target.py").write_text("needle = 1\n", encoding="utf-8")
    (workspace_root / "src").mkdir()
    (workspace_root / "src" / "outside.py").write_text("needle = 2\n", encoding="utf-8")

    monkeypatch.setattr(
        grep_module,
        "get_workspace_root_async",
        AsyncMock(return_value=workspace_root),
    )

    result = await _run_grep(_make_context(), path="nested")

    assert result["status"] == "success"
    assert result["data"]["files"] == [str((nested_dir / "target.py").resolve()).replace("\\", "/")]
