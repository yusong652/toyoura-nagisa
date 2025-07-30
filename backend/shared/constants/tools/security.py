"""
Tool security constants for session-based access control.

This module defines security policies for tool execution, categorizing tools
based on their session requirements and data sensitivity.

Architecture Design:
- SESSION_REQUIRED_TOOLS: Must have session context (user-specific data)
- SESSION_OPTIONAL_TOOLS: Safe without session (public/stateless data)  
- SESSION_BLOCKED_TOOLS: Blocked without session (security-sensitive)
"""

from typing import FrozenSet

# Tools that REQUIRE session ID for safe execution
# These tools access user-specific or sensitive data and must have session context
SESSION_REQUIRED_TOOLS: FrozenSet[str] = frozenset({
    # Calendar tools - access user's personal calendar
    "list_calendar_events",
    "create_calendar_event", 
    "update_calendar_event",
    "delete_calendar_event",
    
    # Email tools - access user's personal email
    "send_email",
    "list_emails", 
    "get_email",
    "delete_email",
    "search_emails",
    
    # Contact tools - access user's personal contacts
    "get_contacts",
    "create_contact",
    "update_contact", 
    "delete_contact",
    "search_contacts",
    
    # Memory tools - access session-specific conversation history
    "add_memory",
    "search_memory", 
    "get_memory",
    "delete_memory",
    "list_memories",
    
    # Location tools - may access user's personal location data
    "get_location",
    "search_places",
    "get_nearby_places",
    
    # Image generation - may use user-specific quotas/settings
    "generate_image",
    "create_image",
    "edit_image",
    
    # File operations - access user's workspace/files
    "read_file",
    "write_file", 
    "delete_file",
    "list_files",
    "search_files",
    
    # Code execution - security sensitive operations
    "execute_python",
    "run_shell_command",
    "execute_code",
})

# Tools that are SAFE to run without session context
# These tools only access public data or provide stateless utility functions
SESSION_OPTIONAL_TOOLS: FrozenSet[str] = frozenset({
    # Meta tools - tool discovery and system introspection
    "search_tools_by_keywords",
    "get_available_tool_categories", 
    "search_tools",
    "list_available_tools",
    
    # Utility tools - stateless calculations and operations
    "calculate",
    "evaluate_expression",
    "convert_units",
    
    # Time tools - public time information
    "get_time",
    "get_timezone",
    "format_date",
    "parse_date",
    
    # Weather tools - public weather data (location may be provided in args)
    "get_weather",
    "get_forecast",
    "get_weather_alerts",
    
    # Web search - public data access
    "web_search",
    "search_web",
    "fetch_url",
    
    # Text processing - stateless text operations
    "translate_text",
    "analyze_sentiment",
    "extract_keywords",
    "summarize_text",
})

# Tools that should be blocked entirely without session context
# These are aliases or deprecated names that should not run without session
SESSION_BLOCKED_TOOLS: FrozenSet[str] = frozenset({
    # Generic/ambiguous tool names that might be unsafe
    "execute",
    "run",
    "call",
    "invoke",
    
    # Admin/system tools
    "admin_tool",
    "system_tool",
    "debug_tool",
})

def is_session_required_tool(tool_name: str) -> bool:
    """
    Check if a tool requires session ID for safe execution.
    
    Args:
        tool_name: Name of the tool to check
        
    Returns:
        bool: True if tool requires session ID
    """
    return tool_name in SESSION_REQUIRED_TOOLS

def is_session_optional_tool(tool_name: str) -> bool:
    """
    Check if a tool is safe to run without session context.
    
    Args:
        tool_name: Name of the tool to check
        
    Returns:
        bool: True if tool is safe without session ID
    """
    return tool_name in SESSION_OPTIONAL_TOOLS

def is_session_blocked_tool(tool_name: str) -> bool:
    """
    Check if a tool should be blocked without session context.
    
    Args:
        tool_name: Name of the tool to check
        
    Returns:
        bool: True if tool should be blocked
    """
    return tool_name in SESSION_BLOCKED_TOOLS

def get_tool_security_policy(tool_name: str) -> str:
    """
    Get the security policy for a tool.
    
    Args:
        tool_name: Name of the tool to check
        
    Returns:
        str: Security policy - "required", "optional", "blocked", or "unknown"
    """
    if is_session_required_tool(tool_name):
        return "required"
    elif is_session_optional_tool(tool_name):
        return "optional"
    elif is_session_blocked_tool(tool_name):
        return "blocked"
    else:
        return "unknown"