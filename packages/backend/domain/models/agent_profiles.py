"""
Agent Configuration - Unified agent definitions.

Configuration data is loaded from config/agents.yaml. This module provides
the domain model and accessors for main agent and SubAgent configuration.
"""

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, Dict, List

import yaml


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SkillConfig:
    """
    Skill configuration with enabled state.

    Attributes:
        name: Unique identifier for the skill (e.g., 'pfc-package-management')
        enabled: Default enabled state for new sessions. Users can toggle per-session.
    """

    name: str
    enabled: bool = True


@dataclass(frozen=True)
class AgentConfig:
    """
    Unified agent configuration for both main agent and SubAgents.

    Use is_main_agent to differentiate runtime behavior.
    """

    # Identity
    name: str
    display_name: str
    description: str

    # Tool configuration
    tools: tuple

    # Runtime behavior
    max_iterations: int = 32
    streaming_enabled: bool = False
    is_main_agent: bool = False

    # Display metadata (for frontend)
    color: str = "#9E9E9E"
    icon: str = "🤖"

    # Skills configuration (on-demand workflow instructions)
    # Each skill has a name and default enabled state
    skills: tuple = ()  # tuple[SkillConfig, ...]

    def __post_init__(self) -> None:
        if not self.is_main_agent and "invoke_agent" in self.tools:
            raise ValueError("SubAgent config must not include invoke_agent")

    @property
    def tool_count(self) -> int:
        return len(self.tools)

    @property
    def estimated_tokens(self) -> int:
        """Estimate tokens based on ~282 tokens per tool schema."""
        return len(self.tools) * 282


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent.parent


def _load_agents_yaml(yaml_path: str | None = None) -> dict[str, Any]:
    if yaml_path is None:
        yaml_path = str(_project_root() / "config" / "agents.yaml")

    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"Agent config file not found: {yaml_path}")

    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Invalid agent config in {yaml_path}: expected mapping")

    return data


def _require_mapping(data: dict[str, Any], key: str, context: str) -> dict[str, Any]:
    if key not in data:
        raise ValueError(f"Missing {context}.{key} in agent config")
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Invalid {context}.{key}: expected mapping")
    return value


def _require_str(data: dict[str, Any], key: str, context: str) -> str:
    if key not in data:
        raise ValueError(f"Missing {context}.{key} in agent config")
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Invalid {context}.{key}: expected non-empty string")
    return value.strip()


def _require_bool(data: dict[str, Any], key: str, context: str) -> bool:
    if key not in data:
        raise ValueError(f"Missing {context}.{key} in agent config")
    value = data.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"Invalid {context}.{key}: expected boolean")
    return value


def _require_int(data: dict[str, Any], key: str, context: str) -> int:
    if key not in data:
        raise ValueError(f"Missing {context}.{key} in agent config")
    value = data.get(key)
    if not isinstance(value, int):
        raise ValueError(f"Invalid {context}.{key}: expected integer")
    if value <= 0:
        raise ValueError(f"Invalid {context}.{key}: must be greater than zero")
    return value


def _require_str_list(data: dict[str, Any], key: str, context: str, allow_empty: bool = False) -> List[str]:
    if key not in data:
        raise ValueError(f"Missing {context}.{key} in agent config")
    value = data.get(key)
    if not isinstance(value, list):
        raise ValueError(f"Invalid {context}.{key}: expected list")

    items: List[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ValueError(f"Invalid {context}.{key}[{index}]: expected string")
        text = item.strip()
        if text:
            items.append(text)

    if not allow_empty and not items:
        raise ValueError(f"Invalid {context}.{key}: must not be empty")

    return items


def _parse_skills_config(data: dict[str, Any], key: str, context: str) -> List[SkillConfig]:
    """
    Parse skills configuration from YAML.

    Format: [{name: "skill-name", enabled: true}, ...]

    Args:
        data: Parent dict containing the skills key
        key: The key name (usually "skills")
        context: Context string for error messages

    Returns:
        List of SkillConfig objects
    """
    if key not in data:
        raise ValueError(f"Missing {context}.{key} in agent config")

    value = data.get(key)
    if not isinstance(value, list):
        raise ValueError(f"Invalid {context}.{key}: expected list")

    skills: List[SkillConfig] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"Invalid {context}.{key}[{index}]: expected mapping with 'name' and 'enabled' fields")
        if "name" not in item:
            raise ValueError(f"Invalid {context}.{key}[{index}]: missing 'name' field")
        name = item["name"]
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Invalid {context}.{key}[{index}].name: expected non-empty string")
        enabled = item.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError(f"Invalid {context}.{key}[{index}].enabled: expected boolean")
        skills.append(SkillConfig(name=name.strip(), enabled=enabled))

    return skills


