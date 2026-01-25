"""PFC Command Browse Tool - Navigate and retrieve command documentation.

This tool provides hierarchical navigation through PFC command documentation,
similar to 'glob + cat' for file systems. It enables LLM to:
1. Discover available command categories and commands (understand boundaries)
2. Retrieve full documentation by exact command

Use pfc_query_command for keyword-based search when command is unknown.
"""

from typing import Dict, Any, Optional

from backend.application.tools.registrar import ToolRegistrar
from pydantic import Field

from backend.infrastructure.pfc.commands import CommandLoader, CommandFormatter
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.application.tools.pfc.utils import normalize_input


def register_pfc_browse_commands_tool(registrar: ToolRegistrar):
    """Register PFC command browse tool with the registrar."""

    @registrar.tool(
        tags={"pfc", "command", "browse", "documentation"},
        annotations={"category": "pfc", "tags": ["pfc", "command", "browse"]}
    )
    async def pfc_browse_commands(
        command: Optional[str] = Field(
            None,
            description=(
                "PFC command to browse (space-separated, matching PFC syntax). Examples:\n"
                "- None or '': List all command categories\n"
                "- 'ball': List all ball commands\n"
                "- 'ball create': Get ball create documentation\n"
                "- 'contact': List all contact commands\n"
                "- 'contact property': Get contact property command documentation"
            )
        )
    ) -> Dict[str, Any]:
        """Browse PFC command documentation by path (like glob + cat).

        Navigation levels:
        - No command: All 7 categories overview
        - Category only (e.g., "ball"): List commands in category
        - Full command (e.g., "ball create"): Full documentation

        When to use:
        - You know the command category or exact command
        - You want to explore available commands

        Related tools:
        - pfc_query_command: Search commands by keywords (when path unknown)
        - pfc_browse_reference: Browse reference docs (e.g., "contact-models linear")
        """
        try:
            # Normalize command input
            cmd = normalize_input(command)

            # Route to appropriate handler based on command depth
            if not cmd:
                return _browse_root()

            parts = cmd.split()

            # Standard category/command navigation
            if len(parts) == 1:
                return _browse_category(parts[0])
            else:
                # Join all parts after category as command name
                # This handles commands like "contact cmat add" -> category="contact", command="cmat add"
                category = parts[0]
                command_name = " ".join(parts[1:])
                return _browse_command(category, command_name)

        except FileNotFoundError as e:
            return error_response(f"Documentation not found: {str(e)}")
        except Exception as e:
            return error_response(f"Error browsing documentation: {str(e)}")



def _browse_root() -> Dict[str, Any]:
    """Level 0: Return overview of all command categories."""
    index = CommandLoader.load_index()
    categories = index.get("categories", {})

    content = CommandFormatter.format_root(categories)
    total_commands = sum(
        len(cat_data.get("commands", []))
        for cat_data in categories.values()
    )

    return success_response(
        message=f"PFC Command Documentation: {len(categories)} categories, {total_commands} commands",
        llm_content={"parts": [{"type": "text", "text": content}]},
        data={
            "level": "root",
            "categories": list(categories.keys()),
            "total_commands": total_commands
        }
    )


def _browse_category(category: str) -> Dict[str, Any]:
    """Level 1: Return list of commands in a category."""
    index = CommandLoader.load_index()
    categories = index.get("categories", {})

    if category not in categories:
        available = ", ".join(categories.keys())
        error_msg = f"Category '{category}' not found. Available: {available}"
        # Fallback to root with complete content
        root_content = CommandFormatter.format_root(categories)
        fallback_content = CommandFormatter.format_with_error(error_msg, root_content)
        return error_response(
            error_msg,
            llm_content={"parts": [{"type": "text", "text": fallback_content}]}
        )

    cat_data = categories[category]
    commands = cat_data.get("commands", [])
    full_name = cat_data.get("full_name", category.title())

    content = CommandFormatter.format_category(category, cat_data)

    return success_response(
        message=f"{full_name}: {len(commands)} commands",
        llm_content={"parts": [{"type": "text", "text": content}]},
        data={
            "level": "category",
            "category": category,
            "command_count": len(commands),
            "commands": [cmd.get("name") for cmd in commands]
        }
    )


def _browse_command(category: str, command_name: str) -> Dict[str, Any]:
    """Level 2: Return full documentation for a specific command."""
    # Load command documentation
    cmd_doc = CommandLoader.load_command_doc(category, command_name)

    if not cmd_doc:
        # Try to provide helpful suggestions
        index = CommandLoader.load_index()
        categories = index.get("categories", {})

        if category not in categories:
            available_cats = ", ".join(categories.keys())
            error_msg = f"Category '{category}' not found. Available: {available_cats}"
            # Fallback to root with complete content
            root_content = CommandFormatter.format_root(categories)
            fallback_content = CommandFormatter.format_with_error(error_msg, root_content)
            return error_response(
                error_msg,
                llm_content={"parts": [{"type": "text", "text": fallback_content}]}
            )

        cat_data = categories[category]
        commands = cat_data.get("commands", [])

        # Command not found - fallback to category with complete content
        available_cmds = [cmd.get("name") for cmd in commands]
        error_msg = (
            f"Command '{command_name}' not found in '{category}'. "
            f"Available: {', '.join(available_cmds[:10])}{'...' if len(available_cmds) > 10 else ''}"
        )
        category_content = CommandFormatter.format_category(category, cat_data)
        fallback_content = CommandFormatter.format_with_error(error_msg, category_content)
        return error_response(
            error_msg,
            llm_content={"parts": [{"type": "text", "text": fallback_content}]}
        )

    # Format the documentation
    formatted_doc = CommandFormatter.format_command(cmd_doc, category)

    # Add navigation footer
    navigation = f"""

Navigation:
- pfc_browse_commands(command="{category}") for {category} commands list
- pfc_browse_commands() for categories overview
"""
    full_content = formatted_doc + navigation

    return success_response(
        message=f"Documentation: {category} {command_name}",
        llm_content={"parts": [{"type": "text", "text": full_content}]},
        data={
            "level": "command",
            "category": category,
            "command": command_name,
            "full_command": f"{category} {command_name}"
        }
    )
