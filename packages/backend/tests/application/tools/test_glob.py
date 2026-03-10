import importlib

import pytest

from unittest.mock import AsyncMock

from backend.application.tools.context import ToolContext, ToolRequestContext, ToolRequestMeta

glob_module = importlib.import_module("backend.application.tools.coding.glob")
glob = glob_module.glob


def _make_context(session_id: str = "session-1") -> ToolContext:
    return ToolContext(
        client_id=session_id,
        request_context=ToolRequestContext(
            meta=ToolRequestMeta(client_id=session_id, tool_call_id="tool-call-1")
        ),
    )


@pytest.mark.asyncio
async def test_glob_defaults_to_workspace_root(monkeypatch, tmp_path):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True)
    target = workspace_root / "match.py"
    target.write_text("x = 1\n", encoding="utf-8")
    (workspace_root / "src").mkdir()
    (workspace_root / "src" / "outside.py").write_text("x = 2\n", encoding="utf-8")

    monkeypatch.setattr(
        glob_module,
        "get_workspace_root_async",
        AsyncMock(return_value=workspace_root),
    )

    result = await glob(_make_context(), pattern="*.py", path=".")

    assert result["status"] == "success"
    assert result["data"]["files"] == [str(target.resolve()).replace("\\", "/")]


@pytest.mark.asyncio
async def test_glob_resolves_relative_paths_from_workspace_root(monkeypatch, tmp_path):
    workspace_root = tmp_path / "workspace"
    nested_dir = workspace_root / "nested"
    nested_dir.mkdir(parents=True)
    target = nested_dir / "match.py"
    target.write_text("x = 1\n", encoding="utf-8")
    (workspace_root / "src").mkdir()
    (workspace_root / "src" / "outside.py").write_text("x = 2\n", encoding="utf-8")

    monkeypatch.setattr(
        glob_module,
        "get_workspace_root_async",
        AsyncMock(return_value=workspace_root),
    )

    result = await glob(_make_context(), pattern="*.py", path="nested")

    assert result["status"] == "success"
    assert result["data"]["files"] == [str(target.resolve()).replace("\\", "/")]
