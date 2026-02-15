import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from backend.infrastructure.mcp.client import MCPClient
from backend.infrastructure.mcp.config import load_mcp_configs
from backend.infrastructure.mcp.models import MCPServerConfig


def _write_config(config_path: Path, payload: dict) -> None:
    config_path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_mcp_configs_resolves_cwd_relative_to_config_file(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    target_dir = tmp_path / "pfc-mcp"
    target_dir.mkdir()

    config_path = config_dir / "mcp.json"
    _write_config(
        config_path,
        {
            "mcpServers": {
                "pfc-mcp": {
                    "command": "uv",
                    "args": ["run", "pfc-mcp"],
                    "cwd": "../pfc-mcp",
                }
            }
        },
    )

    configs = load_mcp_configs(config_path=str(config_path))
    assert len(configs) == 1
    assert configs[0].cwd == str(target_dir.resolve())


def test_load_mcp_configs_expands_cwd_env_var(monkeypatch, tmp_path):
    target_dir = tmp_path / "pfc-mcp"
    target_dir.mkdir()
    monkeypatch.setenv("PFC_MCP_ROOT", str(target_dir))

    config_path = tmp_path / "mcp.json"
    _write_config(
        config_path,
        {
            "mcpServers": {
                "pfc-mcp": {
                    "command": "uv",
                    "args": ["run", "pfc-mcp"],
                    "cwd": "${PFC_MCP_ROOT}",
                }
            }
        },
    )

    configs = load_mcp_configs(config_path=str(config_path))
    assert len(configs) == 1
    assert configs[0].cwd == str(target_dir.resolve())


def test_load_mcp_configs_marks_missing_cwd_env_var(monkeypatch, tmp_path):
    monkeypatch.delenv("PFC_MCP_ROOT", raising=False)

    config_path = tmp_path / "mcp.json"
    _write_config(
        config_path,
        {
            "mcpServers": {
                "pfc-mcp": {
                    "command": "uv",
                    "args": ["run", "pfc-mcp"],
                    "cwd": "${PFC_MCP_ROOT}",
                }
            }
        },
    )

    configs = load_mcp_configs(config_path=str(config_path))
    assert len(configs) == 1
    assert configs[0].cwd is None
    assert "PFC_MCP_ROOT" in configs[0].missing_env_vars


@pytest.mark.asyncio
async def test_mcp_client_passes_cwd_to_stdio_server_parameters(monkeypatch):
    captured = {}

    def fake_stdio_client(server_params):
        captured["server_params"] = server_params

        class _DummyStdioContext:
            async def __aenter__(self):
                return object(), object()

            async def __aexit__(self, exc_type, exc, tb):
                return None

        return _DummyStdioContext()

    class _DummySessionContext:
        def __init__(self, read_stream, write_stream):
            self._session = type("DummySession", (), {"initialize": AsyncMock()})()

        async def __aenter__(self):
            return self._session

        async def __aexit__(self, exc_type, exc, tb):
            return None

    monkeypatch.setattr("backend.infrastructure.mcp.client.stdio_client", fake_stdio_client)
    monkeypatch.setattr("backend.infrastructure.mcp.client.ClientSession", _DummySessionContext)

    config = MCPServerConfig(
        name="pfc-mcp",
        command="uv",
        args=["run", "pfc-mcp"],
        cwd=str(Path.cwd()),
    )
    client = MCPClient(config)
    monkeypatch.setattr(client, "_load_tools", AsyncMock())

    connected = await client.connect()
    assert connected is True
    assert captured["server_params"].cwd == config.cwd
