"""PFC Command Browse Tool - Navigate and retrieve command documentation.

This tool provides hierarchical navigation through PFC command documentation,
similar to 'glob + cat' for file systems. It enables LLM to:
1. Discover available command categories and commands (understand boundaries)
2. Retrieve full documentation by exact command

Use pfc_query_command for keyword-based search when command is unknown.
"""

from typing import Dict, Any, Optional
from fastmcp import FastMCP
from pydantic import Field

from backend.infrastructure.pfc.commands import CommandLoader, CommandFormatter
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response


def register_pfc_browse_commands_tool(mcp: FastMCP):
    """Register PFC command browse tool with the MCP server."""

    @mcp.tool(
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
            cmd = _normalize_command(command)

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

    print("[DEBUG] Registered PFC command browse tool: pfc_browse_commands")


def _normalize_command(command: Optional[str]) -> str:
    """Normalize command input."""
    if command is None:
        return ""
    # Strip whitespace and normalize multiple spaces to single space
    return " ".join(command.split())


def _browse_root() -> Dict[str, Any]:
    """Level 0: Return overview of all command categories."""
    index = CommandLoader.load_index()
    categories = index.get("categories", {})

    # Build category summary
    category_lines = []
    total_commands = 0
    for cat_name, cat_data in categories.items():
        cmd_count = len(cat_data.get("commands", []))
        total_commands += cmd_count
        description = cat_data.get("description", "")
        # Truncate long descriptions
        if len(description) > 50:
            description = description[:47] + "..."

        category_lines.append(f"- {cat_name} ({cmd_count}): {description}")

    content = f"""## PFC Command Documentation

Total: {len(categories)} categories, {total_commands} commands

{chr(10).join(category_lines)}

Navigation:
- pfc_browse_commands(command="<category>") to list commands
- pfc_browse_commands(command="<category> <cmd>") for full doc

Search: pfc_query_command(query="...") for keyword search

Contact Models: pfc_browse_reference(topic="contact-models") for model properties
"""

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
        return error_response(
            f"Category '{category}' not found. Available: {available}"
        )

    cat_data = categories[category]
    commands = cat_data.get("commands", [])
    full_name = cat_data.get("full_name", category.title())
    description = cat_data.get("description", "")

    # Build command list
    command_lines = []
    for cmd in commands:
        name = cmd.get("name", "")
        python_avail = cmd.get("python_available", False)
        if python_avail is True:
            python_mark = "[py]"
        elif python_avail == "partial":
            python_mark = "[py:partial]"
        else:
            python_mark = ""

        short_desc = cmd.get("short_description", "")
        if len(short_desc) > 45:
            short_desc = short_desc[:42] + "..."

        command_lines.append(f"- {name}{' ' + python_mark if python_mark else ''}: {short_desc}")

    # Related categories
    related = cat_data.get("related_categories", [])
    related_text = f"Related: {', '.join(related)}" if related else ""

    # Special note for contact category
    contact_note = ""
    if category == "contact":
        contact_note = '\nContact Models: pfc_browse_reference(topic="contact-models") for model properties'

    content = f"""## {full_name} ({len(commands)} commands)

{description}

{chr(10).join(command_lines)}

[py] = Python SDK available, [py:partial] = partial support

Navigation:
- pfc_browse_commands(command="{category} <cmd>") for full doc
- pfc_browse_commands() for categories overview
{contact_note}
{related_text}
"""

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


def _browse_subcommand_group(category: str, group_name: str, commands: list) -> Dict[str, Any]:
    """Level 1.5: Return list of subcommands in a group (e.g., 'cmat' subcommands)."""
    # Build subcommand list
    command_lines = []
    for cmd in commands:
        name = cmd.get("name", "")
        # Extract subcommand name (e.g., "cmat add" -> "add")
        subcommand = name[len(group_name) + 1:] if name.startswith(group_name + " ") else name

        python_avail = cmd.get("python_available", False)
        if python_avail is True:
            python_mark = "[py]"
        elif python_avail == "partial":
            python_mark = "[py:partial]"
        else:
            python_mark = ""

        short_desc = cmd.get("short_description", "")
        if len(short_desc) > 45:
            short_desc = short_desc[:42] + "..."

        command_lines.append(f"- {subcommand}{' ' + python_mark if python_mark else ''}: {short_desc}")

    content = f"""## {category} {group_name} ({len(commands)} subcommands)

{chr(10).join(command_lines)}

[py] = Python SDK available, [py:partial] = partial support

Navigation:
- pfc_browse_commands(command="{category} {group_name} <subcommand>") for full doc
- pfc_browse_commands(command="{category}") for all {category} commands
"""

    return success_response(
        message=f"{category} {group_name}: {len(commands)} subcommands",
        llm_content={"parts": [{"type": "text", "text": content}]},
        data={
            "level": "subcommand_group",
            "category": category,
            "group": group_name,
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
            return error_response(
                f"Category '{category}' not found. Available: {available_cats}"
            )

        cat_data = categories[category]
        commands = cat_data.get("commands", [])
        available_cmds = [cmd.get("name") for cmd in commands]

        # Check if command_name is a subcommand prefix (e.g., "cmat" matches "cmat add", "cmat apply")
        matching_commands = [cmd for cmd in commands if cmd.get("name", "").startswith(command_name + " ")]
        if matching_commands:
            # Treat as subcommand group browsing (like category browsing)
            return _browse_subcommand_group(category, command_name, matching_commands)

        return error_response(
            f"Command '{command_name}' not found in '{category}'. "
            f"Available: {', '.join(available_cmds[:10])}{'...' if len(available_cmds) > 10 else ''}"
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


