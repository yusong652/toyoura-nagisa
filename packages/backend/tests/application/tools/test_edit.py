import importlib
from unittest.mock import AsyncMock

import pytest

from backend.application.tools.context import ToolContext, ToolRequestContext, ToolRequestMeta

edit_module = importlib.import_module("backend.application.tools.coding.edit")
edit = edit_module.edit


def _make_context(session_id: str = "session-1") -> ToolContext:
    return ToolContext(
        client_id=session_id,
        request_context=ToolRequestContext(
            meta=ToolRequestMeta(client_id=session_id, tool_call_id="tool-call-1")
        ),
    )


@pytest.mark.asyncio
async def test_edit_resolves_relative_paths_from_workspace_root(monkeypatch, tmp_path):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True)
    target = workspace_root / "nested" / "example.py"
    target.parent.mkdir(parents=True)
    target.write_text("value = 1\n", encoding="utf-8")

    monkeypatch.setattr(
        edit_module,
        "get_workspace_root_async",
        AsyncMock(return_value=workspace_root),
    )

    result = await edit(
        _make_context(),
        path="nested/example.py",
        old_string="value = 1",
        new_string="value = 2",
        replace_all=False,
    )

    assert result["status"] == "success"
    assert target.read_text(encoding="utf-8") == "value = 2\n"
    assert result["data"]["diff"]["file_path"] == str(target.resolve()).replace("\\", "/")


@pytest.mark.asyncio
async def test_edit_rejects_paths_outside_workspace(monkeypatch, tmp_path):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True)
    outside = tmp_path / "outside.py"
    outside.write_text("value = 1\n", encoding="utf-8")

    monkeypatch.setattr(
        edit_module,
        "get_workspace_root_async",
        AsyncMock(return_value=workspace_root),
    )

    result = await edit(
        _make_context(),
        path=str(outside),
        old_string="value = 1",
        new_string="value = 2",
        replace_all=False,
    )

    assert result["status"] == "error"
    assert result["message"] == f"File path is outside workspace: {outside}"
