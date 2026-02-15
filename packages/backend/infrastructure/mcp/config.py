"""
MCP configuration loading and parsing.

This module handles loading MCP server configurations from JSON config files,
environment variable expansion, and config file discovery.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
from pathlib import Path
from typing import Any

from .manager import (
    MCPClientManager,
    get_mcp_client_manager,
    initialize_mcp_clients,
    shutdown_mcp_clients,
)
from .client import MCPClient
from .models import MCPServerConfig, MCPTool

logger = logging.getLogger(__name__)
ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")
NAGISA_CONFIG_DIR = ".nagisa"
MCP_CONFIG_FILENAME = "mcp.json"


def _find_missing_env_vars(value: str) -> set[str]:
    """Find env vars referenced by ${VAR_NAME} that are unset or empty."""
    missing_vars: set[str] = set()
    for match in ENV_VAR_PATTERN.finditer(value):
        var_name = match.group(1)
        if not os.getenv(var_name):
            missing_vars.add(var_name)
    return missing_vars


def _expand_env_vars(value: str) -> str:
    """Expand ${VAR_NAME} patterns with environment variables."""

    def replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        return os.getenv(var_name, "")

    return ENV_VAR_PATTERN.sub(replace, value)


def _parse_args(args_raw: Any) -> tuple[list[str], set[str]]:
    """Parse and expand args from raw config value."""
    args_list = args_raw if isinstance(args_raw, list) else []
    missing_env_vars: set[str] = set()

    for arg in args_list:
        if isinstance(arg, str):
            missing_env_vars.update(_find_missing_env_vars(arg))

    args = [_expand_env_vars(arg) for arg in args_list if isinstance(arg, str)]
    args = [arg for arg in args if arg]
    return args, missing_env_vars


def _parse_command_and_args(command_raw: Any, args_raw: Any) -> tuple[str, list[str], set[str]]:
    """Parse command and args.

    Supported forms:
    - command: "uvx", args: ["pfc-mcp"]
    - command: "uvx pfc-mcp" (args omitted, split by whitespace)
    - server value shorthand: "uvx pfc-mcp"
    """
    missing_env_vars: set[str] = set()

    parsed_args, missing_in_args = _parse_args(args_raw)
    missing_env_vars.update(missing_in_args)

    if not isinstance(command_raw, str):
        return "", parsed_args, missing_env_vars

    missing_env_vars.update(_find_missing_env_vars(command_raw))
    rendered_command = _expand_env_vars(command_raw).strip()
    if not rendered_command:
        return "", parsed_args, missing_env_vars

    if isinstance(args_raw, list):
        return rendered_command, parsed_args, missing_env_vars

    try:
        tokens = shlex.split(rendered_command, posix=(os.name != "nt"))
    except Exception:
        tokens = rendered_command.split()
    if not tokens:
        return "", parsed_args, missing_env_vars

    return tokens[0], tokens[1:] + parsed_args, missing_env_vars


def _parse_env(env_raw: Any) -> tuple[dict[str, str] | None, set[str]]:
    """Parse and expand env map from raw config value."""
    env_dict = env_raw if isinstance(env_raw, dict) else {}
    missing_env_vars: set[str] = set()
    env: dict[str, str] = {}

    for key, value in env_dict.items():
        if isinstance(value, str):
            missing_env_vars.update(_find_missing_env_vars(value))
            rendered = _expand_env_vars(value)
            if rendered:
                env[key] = rendered

    return (env or None), missing_env_vars


def _parse_cwd(cwd_raw: Any, base_dir: Path) -> tuple[str | None, set[str]]:
    """Parse and resolve cwd from raw config value."""
    if not isinstance(cwd_raw, str):
        return None, set()

    missing_env_vars = _find_missing_env_vars(cwd_raw)
    rendered_cwd = _expand_env_vars(cwd_raw).strip()
    if not rendered_cwd:
        return None, missing_env_vars

    cwd_path = Path(rendered_cwd).expanduser()
    if not cwd_path.is_absolute():
        cwd_path = (base_dir / cwd_path).resolve()
    else:
        cwd_path = cwd_path.resolve()

    return str(cwd_path), missing_env_vars


def _parse_mcp_server(
    server_name: str,
    server_data: Any,
    config_file_path: Path | None = None,
) -> MCPServerConfig:
    """Parse one MCP server entry from JSON mapping format.

    Supports both full object and shorthand command string:
    - "pfc-mcp": {"command": "uvx", "args": ["pfc-mcp"]}
    - "pfc-mcp": "uvx pfc-mcp"
    """
    if isinstance(server_data, str):
        normalized: dict[str, Any] = {"command": server_data}
    elif isinstance(server_data, dict):
        normalized = server_data
    else:
        normalized = {}

    command, args, missing_in_command_args = _parse_command_and_args(
        normalized.get("command", ""),
        normalized["args"] if "args" in normalized else None,
    )
    base_dir = config_file_path.parent if config_file_path else Path.cwd()
    cwd, missing_in_cwd = _parse_cwd(normalized.get("cwd"), base_dir)
    env, missing_in_env = _parse_env(normalized.get("env", {}))
    missing_env_vars = sorted(missing_in_command_args | missing_in_env | missing_in_cwd)

    return MCPServerConfig(
        name=server_name,
        command=command,
        args=args,
        cwd=cwd,
        env=env,
        enabled=normalized.get("enabled", True),
        description=normalized.get("description", ""),
        missing_env_vars=missing_env_vars,
    )


def _load_mcp_servers_mapping_from_file(config_file_path: Path) -> dict[str, Any]:
    """Load and validate mcpServers mapping from a JSON config file."""
    with config_file_path.open(encoding="utf-8") as f:
        config_data = json.load(f)

    if not isinstance(config_data, dict):
        logger.warning(f"Invalid MCP config format in {config_file_path}: root must be an object")
        return {}

    mcp_servers = config_data.get("mcpServers", {})
    if not isinstance(mcp_servers, dict):
        logger.warning(f"Invalid MCP config format in {config_file_path}: 'mcpServers' must be an object")
        return {}

    normalized: dict[str, Any] = {}
    for server_name, server_data in mcp_servers.items():
        if isinstance(server_name, str) and isinstance(server_data, (dict, str)):
            normalized[server_name] = server_data
    return normalized


def _build_default_mcp_config_paths(workspace_root: str | None = None) -> list[Path]:
    """Build MCP config lookup paths in low -> high priority order."""
    project_root = Path(__file__).parent.parent.parent.parent.parent
    builtin_config = project_root / "config" / MCP_CONFIG_FILENAME
    user_config = Path.home() / NAGISA_CONFIG_DIR / MCP_CONFIG_FILENAME

    config_paths = [builtin_config, user_config]

    if workspace_root:
        workspace_path = Path(workspace_root).expanduser()
        if not workspace_path.is_absolute():
            workspace_path = (Path.cwd() / workspace_path).resolve()
        else:
            workspace_path = workspace_path.resolve()
        workspace_config = workspace_path / NAGISA_CONFIG_DIR / MCP_CONFIG_FILENAME
        config_paths.append(workspace_config)

    return config_paths


def load_mcp_configs(
    config_path: str | None = None,
    workspace_root: str | None = None,
) -> list[MCPServerConfig]:
    """
    Load MCP server configurations from JSON config file.

    Supported schema:

    {
      "mcpServers": {
        "server-name": {
          "command": "uvx",
          "args": ["package-name"],
          "cwd": "/optional/working/directory"
        }
      }
    }

    Minimal shorthand is also supported:

    {
      "mcpServers": {
        "server-name": "uvx package-name"
      }
    }

    Config priority (low -> high):
        1. Builtin: project/config/mcp.json
        2. User: ~/.nagisa/mcp.json
        3. Workspace: <workspace>/.nagisa/mcp.json

    Args:
        config_path: Optional explicit config path. If provided, only this file is loaded.
        workspace_root: Optional workspace root used to resolve workspace-level config.

    Returns:
        List of MCPServerConfig objects
    """
    config_paths = [Path(config_path)] if config_path else _build_default_mcp_config_paths(workspace_root)

    merged_servers: dict[str, tuple[Any, Path]] = {}
    loaded_paths: list[Path] = []

    for path in config_paths:
        if not path.exists():
            continue
        try:
            server_mapping = _load_mcp_servers_mapping_from_file(path)
        except Exception as e:
            logger.warning(f"Failed to load MCP config file {path}: {e}")
            continue

        for server_name, server_data in server_mapping.items():
            if server_name in merged_servers:
                logger.info(f"MCP server '{server_name}' overridden by config: {path}")
            merged_servers[server_name] = (server_data, path)

        loaded_paths.append(path)

    if not loaded_paths:
        logger.warning("No MCP config files found (checked builtin/user/workspace paths)")
        return []

    configs: list[MCPServerConfig] = []
    for server_name, (server_data, source_path) in merged_servers.items():
        if isinstance(server_data, dict) and server_data.get("type", "stdio") != "stdio":
            logger.warning(f"[{server_name}] Unsupported MCP transport type: {server_data.get('type')}")
            continue
        configs.append(_parse_mcp_server(server_name, server_data, source_path))

    loaded_path_text = ", ".join(str(path) for path in loaded_paths)
    logger.info(f"Loaded {len(configs)} MCP server configs from: {loaded_path_text}")
    return configs


async def ensure_mcp_clients_for_workspace(workspace_root: str | None) -> None:
    """Ensure MCP clients are connected for merged config of a workspace."""
    manager = get_mcp_client_manager()
    loaded_configs = load_mcp_configs(workspace_root=workspace_root)
    connected = set(manager.get_connected_servers())

    for config in loaded_configs:
        if config.name in connected:
            continue
        if config.missing_env_vars:
            missing_vars = ", ".join(config.missing_env_vars)
            logger.warning(
                f"[{config.name}] Skipping MCP server initialization due to missing environment variables: {missing_vars}"
            )
            continue

        success = await manager.add_server(config)
        if success:
            connected.add(config.name)
