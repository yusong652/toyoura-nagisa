"""
Agent Profile Configuration - Unified profile definitions.

This module provides the single source of truth for all agent profile
configurations, including tool assignments, runtime behavior, and display metadata.

Architecture note:
- Lives in Domain layer (business rules for agent configuration)
- Infrastructure layer (tool_manager) reads from here
- This is configuration/strategy, not infrastructure implementation
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List


class AgentProfile(Enum):
    """Agent profile types."""
    PFC_EXPERT = "pfc_expert"
    DISABLED = "disabled"


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
# Following Claude Code's Explore agent design: lightweight, read-only, fast
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
    # NOTE: No write, no edit, no pfc_execute_task
    # Explorer uses bash only for read-only operations (ls, find, git)
    # Complex execution logic should be handled by MainAgent
]

# SubAgent-specific tool list for PFC Diagnostic Expert (multimodal visual analysis)
# Pure visual analysis + task status inspection - MainAgent handles script execution
SUBAGENT_PFC_DIAGNOSTIC_TOOLS: List[str] = [
    # Core diagnostic tools (multimodal)
    "pfc_capture_plot",  # Visual capture from multiple angles/coloring modes
    "read",              # Image analysis (multimodal LLM capability)
    # Task status inspection (read MainAgent's executed tasks)
    "pfc_check_task_status",  # Query task progress and output
    "pfc_list_tasks",         # List all tracked tasks with status
    # Support tools (workspace navigation, read-only)
    "glob",
    "grep",
    "bash",
    "bash_output",
    # Workflow tracking
    "todo_write",
    # NOTE: No pfc_execute_task - MainAgent handles all script execution
    # NOTE: No write, no edit - diagnostic agent reports issues, MainAgent fixes
    # NOTE: No invoke_agent - prevents recursive SubAgent spawning
]


# =============================================================================
# Skills Configuration (on-demand workflow instructions)
# =============================================================================

# PFC-specific skills for simulation workflows
# Note: Basic capabilities (error resolution, script creation, doc navigation,
# subagent delegation, task execution) are now in system prompt.
# Skills are reserved for special workflows that need on-demand detailed guidance.
PFC_SKILLS: List[str] = [
    "pfc-package-management",  # PFC Python package install/uninstall
    "pfc-server-setup",        # pfc-server setup and connection guide
]


# =============================================================================
# Profile Configuration
# =============================================================================

@dataclass(frozen=True)
class ProfileConfig:
    """
    Complete agent profile configuration.

    Combines runtime behavior settings with tool assignments and display metadata.
    Immutable (frozen) to ensure configuration consistency.
    """
    # Identity
    name: str
    display_name: str
    description: str

    # Runtime behavior
    max_iterations: int
    streaming_enabled: bool
    enable_memory: bool

    # Tool configuration
    tools: tuple  # Immutable tuple of tool names

    # Display metadata (for frontend)
    color: str
    icon: str

    # Skills configuration (on-demand workflow instructions)
    # Placed after required fields due to dataclass ordering requirements
    skills: tuple = ()  # Immutable tuple of skill names available for this profile

    @property
    def tool_profile(self) -> str:
        """Tool profile name (same as name for ProfileConfig)."""
        return self.name

    @property
    def tool_count(self) -> int:
        return len(self.tools)

    @property
    def estimated_tokens(self) -> int:
        """Estimate tokens based on ~282 tokens per tool schema."""
        return len(self.tools) * 282


# =============================================================================
# Profile Registry (single source of truth)
# =============================================================================

PROFILE_CONFIGS: Dict[AgentProfile, ProfileConfig] = {
    AgentProfile.PFC_EXPERT: ProfileConfig(
        name="pfc_expert",
        display_name="PFC Expert",
        description="ITASCA PFC simulation with script-based workflow",
        max_iterations=64,
        streaming_enabled=True,
        enable_memory=True,
        tools=tuple(PFC_TOOLS),
        color="#9C27B0",
        icon="⚛️",
        skills=tuple(PFC_SKILLS),
    ),

    AgentProfile.DISABLED: ProfileConfig(
        name="disabled",
        display_name="Chat Agent",
        description="Pure conversation mode without tools",
        max_iterations=64,
        streaming_enabled=True,
        enable_memory=True,
        tools=(),
        color="#F44336",
        icon="🚫",
    ),
}


# =============================================================================
# SubAgent Definitions
# =============================================================================
# SubAgents have independent names (for prompt loading) but reuse tool profiles.

@dataclass(frozen=True)
class SubAgentConfig:
    """
    SubAgent configuration.

    SubAgents have their own prompt file (config/prompts/{name}.md)
    and an explicit tool list that MUST NOT include invoke_agent
    to prevent recursive SubAgent spawning.
    """
    name: str                    # Unique name, also prompt file name
    display_name: str
    description: str
    tools: tuple                 # Explicit tool list (no invoke_agent!)
    max_iterations: int = 32  # Default for SubAgents (higher than before to handle complex tasks)
    streaming_enabled: bool = False
    enable_memory: bool = False

    @property
    def tool_profile(self) -> str:
        """Tool profile name (same as name for SubAgentConfig)."""
        return self.name


PFC_EXPLORER = SubAgentConfig(
    name="pfc_explorer",
    display_name="Tama (PFC Explorer)",
    description="Tama - PFC documentation query agent (read-only)",
    tools=tuple(SUBAGENT_PFC_EXPLORER_TOOLS),
    max_iterations=64,  # Reduced: read-only exploration tasks are simpler
    streaming_enabled=False,
    enable_memory=False,
)

PFC_DIAGNOSTIC = SubAgentConfig(
    name="pfc_diagnostic",
    display_name="Hoshi (PFC Diagnostic)",
    description="Hoshi - Multimodal visual analysis agent for PFC simulation diagnostics",
    tools=tuple(SUBAGENT_PFC_DIAGNOSTIC_TOOLS),
    max_iterations=64,  # Multi-angle analysis may require many capture+read cycles
    streaming_enabled=False,
    enable_memory=False,
)

SUBAGENT_CONFIGS: Dict[str, SubAgentConfig] = {
    "pfc_explorer": PFC_EXPLORER,
    "pfc_diagnostic": PFC_DIAGNOSTIC,
}


# =============================================================================
# Accessor Functions
# =============================================================================

def get_profile_config(profile: str | AgentProfile) -> ProfileConfig:
    """
    Get profile configuration by name or enum.

    Args:
        profile: Profile name string or AgentProfile enum

    Returns:
        ProfileConfig for the specified profile

    Raises:
        KeyError: If profile not found
    """
    if isinstance(profile, str):
        profile = AgentProfile(profile)
    return PROFILE_CONFIGS[profile]


def get_tools_for_profile(profile: str | AgentProfile) -> List[str]:
    """
    Get tool list for a profile or SubAgent.

    Args:
        profile: Profile name string, AgentProfile enum, or SubAgent name

    Returns:
        List of tool names for the profile/SubAgent
    """
    # First check if it's a SubAgent name
    if isinstance(profile, str) and profile in SUBAGENT_CONFIGS:
        return list(SUBAGENT_CONFIGS[profile].tools)

    # Otherwise, look up in PROFILE_CONFIGS
    config = get_profile_config(profile)
    return list(config.tools)


def get_all_profiles() -> Dict[str, dict]:
    """
    Get all profile configurations for frontend display.

    Returns:
        Dict mapping profile name to display info
    """
    return {
        profile.value: {
            "name": config.display_name,
            "description": config.description,
            "estimated_tokens": config.estimated_tokens,
            "tool_count": config.tool_count,
            "color": config.color,
            "icon": config.icon,
        }
        for profile, config in PROFILE_CONFIGS.items()
    }


def get_subagent_config(name: str) -> SubAgentConfig:
    """Get SubAgent configuration by name."""
    return SUBAGENT_CONFIGS[name]


def get_skills_for_profile(profile: str | AgentProfile) -> List[str]:
    """
    Get available skills for a profile.

    Args:
        profile: Profile name string or AgentProfile enum

    Returns:
        List of skill names available for the profile
    """
    # SubAgents don't have skills (they're task-focused)
    if isinstance(profile, str) and profile in SUBAGENT_CONFIGS:
        return []

    config = get_profile_config(profile)
    return list(config.skills)
