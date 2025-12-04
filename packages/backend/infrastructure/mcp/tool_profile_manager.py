"""
Tool Profile Manager - Adapter layer for profile-based tool management.

This module provides backward-compatible access to agent profile configurations.
The actual configuration is defined in domain/models/agent_profiles.py.

This adapter exists to:
1. Maintain backward compatibility with existing code
2. Allow infrastructure layer to access domain-defined profiles
3. Provide the ToolProfileManager interface expected by tool_manager.py
"""

from typing import Dict, List, Any
from dataclasses import dataclass

# Re-export AgentProfile enum from domain layer
from backend.domain.models.agent_profiles import (
    AgentProfile,
    ProfileConfig,
    PROFILE_CONFIGS,
    get_profile_config,
    get_tools_for_profile,
    get_all_profiles,
)


@dataclass
class ToolProfile:
    """
    Tool collection configuration (backward compatibility).

    Maps to ProfileConfig from domain layer.
    """
    name: str
    description: str
    tools: List[str]
    estimated_tokens: int
    color: str
    icon: str


class ToolProfileManager:
    """
    Tool collection manager (backward compatibility adapter).

    Delegates to domain layer's agent_profiles module.
    """

    @classmethod
    def get_profile(cls, profile: AgentProfile) -> ToolProfile:
        """Get agent profile configuration."""
        config = PROFILE_CONFIGS[profile]
        return ToolProfile(
            name=config.display_name,
            description=config.description,
            tools=list(config.tools),
            estimated_tokens=config.estimated_tokens,
            color=config.color,
            icon=config.icon,
        )

    @classmethod
    def get_tools_for_profile(cls, profile: AgentProfile) -> List[str]:
        """Get tool list for specified profile."""
        return get_tools_for_profile(profile)

    @classmethod
    def get_available_profiles(cls) -> Dict[str, Dict[str, Any]]:
        """Get all available agent profile configurations (for frontend display)."""
        return get_all_profiles()
