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


@pytest.mark.asyncio
async def test_glob_respects_gitignore(monkeypatch, tmp_path):
    """Files ignored by .gitignore should be skipped for recursive (`**`) patterns."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True)
    # Mark this as a repo root so .gitignore loading stops here
    (workspace_root / ".git").mkdir()
    (workspace_root / ".gitignore").write_text("ignored/\nsecret.py\n", encoding="utf-8")

    visible = workspace_root / "pkg" / "visible.py"
    visible.parent.mkdir()
    visible.write_text("x\n", encoding="utf-8")

    hidden_dir = workspace_root / "ignored"
    hidden_dir.mkdir()
    (hidden_dir / "nope.py").write_text("x\n", encoding="utf-8")

    secret = workspace_root / "secret.py"
    secret.write_text("x\n", encoding="utf-8")

    monkeypatch.setattr(
        glob_module,
        "get_workspace_root_async",
        AsyncMock(return_value=workspace_root),
    )

    result = await glob(_make_context(), pattern="**/*.py", path=".")

    assert result["status"] == "success"
    files = result["data"]["files"]
    assert any(f.endswith("/pkg/visible.py") for f in files)
    assert not any("ignored/" in f for f in files)
    assert not any(f.endswith("/secret.py") for f in files)


@pytest.mark.asyncio
async def test_glob_prunes_heavy_dirs(monkeypatch, tmp_path):
    """Hard-coded prune list should skip node_modules, .git, etc."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True)
    good = workspace_root / "src" / "a.py"
    good.parent.mkdir()
    good.write_text("x\n", encoding="utf-8")

    for noisy in (".git", "node_modules", "__pycache__"):
        (workspace_root / noisy).mkdir()
        (workspace_root / noisy / "buried.py").write_text("x\n", encoding="utf-8")

    monkeypatch.setattr(
        glob_module,
        "get_workspace_root_async",
        AsyncMock(return_value=workspace_root),
    )

    result = await glob(_make_context(), pattern="**/*.py", path=".")
    assert result["status"] == "success"
    files = result["data"]["files"]
    assert any(f.endswith("/src/a.py") for f in files)
    for noisy in (".git", "node_modules", "__pycache__"):
        assert not any(f"/{noisy}/" in f for f in files)
