"""Shared configuration for coding.tools.

A *singleton-style* object holds runtime parameters (currently only
``root_dir`` and ``debug_mode``).  Tools can import
:pyfunc:`get_tools_config` to access the current settings, or
:pyfunc:`set_tools_config` to replace them (e.g. at application start-up).
"""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass

__all__ = [
    "ToolsConfig",
    "get_tools_config",
    "set_tools_config",
]


@dataclass
class ToolsConfig:
    root_dir: Path
    debug_mode: bool = False


# ---------------------------------------------------------------------------
# Global mutable instance (can be swapped by set_tools_config)
# ---------------------------------------------------------------------------

# By default assume repo layout: <repo_root>/workspace/default
# "repo_root" is five levels up from this file (tools → coding → tools → nagisa_mcp → backend → <repo_root>)
# This is more robust than using parents[6] which pointed to the user's home dir
# in some environments.
_DEFAULT_ROOT = Path(__file__).resolve().parents[5] / "workspace" / "default"
_DEFAULT_ROOT.mkdir(parents=True, exist_ok=True)

_CONFIG: ToolsConfig = ToolsConfig(root_dir=_DEFAULT_ROOT)


def get_tools_config() -> ToolsConfig:
    """Return current global config instance."""

    return _CONFIG


def set_tools_config(cfg: ToolsConfig) -> None:
    """Replace global config – call once during application bootstrap."""

    global _CONFIG  # noqa: PLW0603
    _CONFIG = cfg 