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


# === Agent Registry ===
AGENT_DEFINITIONS: Dict[str, AgentDefinition] = {
    "pfc_explorer": PFC_EXPLORER,
}
