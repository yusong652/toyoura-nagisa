"""Mode policy for tool execution.

Loads read-only tool rules from config/mode_policy.yaml and provides
helpers to enforce plan/build gating for tool execution. If the YAML
is missing or invalid, plan mode denies all tool execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import logging
import shlex
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModePolicy:
    read_only_tools: set[str]
    read_only_bash_commands: set[str]
    read_only_git_subcommands: set[str]
    blocked_command_tokens: tuple[str, ...]
    valid: bool


_MODE_POLICY: ModePolicy | None = None


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent.parent


def _normalize_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    items: list[str] = []
    for item in value:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            items.append(text)
    return items


def _load_mode_policy_yaml(yaml_path: str | None = None) -> tuple[dict[str, Any], bool]:
    if yaml_path is None:
        yaml_path = str(_project_root() / "config" / "mode_policy.yaml")

    path = Path(yaml_path)
    if not path.exists():
        logger.warning("Mode policy file not found: %s", yaml_path)
        return {}, False

    try:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as exc:
        logger.warning("Failed to load mode policy from %s: %s", yaml_path, exc)
        return {}, False

    if not isinstance(data, dict):
        logger.warning("Invalid mode policy config in %s: expected mapping", yaml_path)
        return {}, False

    return data, True


def _get_set(data: dict[str, Any], key: str) -> set[str]:
    if key not in data:
        logger.warning("Mode policy key '%s' missing", key)
        return set()

    value = data.get(key)
    if value is None:
        return set()

    if not isinstance(value, (list, tuple, set)):
        logger.warning("Invalid mode policy key '%s': expected list", key)
        return set()

    return set(_normalize_list(value))


def _get_tokens(data: dict[str, Any], key: str) -> tuple[str, ...]:
    if key not in data:
        logger.warning("Mode policy key '%s' missing", key)
        return ()

    value = data.get(key)
    if value is None:
        return ()

    if not isinstance(value, (list, tuple, set)):
        logger.warning("Invalid mode policy key '%s': expected list", key)
        return ()

    return tuple(_normalize_list(value))


def get_mode_policy() -> ModePolicy:
    global _MODE_POLICY
    if _MODE_POLICY is None:
        data, valid = _load_mode_policy_yaml()
        if not valid:
            _MODE_POLICY = ModePolicy(
                read_only_tools=set(),
                read_only_bash_commands=set(),
                read_only_git_subcommands=set(),
                blocked_command_tokens=(),
                valid=False,
            )
        else:
            _MODE_POLICY = ModePolicy(
                read_only_tools=_get_set(data, "read_only_tools"),
                read_only_bash_commands=_get_set(data, "read_only_bash_commands"),
                read_only_git_subcommands=_get_set(data, "read_only_git_subcommands"),
                blocked_command_tokens=_get_tokens(data, "blocked_command_tokens"),
                valid=True,
            )
    return _MODE_POLICY


def is_bash_command_read_only(command: str, policy: ModePolicy | None = None) -> bool:
    """Return True if a bash command is safe for plan mode."""
    if not command:
        return False

    command = command.strip()
    if not command:
        return False

    policy = policy or get_mode_policy()
    if not policy.valid:
        return False
    if any(token in command for token in policy.blocked_command_tokens):
        return False

    try:
        parts = shlex.split(command)
    except ValueError:
        return False

    if not parts:
        return False

    root = parts[0]
    if root in policy.read_only_bash_commands:
        return True

    if root == "git":
        if len(parts) < 2:
            return False
        return parts[1] in policy.read_only_git_subcommands

    return False


def is_read_only_tool(tool_name: str, tool_args: dict[str, Any], policy: ModePolicy | None = None) -> bool:
    """Return True if a tool call is considered read-only."""
    policy = policy or get_mode_policy()
    if not policy.valid:
        return False
    if tool_name == "bash":
        return is_bash_command_read_only(str(tool_args.get("command", "")), policy=policy)

    return tool_name in policy.read_only_tools


def is_tool_allowed_in_mode(
    mode: str, tool_name: str, tool_args: dict[str, Any], policy: ModePolicy | None = None
) -> bool:
    """Return True if a tool is allowed in the given session mode."""
    normalized_mode = (mode or "build").lower()
    if normalized_mode != "plan":
        return True

    policy = policy or get_mode_policy()
    if not policy.valid:
        return False

    return is_read_only_tool(tool_name, tool_args, policy=policy)


def build_mode_blocked_message(mode: str, tool_name: str) -> str:
    """Build a user-facing error message for blocked tools."""
    normalized_mode = (mode or "build").upper()
    return (
        f"Tool '{tool_name}' is disabled while session is in {normalized_mode} mode. "
        "Switch to BUILD mode to execute write or execution tools."
    )
