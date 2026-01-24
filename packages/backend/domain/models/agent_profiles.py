"""
Agent Configuration - Unified agent definitions.

This module provides the single source of truth for main agent and SubAgent
configuration, including tool assignments and runtime behavior.

Architecture note:
- Domain layer configuration (business rules)
- Infrastructure layer reads from here for tool selection
"""

from dataclasses import dataclass
from typing import Dict, List


# =============================================================================
# Tool Lists (flat definitions for easy maintenance)
# =============================================================================

PFC_TOOLS: List[str] = [
    # File operations
    "write",
    "read",
    "edit",
    # System commands
    "bash",
    "bash_output",
    "kill_shell",
    "glob",
    "grep",
    # Search and planning
    "web_search",
    "web_fetch",
    "todo_write",
    # PFC documentation - Browse (directory listing)
    "pfc_browse_commands",
    "pfc_browse_python_api",
    "pfc_browse_reference",
    # PFC documentation - Query (detailed lookup)
    "pfc_query_python_api",
    "pfc_query_command",
    # PFC execution (script-only workflow)
    "pfc_execute_task",
    "pfc_check_task_status",
    "pfc_list_tasks",
    "pfc_interrupt_task",
    # PFC diagnostic (multimodal visual analysis)
    "pfc_capture_plot",
    # SubAgent delegation
    "invoke_agent",
    # Skills (on-demand workflow instructions)
    "trigger_skill",
]

# SubAgent-specific tool list for PFC Explorer (read-only exploration)
SUBAGENT_PFC_EXPLORER_TOOLS: List[str] = [
    # File operations (read-only)
    "read",
    "glob",
    "grep",
    # Bash for fallback search (ls, find, git log, etc.)
    "bash",
    "bash_output",
    # PFC documentation query (read-only)
    "pfc_browse_commands",
    "pfc_browse_python_api",
    "pfc_query_python_api",
    "pfc_query_command",
    "pfc_browse_reference",
    # Task context inspection (script is context)
    "pfc_list_tasks",
    "pfc_check_task_status",
    # Web search for external docs
    "web_search",
    # Task tracking (consistent with Claude Code Explore agent)
    "todo_write",
]

# SubAgent-specific tool list for PFC Diagnostic Expert (multimodal visual analysis)
SUBAGENT_PFC_DIAGNOSTIC_TOOLS: List[str] = [
    # Core diagnostic tools (multimodal)
    "pfc_capture_plot",
    "read",
    # Task status inspection (read MainAgent's executed tasks)
    "pfc_check_task_status",
    "pfc_list_tasks",
    # Support tools (workspace navigation, read-only)
    "glob",
    "grep",
    "bash",
    "bash_output",
    # Workflow tracking
    "todo_write",
]


# =============================================================================
# Skills Configuration (on-demand workflow instructions)
# =============================================================================

PFC_SKILLS: List[str] = [
    "pfc-package-management",
    "pfc-server-setup",
]


# =============================================================================
# Unified Agent Configuration
# =============================================================================


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
    enable_memory: bool = False
    is_main_agent: bool = False

    # Display metadata (for frontend)
    color: str = "#9E9E9E"
    icon: str = "🤖"

    # Skills configuration (on-demand workflow instructions)
    skills: tuple = ()

    def __post_init__(self) -> None:
        if not self.is_main_agent and "invoke_agent" in self.tools:
            raise ValueError("SubAgent config must not include invoke_agent")

    @property
    def tool_profile(self) -> str:
        """Tool profile name (same as name for AgentConfig)."""
        return self.name

    @property
    def tool_count(self) -> int:
        return len(self.tools)

    @property
    def estimated_tokens(self) -> int:
        """Estimate tokens based on ~282 tokens per tool schema."""
        return len(self.tools) * 282


MAIN_AGENT_CONFIG = AgentConfig(
    name="pfc_expert",
    display_name="PFC Expert",
    description="ITASCA PFC simulation with script-based workflow",
    tools=tuple(PFC_TOOLS),
    max_iterations=64,
    streaming_enabled=True,
    enable_memory=True,
    is_main_agent=True,
    color="#9C27B0",
    icon="⚛️",
    skills=tuple(PFC_SKILLS),
)


# =============================================================================
# SubAgent Definitions
# =============================================================================


PFC_EXPLORER = AgentConfig(
    name="pfc_explorer",
    display_name="Tama (PFC Explorer)",
    description="Tama - PFC documentation query agent (read-only)",
    tools=tuple(SUBAGENT_PFC_EXPLORER_TOOLS),
    max_iterations=64,
    streaming_enabled=False,
    enable_memory=False,
    is_main_agent=False,
)

PFC_DIAGNOSTIC = AgentConfig(
    name="pfc_diagnostic",
    display_name="Hoshi (PFC Diagnostic)",
    description="Hoshi - Multimodal visual analysis agent for PFC simulation diagnostics",
    tools=tuple(SUBAGENT_PFC_DIAGNOSTIC_TOOLS),
    max_iterations=64,
    streaming_enabled=False,
    enable_memory=False,
    is_main_agent=False,
)

SUBAGENT_CONFIGS: Dict[str, AgentConfig] = {
    "pfc_explorer": PFC_EXPLORER,
    "pfc_diagnostic": PFC_DIAGNOSTIC,
}


# =============================================================================
# Accessor Functions
# =============================================================================


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
    Get available skills for an agent.

    Args:
        agent_name: Main agent name or SubAgent name

    Returns:
        List of skill names available for the agent
    """
    if agent_name in SUBAGENT_CONFIGS:
        return list(SUBAGENT_CONFIGS[agent_name].skills)
    if agent_name == MAIN_AGENT_CONFIG.name:
        return list(MAIN_AGENT_CONFIG.skills)
    raise KeyError(f"Unknown agent name: {agent_name}")
