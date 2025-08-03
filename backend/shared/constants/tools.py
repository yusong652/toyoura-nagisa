"""
Tool-related constants for the aiNagisa project.

This module defines constants used across different components for tool management,
ensuring consistency in tool identification and categorization.
"""

from typing import Set

# Meta tools that provide system-level functionality and should not be vectorized
# These tools are always available and part of the core infrastructure
META_TOOLS: Set[str] = {
    "get_available_tool_categories",
    "search_tools"
}