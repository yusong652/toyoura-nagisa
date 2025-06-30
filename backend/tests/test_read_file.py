import os
import base64
from pathlib import Path

import pytest

from backend.nagisa_mcp.tools.coding.tools.read_file import read_file
from backend.nagisa_mcp.tools.coding.tools.workspace import DEFAULT_WORKSPACE


@pytest.fixture()
def tmp_workspace(tmp_path: Path, monkeypatch):
    # Point DEFAULT_WORKSPACE to a fresh temp dir
    test_dir = tmp_path / "ws"
    test_dir.mkdir()
    monkeypatch.setattr(
        "backend.nagisa_mcp.tools.coding.tools.workspace.DEFAULT_WORKSPACE", str(test_dir), raising=False
    )
    return test_dir


def test_read_text_file(tmp_workspace: Path):
    f = tmp_workspace / "hello.txt"
    f.write_text("hello world")
    result = read_file(path=str(f.relative_to(tmp_workspace)))
    assert result["status"] == "success"
    assert result["content"].startswith("hello")


def test_read_binary_inline(tmp_workspace: Path):
    img = tmp_workspace / "img.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
    result = read_file(path=str(img))
    assert result["status"] == "success"
    assert "inline_data" in result
    data = result["inline_data"]["data"]
    assert base64.b64decode(data)[:4] == b"\x89PNG"


def test_offset_limit(tmp_workspace: Path):
    f = tmp_workspace / "long.txt"
    f.write_text("abcdefghij")
    result = read_file(path=str(f), offset=2, limit=3)
    assert result["content"] == "cde"


def test_outside_workspace(tmp_workspace: Path):
    outside = tmp_workspace.parent / "oops.txt"
    outside.write_text("nope")
    result = read_file(path=str(outside))
    assert "error" in result 