def _build_agent_config(
    data: dict[str, Any], *, context: str, is_main_agent: bool, default_name: str | None = None
) -> AgentConfig:
    if "name" in data:
        name = _require_str(data, "name", context)
        if default_name and name != default_name:
            raise ValueError(f"Invalid {context}.name: '{name}' does not match key '{default_name}'")
    elif default_name:
        name = default_name
    else:
        raise ValueError(f"Missing {context}.name in agent config")

    display_name = _require_str(data, "display_name", context)
    description = _require_str(data, "description", context)
    if "tools" in data and data["tools"] is not None:
        tools = tuple(_require_str_list(data, "tools", context, allow_empty=True))
    else:
        tools = ()
    max_iterations = _require_int(data, "max_iterations", context)
    streaming_enabled = _require_bool(data, "streaming_enabled", context)
    color = _require_str(data, "color", context)
    icon = _require_str(data, "icon", context)
    skills = tuple(_parse_skills_config(data, "skills", context))

    return AgentConfig(
        name=name,
        display_name=display_name,
        description=description,
        tools=tools,
        max_iterations=max_iterations,
        streaming_enabled=streaming_enabled,
        is_main_agent=is_main_agent,
        color=color,
        icon=icon,
        skills=skills,
    )


def _load_agent_configs() -> tuple[AgentConfig, Dict[str, AgentConfig]]:
    data = _load_agents_yaml()
    main_agent_data = _require_mapping(data, "main_agent", "agents")
    main_agent = _build_agent_config(
        main_agent_data,
        context="main_agent",
        is_main_agent=True,
        default_name=None,
    )

    subagents_data = _require_mapping(data, "subagents", "agents")
    subagents: Dict[str, AgentConfig] = {}
    for key, value in subagents_data.items():
        if not isinstance(value, dict):
            raise ValueError(f"Invalid subagents.{key}: expected mapping")
        config = _build_agent_config(
            value,
            context=f"subagents.{key}",
            is_main_agent=False,
            default_name=key,
        )
        subagents[config.name] = config

    return main_agent, subagents


try:
    MAIN_AGENT_CONFIG, SUBAGENT_CONFIGS = _load_agent_configs()
except Exception as exc:
    logger.error("Failed to load agent configs: %s", exc)
    raise


PFC_EXPLORER = SUBAGENT_CONFIGS["pfc_explorer"]
PFC_DIAGNOSTIC = SUBAGENT_CONFIGS["pfc_diagnostic"]


def get_agent_config() -> AgentConfig:
    """Get the single main agent configuration."""
    return MAIN_AGENT_CONFIG


def get_subagent_config(name: str) -> AgentConfig:
    """Get SubAgent configuration by name."""
    return SUBAGENT_CONFIGS[name]


def get_tools_for_agent(agent_name: str) -> List[str]:
    """
    Get tool list for the main agent or a SubAgent.

    Args:
        agent_name: Main agent name or SubAgent name

    Returns:
        List of tool names
    """
    if agent_name in SUBAGENT_CONFIGS:
        return list(SUBAGENT_CONFIGS[agent_name].tools)
    if agent_name == MAIN_AGENT_CONFIG.name:
        return list(MAIN_AGENT_CONFIG.tools)
    raise KeyError(f"Unknown agent name: {agent_name}")


def get_skills_for_agent(agent_name: str) -> List[str]:
    """
    Get available skill names for an agent.

    NOTE: This returns only skill names for backward compatibility.
    Use get_skill_configs_for_agent() for full SkillConfig objects.

    Args:
        agent_name: Main agent name or SubAgent name

    Returns:
        List of skill names available for the agent
    """
    if agent_name in SUBAGENT_CONFIGS:
        return [s.name for s in SUBAGENT_CONFIGS[agent_name].skills]
    if agent_name == MAIN_AGENT_CONFIG.name:
        return [s.name for s in MAIN_AGENT_CONFIG.skills]
    raise KeyError(f"Unknown agent name: {agent_name}")


def get_skill_configs_for_agent(agent_name: str) -> List[SkillConfig]:
    """
    Get full skill configurations for an agent.

    Args:
        agent_name: Main agent name or SubAgent name

    Returns:
        List of SkillConfig objects for the agent
    """
    if agent_name in SUBAGENT_CONFIGS:
        return list(SUBAGENT_CONFIGS[agent_name].skills)
    if agent_name == MAIN_AGENT_CONFIG.name:
        return list(MAIN_AGENT_CONFIG.skills)
    raise KeyError(f"Unknown agent name: {agent_name}")
