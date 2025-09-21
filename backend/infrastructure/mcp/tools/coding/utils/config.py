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

# Use project root directory as workspace for full development participation
# Now that we have bash confirmation, agent can safely work in project root
# "repo_root" is six levels up from this file:
# config.py → tools → coding → tools → mcp → infrastructure → backend → <repo_root>
_DEFAULT_ROOT = Path(__file__).resolve().parents[6]

_CONFIG: ToolsConfig = ToolsConfig(root_dir=_DEFAULT_ROOT)


def get_tools_config() -> ToolsConfig:
    """Return current global config instance."""

    return _CONFIG


def set_tools_config(cfg: ToolsConfig) -> None:
    """Replace global config – call once during application bootstrap."""

    global _CONFIG  # noqa: PLW0603
    _CONFIG = cfg 