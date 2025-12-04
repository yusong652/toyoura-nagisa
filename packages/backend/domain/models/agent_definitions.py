"""
Predefined agent configurations.

This module contains all built-in agent definitions. New agents
can be added here or registered at runtime via AgentRegistry.

Each agent's system prompt is loaded from config/prompts/{name}.md,
reusing the existing prompt infrastructure with tool schemas and
environment info injection.
"""

from typing import Dict

from backend.domain.models.agent import AgentDefinition


# === MainAgent Definitions (Streaming Mode) ===
# Each profile has its own definition with appropriate tool_profile.
# Used by AgentService.process_chat() for user-facing conversations.

_MAIN_AGENT_BASE = {
    "max_iterations": 64,
    "streaming_enabled": True,
    "enable_memory": True,
}

GENERAL_AGENT = AgentDefinition(
    name="general",
    display_name="General Agent",
    description="Multi-domain agent with full tool access",
    tool_profile="general",
    **_MAIN_AGENT_BASE,
)

CODING_AGENT = AgentDefinition(
    name="coding",
    display_name="Coding Agent",
    description="Code development and debugging agent",
    tool_profile="coding",
    **_MAIN_AGENT_BASE,
)

LIFESTYLE_AGENT = AgentDefinition(
    name="lifestyle",
    display_name="Lifestyle Agent",
    description="Email, calendar, and communication agent",
    tool_profile="lifestyle",
    **_MAIN_AGENT_BASE,
)

PFC_AGENT = AgentDefinition(
    name="pfc",
    display_name="PFC Agent",
    description="PFC simulation and scientific computing agent",
    tool_profile="pfc",
    **_MAIN_AGENT_BASE,
)

DISABLED_AGENT = AgentDefinition(
    name="disabled",
    display_name="Chat Agent",
    description="Text-only conversation agent without tools",
    tool_profile="disabled",
    **_MAIN_AGENT_BASE,
)

# Lookup table for MainAgent profiles
MAIN_AGENT_PROFILES: Dict[str, AgentDefinition] = {
    "general": GENERAL_AGENT,
    "coding": CODING_AGENT,
    "lifestyle": LIFESTYLE_AGENT,
    "pfc": PFC_AGENT,
    "disabled": DISABLED_AGENT,
}


def get_main_agent_definition(profile: str) -> AgentDefinition:
    """
    Get MainAgent definition for a given profile.

    Args:
        profile: Agent profile name (general, coding, lifestyle, pfc, disabled)

    Returns:
        AgentDefinition for the profile, defaults to GENERAL_AGENT if not found
    """
    return MAIN_AGENT_PROFILES.get(profile, GENERAL_AGENT)


# === PFC Explorer SubAgent ===
# System prompt loaded from: config/prompts/pfc_explorer.md
PFC_EXPLORER = AgentDefinition(
    name="pfc_explorer",  # Also used as prompt profile
    display_name="PFC Explorer",
    description="PFC documentation query and syntax validation agent",
    tool_profile="pfc",  # Uses PFC tool set
    max_iterations=10,
    streaming_enabled=False,
    enable_memory=False,
)


# === Agent Registry (SubAgents only) ===
SUBAGENT_DEFINITIONS: Dict[str, AgentDefinition] = {
    "pfc_explorer": PFC_EXPLORER,
}
