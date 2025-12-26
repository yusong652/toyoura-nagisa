"""Markdown formatter for PFC command documentation.

This module formats command documentation and model properties as markdown
for LLM consumption.

Formatting Goals:
- Clear structure with headers
- Concise but complete information
- Highlight key syntax and examples
- Include Python SDK alternatives when available
"""

from typing import Dict, Any, List
from backend.infrastructure.pfc.commands.models import CommandSearchResult, DocumentType


class CommandFormatter:
    """Format PFC command documentation as markdown.

    This class provides static methods for formatting commands and model
    properties in a consistent, LLM-friendly markdown format.
    """

    @staticmethod
    def format_command(doc: Dict[str, Any], category: str) -> str:
        """Format a full command documentation as markdown.

        Args:
            doc: Command documentation dict
            category: Command category (e.g., "ball", "contact")

        Returns:
            Formatted markdown string

        Example:
            >>> doc = {"command": "ball create", "syntax": "...", ...}
            >>> md = CommandFormatter.format_command(doc, "ball")
            >>> "## Syntax" in md
            True
        """
        parts = []

        # Header
        command_name = doc.get("command", "Unknown Command")
        parts.append(f"# {command_name}")
        parts.append("")

        # Description
        description = doc.get("description", "")
        if description:
            parts.append(description)
            parts.append("")

        # Syntax
        syntax = doc.get("syntax", "")
        if syntax:
            parts.append("## Syntax")
            parts.append("```")
            parts.append(syntax)
            parts.append("```")
            parts.append("")

        # Keywords
        keywords = doc.get("keywords", [])
        if keywords:
            parts.append("## Keywords")
            for kw in keywords:
                kw_name = kw.get("name", "")
                kw_syntax = kw.get("syntax", "")
                kw_desc = kw.get("description", "")

                # Format: syntax as header, description as content
                if kw_syntax:
                    parts.append(f"### `{kw_syntax}`")
                else:
                    parts.append(f"### `{kw_name}`")

                if kw_desc:
                    parts.append(kw_desc)
                parts.append("")

        # Examples
        examples = doc.get("examples", [])
        if examples:
            parts.append("## Examples")
            for example in examples:
                example_desc = example.get("description", "")
                example_command = example.get("command", "")

                if example_desc:
                    parts.append(example_desc)

                if example_command:
                    parts.append("```")
                    parts.append(example_command)
                    parts.append("```")
                parts.append("")
            parts.append("")

        # Notes (moved before Python Usage for better visibility)
        notes = doc.get("notes", [])
        if notes:
            parts.append("## Important Notes")
            for note in notes:
                parts.append(f"- {note}")
            parts.append("")

        # Python SDK Alternative (supports both old and new format)
        python_alt = doc.get("python_alternative", "")
        python_sdk_alt = doc.get("python_sdk_alternative", {})

        if python_sdk_alt:
            # New format - directly embed workaround field
            workaround = python_sdk_alt.get("workaround", "")
            if workaround:
                parts.append("## Python Usage")
                parts.append(workaround)
                parts.append("")

        elif python_alt:
            # Old format - keep for backward compatibility
            parts.append("## Python SDK Alternative")
            parts.append(python_alt)
            parts.append("")

        # Related Commands
        related = doc.get("related_commands", [])
        if related:
            parts.append("## Related Commands")
            for rel_cmd in related:
                parts.append(f"- {rel_cmd}")
            parts.append("")

        return "\n".join(parts)

    @staticmethod
    def format_search_results(results: List[CommandSearchResult]) -> str:
        """Format search results as a summary list.

        Args:
            results: List of CommandSearchResult objects

        Returns:
            Formatted markdown string with result summaries

        Example:
            >>> results = [CommandSearchResult(...), ...]
            >>> md = CommandFormatter.format_search_results(results)
            >>> "Found" in md
            True
        """
        if not results:
            return "No results found."

        parts = [f"Found {len(results)} result(s):", ""]

        for i, result in enumerate(results, 1):
            type_label = "[CMD]" if result.doc_type == DocumentType.COMMAND else "[MODEL]"
            score_indicator = "★★★" if result.score >= 900 else ("★★" if result.score >= 700 else "★")

            # Format display name
            display_name = result.name
            if result.doc_type == DocumentType.MODEL_PROPERTY and result.metadata:
                full_name = result.metadata.get("full_name")
                if full_name:
                    display_name = f"{result.name} - {full_name}"

            parts.append(f"{i}. **{type_label} {display_name}** {score_indicator}")

            if result.metadata:
                # For commands, show short_description; for models, show description or common_use
                desc = (result.metadata.get("short_description") or
                       result.metadata.get("description") or
                       result.metadata.get("common_use"))
                if desc:
                    # Truncate long descriptions
                    desc = desc[:100] + "..." if len(desc) > 100 else desc
                    parts.append(f"   {desc}")

            parts.append("")

        return "\n".join(parts)

    @staticmethod
    def format_no_results_response(query: str) -> str:
        """Format a helpful message when no results are found.

        Args:
            query: Original search query

        Returns:
            Formatted markdown string with suggestions
        """
        return f"""No PFC command documentation found for '{query}'.

Suggestions:
- Try simpler keywords (e.g., "ball create" instead of "how to create a ball")
- Command categories: ball, wall, clump, contact, model, fragment, measure
- For contact model properties: use pfc_browse_reference tool
- For Python SDK: use pfc_query_python_api tool

Common commands:
- ball create, ball generate, ball attribute
- wall generate, wall attribute
- contact model, contact property, contact cmat
- model cycle, model solve, model domain
"""
