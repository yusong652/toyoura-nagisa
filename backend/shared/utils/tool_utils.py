"""
Tool utility functions for the aiNagisa project.

This module provides common utility functions for tool management that can be
shared across different components and modules.
"""

from backend.shared.constants.tools import META_TOOLS


def is_meta_tool(tool_name: str) -> bool:
    """
    Check if a tool is a meta tool (system infrastructure).
    
    Meta tools are system-level tools that provide infrastructure functionality
    like tool discovery and categorization. They should not be vectorized as
    they are always available and part of the core system.
    
    Args:
        tool_name: Tool name to check
        
    Returns:
        bool: True if it's a meta tool, False otherwise
        
    Example:
        >>> is_meta_tool("search_tools")
        True
        >>> is_meta_tool("write_file")
        False
    """
    return tool_name in META_TOOLS