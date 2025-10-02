"""
Tool Profile Manager - Simplified agent profile-based tool management system

Supports multiple modes: lifestyle assistant, coding assistant, etc.
"""

from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum


class AgentProfile(Enum):
    """Agent profile types"""
    LIFESTYLE = "lifestyle"  # Lifestyle assistant
    CODING = "coding"        # Coding assistant
    PFC = "pfc"             # PFC simulation expert
    GENERAL = "general"      # General mode with all tools
    DISABLED = "disabled"    # All tools disabled


@dataclass
class ToolProfile:
    """Tool collection configuration"""
    name: str
    description: str
    tools: List[str]
    estimated_tokens: int
    color: str  # Frontend display color
    icon: str   # Frontend display icon


class ToolProfileManager:
    """Tool collection manager"""

    # Coding tools (including web_search)
    CODING_TOOLS = [
        "write",
        "read",
        "edit",   # File editing tool
        "bash",   # Shell command execution
        "bash_output",  # Background bash output monitoring
        "kill_shell",   # Background bash process termination
        "glob",   # File pattern matching
        "grep",
        "web_search"  # Web search for programming
    ]

    # Lifestyle tools (all non-coding tools, including web_search)
    LIFESTYLE_TOOLS = [
        "send_email",
        "check_emails",
        "read_email",
        "list_calendar_events",
        "create_calendar_event",
        "update_calendar_event",
        "delete_calendar_event",
        "list_contacts",
        "search_contacts",
        "generate_image",
        "search_places",
        "get_location",
        "web_search",  # Web search for lifestyle
        "get_current_time"
    ]

    # General tools (merged coding and lifestyle, deduplicated)
    GENERAL_TOOLS = [
        # Coding tools
        "write", "read", "edit", "bash", "bash_output", "kill_shell",
        "glob", "grep",
        # Lifestyle tools (excluding duplicate web_search)
        "send_email", "check_emails", "read_email",
        "list_calendar_events", "create_calendar_event",
        "update_calendar_event", "delete_calendar_event",
        "list_contacts", "search_contacts",
        "generate_image", "search_places", "get_location",
        "get_current_time",
        # Shared tool (only include once)
        "web_search"
    ]

    # PFC simulation tools (coding tools + future PFC-specific tools)
    PFC_TOOLS = [
        # File operation tools for PFC scripts and data files
        "write",
        "read",
        "edit",
        # System command tools for running PFC-related commands
        "bash",
        "bash_output",  # Background bash output monitoring for PFC simulations
        "kill_shell",   # Background bash process termination for PFC simulations
        "glob",  # File pattern matching for PFC data files
        "grep",
        # Search tools for finding PFC documentation and examples
        "web_search",
        # PFC-specific tools (to be added in the future)
        # "pfc_execute",        # Execute PFC commands
        # "pfc_model_create",   # Create models
        # "pfc_model_query",    # Query model state
        # "pfc_simulation_run", # Run simulations
        # "pfc_data_extract",   # Extract data
        # "pfc_visualization"   # Visualization
    ]
    
    # Tool profile definitions
    TOOL_PROFILES: Dict[AgentProfile, ToolProfile] = {
        AgentProfile.CODING: ToolProfile(
            name="Coding",
            description="Specialized in code development, file operations and programming tasks",
            tools=CODING_TOOLS,
            estimated_tokens=len(CODING_TOOLS) * 282,  # 10 tools
            color="#4CAF50",  # Green
            icon="💻"
        ),
        
        AgentProfile.LIFESTYLE: ToolProfile(
            name="Lifestyle", 
            description="Focused on daily life, communication, entertainment and information services",
            tools=LIFESTYLE_TOOLS,
            estimated_tokens=len(LIFESTYLE_TOOLS) * 282,  # 14 tools
            color="#FF9800",  # Orange
            icon="🌟"
        ),
        
        AgentProfile.PFC: ToolProfile(
            name="PFC Expert",
            description="ITASCA PFC simulation specialist with file operations and analysis tools",
            tools=PFC_TOOLS,
            estimated_tokens=len(PFC_TOOLS) * 282,  # Currently 10 basic tools, will expand in future
            color="#9C27B0",  # Purple
            icon="⚛️"
        ),
        
        AgentProfile.GENERAL: ToolProfile(
            name="General",
            description="Full tool capabilities, suitable for complex tasks",
            tools=GENERAL_TOOLS,
            estimated_tokens=len(GENERAL_TOOLS) * 282,  # Using GENERAL_TOOLS length
            color="#607D8B",  # Blue-grey
            icon="🤖"
        ),
        
        AgentProfile.DISABLED: ToolProfile(
            name="Disabled",
            description="No tools enabled, pure conversation mode",
            tools=[],  # 空列表，但通过特殊逻辑处理为禁用所有工具
            estimated_tokens=0,  # No tools
            color="#F44336",  # Red
            icon="🚫"
        )
    }
    
    @classmethod
    def get_profile(cls, profile: AgentProfile) -> ToolProfile:
        """Get agent profile configuration"""
        return cls.TOOL_PROFILES[profile]
    
    @classmethod
    def get_tools_for_profile(cls, profile: AgentProfile) -> List[str]:
        """Get tool list for specified profile"""
        profile_config = cls.TOOL_PROFILES[profile]
        return profile_config.tools
    
    @classmethod
    def get_available_profiles(cls) -> Dict[str, Dict[str, Any]]:
        """Get all available agent profile configurations (for frontend display)"""
        return {
            profile.value: {
                "name": config.name,
                "description": config.description,
                "estimated_tokens": config.estimated_tokens,
                "tool_count": len(config.tools) if config.tools else 24,
                "color": config.color,
                "icon": config.icon
            }
            for profile, config in cls.TOOL_PROFILES.items()
        }
    