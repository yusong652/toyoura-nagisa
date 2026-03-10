import importlib
from unittest.mock import AsyncMock

import pytest

from backend.application.tools.context import ToolContext, ToolRequestContext, ToolRequestMeta

read_module = importlib.import_module("backend.application.tools.coding.read")
read = read_module.read


def _make_context(session_id: str = "session-1") -> ToolContext:
    return ToolContext(
        client_id=session_id,
        request_context=ToolRequestContext(
            meta=ToolRequestMeta(client_id=session_id, tool_call_id="tool-call-1")
        ),
    )


@pytest.mark.asyncio
async def test_read_resolves_relative_paths_from_workspace_root(monkeypatch, tmp_path):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True)
    target = workspace_root / "target.txt"
    target.write_text("hello\n", encoding="utf-8")

    monkeypatch.setattr(
        read_module,
        "get_workspace_root_async",
        AsyncMock(return_value=workspace_root),
    )

    result = await read(_make_context(), path="target.txt", offset=None, limit=None)

    assert result["status"] == "success"
    assert result["data"]["file_path"] == str(target.resolve()).replace("\\", "/")
