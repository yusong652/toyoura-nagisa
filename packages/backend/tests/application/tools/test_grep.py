import importlib
from unittest.mock import AsyncMock

import pytest

from backend.application.tools.context import ToolContext, ToolRequestContext, ToolRequestMeta

grep_module = importlib.import_module("backend.application.tools.coding.grep")
grep = grep_module.grep


class _FakeRgProc:
    """Mimic asyncio.subprocess.Process for ripgrep output."""

    def __init__(self, stdout: bytes, returncode: int = 0, stderr: bytes = b""):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode

    async def communicate(self):
        return self._stdout, self._stderr


def _fake_create_subprocess_exec(stdout: bytes, returncode: int = 0, stderr: bytes = b""):
    async def _factory(*args, **kwargs):
        return _FakeRgProc(stdout, returncode, stderr)
    return _factory


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
    # Compare as a set: rg (parallel) and the Python walker return files
    # in different orders; grep has no ordering contract.
    assert set(result["data"]["files"]) == {
        str(top_level.resolve()).replace("\\", "/"),
        str(nested.resolve()).replace("\\", "/"),
    }


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


@pytest.mark.asyncio
async def test_grep_uses_ripgrep_when_available(monkeypatch, tmp_path):
    """When RG_PATH is set, grep should shell out to rg and parse its output."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True)
    (workspace_root / "a.py").write_text("needle\n", encoding="utf-8")
    (workspace_root / "b.py").write_text("other\n", encoding="utf-8")

    monkeypatch.setattr(
        grep_module,
        "get_workspace_root_async",
        AsyncMock(return_value=workspace_root),
    )
    monkeypatch.setattr(grep_module, "RG_PATH", "/fake/rg")

    # rg -l output with -0: "<path>\0\n" per match
    stdout = f"{workspace_root / 'a.py'}\0\n".encode()
    monkeypatch.setattr(
        "asyncio.create_subprocess_exec",
        _fake_create_subprocess_exec(stdout, returncode=0),
    )

    result = await _run_grep(_make_context())
    assert result["status"] == "success"
    assert result["data"]["total_files"] == 1
    assert result["data"]["files"][0].endswith("/a.py")


@pytest.mark.asyncio
async def test_grep_falls_back_when_ripgrep_regex_incompatible(monkeypatch, tmp_path):
    """rg exit 2 with regex-parse-error should fall back to Python engine."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True)
    (workspace_root / "a.py").write_text("python-only\n", encoding="utf-8")

    monkeypatch.setattr(
        grep_module,
        "get_workspace_root_async",
        AsyncMock(return_value=workspace_root),
    )
    monkeypatch.setattr(grep_module, "RG_PATH", "/fake/rg")
    monkeypatch.setattr(
        "asyncio.create_subprocess_exec",
        _fake_create_subprocess_exec(b"", returncode=2, stderr=b"regex parse error: ..."),
    )

    result = await _run_grep(_make_context(), pattern="python-only")
    # Fallback Python walker should have found the match.
    assert result["status"] == "success"
    assert result["data"]["total_files"] == 1


@pytest.mark.asyncio
async def test_grep_content_mode_parses_rg_line_numbers(monkeypatch, tmp_path):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True)
    monkeypatch.setattr(
        grep_module,
        "get_workspace_root_async",
        AsyncMock(return_value=workspace_root),
    )
    monkeypatch.setattr(grep_module, "RG_PATH", "/fake/rg")

    path = workspace_root / "x.py"
    stdout = (
        f"{path}\x0012:match one\n"
        f"{path}\x0034:match two\n"
    ).encode()
    monkeypatch.setattr(
        "asyncio.create_subprocess_exec",
        _fake_create_subprocess_exec(stdout, returncode=0),
    )

    result = await _run_grep(
        _make_context(),
        output_mode="content",
        show_line_numbers=True,
    )
    assert result["status"] == "success"
    content = result["data"]["content"]
    assert any("12:match one" in line for line in content)
    assert any("34:match two" in line for line in content)
