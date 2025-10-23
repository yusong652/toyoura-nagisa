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

        # Parameters
        parameters = doc.get("parameters", [])
        if parameters:
            parts.append("## Parameters")
            for param in parameters:
                param_name = param.get("name", "")
                param_desc = param.get("description", "")
                parts.append(f"- **{param_name}**: {param_desc}")
            parts.append("")

        # Examples
        examples = doc.get("examples", [])
        if examples:
            parts.append("## Examples")
            for example in examples:
                example_desc = example.get("description", "")
                example_code = example.get("code", "")
                if example_desc:
                    parts.append(example_desc)
                if example_code:
                    parts.append("```")
                    parts.append(example_code)
                    parts.append("```")
            parts.append("")

        # Python SDK Alternative
        python_alt = doc.get("python_alternative", "")
        if python_alt:
            parts.append("## Python SDK Alternative")
            parts.append(python_alt)
            parts.append("")

        # Notes
        notes = doc.get("notes", [])
        if notes:
            parts.append("## Notes")
            for note in notes:
                parts.append(f"- {note}")
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
    def format_model_property(doc: Dict[str, Any], property_keyword: str) -> str:
        """Format a contact model property documentation as markdown.

        Args:
            doc: Model documentation dict (full model with property_groups)
            property_keyword: Specific property keyword (e.g., "kn", "pb_kn")

        Returns:
            Formatted markdown string

        Example:
            >>> doc = {"model": "linear", "property_groups": [...]}
            >>> md = CommandFormatter.format_model_property(doc, "kn")
            >>> "# linear.kn" in md
            True
        """
        parts = []

        model_name = doc.get("model", "unknown")
        model_full_name = doc.get("full_name", model_name)

        # Find the specific property
        target_property = None
        for group in doc.get("property_groups", []):
            for prop in group.get("properties", []):
                if prop.get("keyword") == property_keyword:
                    target_property = prop
                    break
            if target_property:
                break

        if not target_property:
            return f"# Property {property_keyword} not found in {model_name}"

        # Header
        parts.append(f"# {model_name}.{property_keyword}")
        parts.append(f"*{model_full_name}*")
        parts.append("")

        # Property details
        symbol = target_property.get("symbol", "")
        if symbol:
            parts.append(f"**Symbol**: {symbol}")

        prop_type = target_property.get("type", "")
        if prop_type:
            parts.append(f"**Type**: {prop_type}")

        description = target_property.get("description", "")
        if description:
            parts.append(f"**Description**: {description}")
            parts.append("")

        # Range and default
        prop_range = target_property.get("range", "")
        default = target_property.get("default", "")
        if prop_range or default:
            parts.append("## Value Constraints")
            if prop_range:
                parts.append(f"- **Range**: {prop_range}")
            if default:
                parts.append(f"- **Default**: {default}")
            parts.append("")

        # Flags
        modifiable = target_property.get("modifiable", True)
        inheritable = target_property.get("inheritable", False)
        parts.append("## Property Flags")
        parts.append(f"- **Modifiable**: {'Yes' if modifiable else 'No'}")
        parts.append(f"- **Inheritable**: {'Yes' if inheritable else 'No'}")
        parts.append("")

        # Notes
        notes = target_property.get("notes", "")
        if notes:
            parts.append("## Notes")
            parts.append(notes)
            parts.append("")

        # Usage context
        parts.append("## Usage")
        parts.append("Set this property using:")
        parts.append(f"- Command: `contact cmat add ... property {property_keyword} <value>`")
        parts.append(f"- Command: `contact property {property_keyword} <value> range ...`")
        parts.append(f"- Python: `contact.set_prop('{property_keyword}', value)`")
        parts.append("")

        # Model context
        typical_apps = doc.get("typical_applications", [])
        if typical_apps:
            parts.append(f"## {model_full_name} - Typical Applications")
            for app in typical_apps:
                parts.append(f"- {app}")
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
            type_label = "[CMD]" if result.doc_type == DocumentType.COMMAND else "[PROP]"
            score_indicator = "★★★" if result.score >= 900 else ("★★" if result.score >= 700 else "★")

            parts.append(f"{i}. **{type_label} {result.name}** {score_indicator}")

            if result.metadata:
                desc = result.metadata.get("short_description") or result.metadata.get("description")
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

**Suggestions**:
- Try using simpler keywords (e.g., "ball create" instead of "how to create a ball")
- Check command categories: ball, wall, clump, contact, model, fragment, measure
- Use `include_model_properties=False` if you're only looking for commands
- Try the Python SDK query tool (`pfc_query_python_api`) for Python SDK alternatives

**Common commands**:
- `ball create`, `ball generate`, `ball attribute`
- `wall generate`, `wall attribute`
- `contact model`, `contact property`, `contact cmat`
- `model cycle`, `model solve`, `model domain`
"""
