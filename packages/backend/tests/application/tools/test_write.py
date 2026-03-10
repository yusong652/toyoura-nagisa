import importlib
from unittest.mock import AsyncMock

import pytest

from backend.application.tools.context import ToolContext, ToolRequestContext, ToolRequestMeta

write_module = importlib.import_module("backend.application.tools.coding.write")
write = write_module.write


def _make_context(session_id: str = "session-1") -> ToolContext:
    return ToolContext(
        client_id=session_id,
        request_context=ToolRequestContext(
            meta=ToolRequestMeta(client_id=session_id, tool_call_id="tool-call-1")
        ),
    )


@pytest.mark.asyncio
async def test_write_resolves_relative_paths_from_workspace_root(monkeypatch, tmp_path):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True)

    monkeypatch.setattr(
        write_module,
        "get_workspace_root_async",
        AsyncMock(return_value=workspace_root),
    )

    result = await write(_make_context(), path="nested/output.txt", content="hello\n")
    target = workspace_root / "nested" / "output.txt"

    assert result["status"] == "success"
    assert target.read_text(encoding="utf-8") == "hello\n"
    assert result["data"]["file_path"] == str(target.resolve()).replace("\\", "/")


@pytest.mark.asyncio
async def test_write_rejects_paths_outside_workspace(monkeypatch, tmp_path):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True)
    outside = tmp_path / "outside.txt"

    monkeypatch.setattr(
        write_module,
        "get_workspace_root_async",
        AsyncMock(return_value=workspace_root),
    )

    result = await write(_make_context(), path=str(outside), content="hello\n")

    assert result["status"] == "error"
    assert result["message"] == f"Path is outside of workspace: {outside}"
