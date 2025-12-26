"""PFC Reference Browse Tool - Navigate syntax elements and model properties.

This tool provides unified navigation through PFC reference documentation,
which covers syntax elements used within commands (not standalone commands).

Reference Categories:
- contact-models: Contact model properties (kn, ks, fric, pb_*, etc.)
- range-elements: Range filtering syntax (position, cylinder, group, id, etc.)

Use this tool to understand syntax elements that modify command behavior.
"""

from typing import Dict, Any, Optional, List
from fastmcp import FastMCP
from pydantic import Field

from backend.infrastructure.pfc.commands import CommandLoader, CommandFormatter
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response


def register_pfc_browse_reference_tool(mcp: FastMCP):
    """Register PFC reference browse tool with the MCP server."""

    @mcp.tool(
        tags={"pfc", "reference", "browse", "documentation"},
        annotations={"category": "pfc", "tags": ["pfc", "reference", "browse"]}
    )
    async def pfc_browse_reference(
        topic: Optional[str] = Field(
            None,
            description=(
                "Reference topic to browse (space-separated path). Examples:\n"
                "- None or '': List all reference categories\n"
                "- 'contact-models': List all contact models\n"
                "- 'contact-models linear': Linear model properties\n"
                "- 'range-elements': Range elements overview (24 elements)\n"
                "- 'range-elements position': Position range syntax\n"
                "- 'range-elements cylinder': Cylinder range syntax\n"
                "- 'range-elements group': Group range syntax"
            )
        )
    ) -> Dict[str, Any]:
        """Browse PFC reference documentation (syntax elements, model properties).

        References are language elements used within commands, not standalone commands.

        Navigation levels:
        - No topic: All reference categories
        - Category (e.g., "contact-models"): List items in category
        - Full path (e.g., "contact-models linear"): Full documentation

        When to use:
        - Need contact model property names (kn, ks, fric, pb_*)
        - Need range filtering syntax (position, cylinder, group, id)
        - Setting up "contact cmat add model ... property ..." commands
        - Using range filters in any PFC command

        Related tools:
        - pfc_browse_commands: Command syntax (e.g., "ball create")
        - pfc_query_command: Search commands by keywords
        """
        try:
            # Normalize topic input
            topic = _normalize_topic(topic)

            if not topic:
                return _browse_references_root()

            parts = topic.split()
            category = parts[0]

            if len(parts) == 1:
                return _browse_category(category)
            else:
                item = " ".join(parts[1:])
                return _browse_item(category, item)

        except FileNotFoundError as e:
            return error_response(f"Documentation not found: {str(e)}")
        except Exception as e:
            return error_response(f"Error browsing references: {str(e)}")

    print("[DEBUG] Registered PFC reference browse tool: pfc_browse_reference")


def _normalize_topic(topic: Optional[str]) -> str:
    """Normalize topic input."""
    if topic is None:
        return ""
    return " ".join(topic.strip().lower().split())


def _browse_references_root() -> Dict[str, Any]:
    """Level 0: Return overview of all reference categories."""
    refs_index = CommandLoader.load_references_index()

    if not refs_index:
        return error_response("Reference documentation not found")

    categories = refs_index.get("categories", {})

    # Build category summary
    category_lines = []
    for cat_name, cat_data in categories.items():
        name = cat_data.get("name", cat_name)
        desc = cat_data.get("description", "")
        summary = cat_data.get("summary", "")
        if len(desc) > 50:
            desc = desc[:47] + "..."
        category_lines.append(f"- {cat_name}: {desc}")
        if summary:
            category_lines.append(f"  ({summary})")

    content = f"""## PFC Reference Documentation

References are syntax elements used within commands, not standalone commands.

Total: {len(categories)} categories

{chr(10).join(category_lines)}

Navigation:
- pfc_browse_reference(topic="<category>") to list items
- pfc_browse_reference(topic="<category> <item>") for full doc

Related:
- pfc_browse_commands: Command syntax
- pfc_query_command: Search commands by keywords
"""

    return success_response(
        message=f"PFC Reference Documentation: {len(categories)} categories",
        llm_content={"parts": [{"type": "text", "text": content}]},
        data={
            "level": "root",
            "categories": list(categories.keys())
        }
    )


def _browse_category(category: str) -> Dict[str, Any]:
    """Level 1: Return list of items in a reference category."""
    refs_index = CommandLoader.load_references_index()
    categories = refs_index.get("categories", {})

    if category not in categories:
        available = ", ".join(categories.keys())
        return error_response(
            f"Category '{category}' not found. Available: {available}"
        )

    # Use unified loader to get category index
    cat_index = CommandLoader.load_reference_category_index(category)
    if not cat_index:
        return error_response(f"Category '{category}' index not found")

    # Dispatch to category-specific formatter
    if category == "contact-models":
        return _format_contact_models_index(cat_index)
    elif category == "range-elements":
        return _format_range_elements_index(cat_index)
    else:
        return error_response(f"Category '{category}' not yet implemented")


def _format_contact_models_index(index: Dict[str, Any]) -> Dict[str, Any]:
    """Format contact models category index."""
    models = index.get("models", [])

    # Build model list
    model_lines = []
    for model in models:
        name = model.get("name", "")
        full_name = model.get("full_name", name)
        desc = model.get("description", "")
        if len(desc) > 45:
            desc = desc[:42] + "..."
        model_lines.append(f"- {name} ({full_name}): {desc}")

    content = f"""## PFC Contact Models

Contact models define mechanical behavior at contact points.
Total: {len(models)} built-in models

{chr(10).join(model_lines)}

Common Properties:
- kn: Normal stiffness [force/length]
- ks: Shear stiffness [force/length]
- fric: Friction coefficient
- pb_*: Parallel bond properties
- cb_*: Contact bond properties

Navigation:
- pfc_browse_reference(topic="contact-models <name>") for model properties

Usage with commands:
- contact cmat add model <name> property <prop> <value>
- contact property <prop> <value> range ...
"""

    return success_response(
        message=f"PFC Contact Models: {len(models)} models",
        llm_content={"parts": [{"type": "text", "text": content}]},
        data={
            "level": "category",
            "category": "contact-models",
            "items": [m.get("name") for m in models]
        }
    )


def _format_range_elements_index(index: Dict[str, Any]) -> Dict[str, Any]:
    """Format range elements category index."""
    categories = index.get("categories", {})
    elements = index.get("elements", [])

    # Build element list by category
    category_lines = []
    for cat_key, cat_data in categories.items():
        cat_name = cat_data.get("name", cat_key)
        cat_elements = cat_data.get("elements", [])
        category_lines.append(f"**{cat_name}**: {', '.join(cat_elements)}")

    all_element_names = [e.get("name", "") for e in elements]

    content = f"""## PFC Range Elements Reference

Range elements filter objects by geometric regions, attributes, or logical conditions.
Used after the 'range' keyword in PFC commands.

**Usage Pattern**: `<command> ... range <element> [params]`

### Available Elements ({len(all_element_names)} total)

{chr(10).join(category_lines)}

### Common Examples
```
ball delete range position-x 0 10
ball attribute density 2650 range group 'sample'
contact property fric 0.5 range cylinder end-1 0 0 0 end-2 0 0 10 radius 5
```

### Navigation

Browse specific element:
- pfc_browse_reference(topic="range-elements position")
- pfc_browse_reference(topic="range-elements cylinder")
- pfc_browse_reference(topic="range-elements group")
"""

    return success_response(
        message=f"Range Elements: {len(all_element_names)} elements",
        llm_content={"parts": [{"type": "text", "text": content}]},
        data={
            "level": "category",
            "category": "range-elements",
            "items": all_element_names
        }
    )


def _browse_item(category: str, item: str) -> Dict[str, Any]:
    """Level 2: Return full documentation for a specific item."""
    # Use unified loader
    item_doc = CommandLoader.load_reference_item_doc(category, item)

    if not item_doc:
        # Get available items for error message
        items = CommandLoader.get_reference_item_list(category)
        available = [i.get("name", "") for i in items]
        return error_response(
            f"Item '{item}' not found in '{category}'. Available: {', '.join(available[:15])}{'...' if len(available) > 15 else ''}"
        )

    # Dispatch to category-specific formatter
    if category == "contact-models":
        return _format_contact_model_doc(item_doc)
    elif category == "range-elements":
        return _format_range_element_doc(item_doc)
    else:
        return error_response(f"Category '{category}' not yet implemented")


def _format_contact_model_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Format contact model documentation."""
    model_name = doc.get("model", "")

    # Format the model documentation using existing formatter
    formatted_doc = CommandFormatter.format_full_model(doc)

    # Add navigation footer
    navigation = f"""

Navigation:
- pfc_browse_reference(topic="contact-models") for all models list
- pfc_browse_reference() for reference categories

Usage:
- contact cmat add model {model_name} property <prop> <value>
- contact property <prop> <value> range model {model_name}
"""

    full_content = formatted_doc + navigation

    return success_response(
        message=f"Contact Model: {model_name}",
        llm_content={"parts": [{"type": "text", "text": full_content}]},
        data={
            "level": "item",
            "category": "contact-models",
            "item": model_name
        }
    )


def _format_range_element_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Format range element documentation."""
    parts = []

    elem_name = doc.get("name", "")
    category_name = doc.get("category_name", doc.get("category", ""))
    elem_syntax = doc.get("syntax", "")
    alt_syntax = doc.get("alt_syntax", "")
    elem_desc = doc.get("description", "")
    elem_examples = doc.get("examples", [])
    parameters = doc.get("parameters", [])
    supports_extent = doc.get("supports_extent", False)
    notes = doc.get("notes", [])
    related = doc.get("related", [])

    # Header
    parts.append(f"# range {elem_name}")
    parts.append(f"*Category: {category_name}*")
    parts.append("")

    # Syntax
    if elem_syntax:
        parts.append("## Syntax")
        parts.append("```")
        parts.append(f"range {elem_syntax}")
        parts.append("```")
        if alt_syntax:
            parts.append(f"**Alternative**: `range {alt_syntax}`")
        parts.append("")

    # Description
    if elem_desc:
        parts.append("## Description")
        parts.append(elem_desc)
        parts.append("")

    # Parameters
    if parameters:
        parts.append("## Parameters")
        parts.append("| Parameter | Type | Description |")
        parts.append("|-----------|------|-------------|")
        for param in parameters:
            p_name = param.get("name", "")
            p_type = param.get("type", "")
            p_desc = param.get("description", "")
            parts.append(f"| `{p_name}` | {p_type} | {p_desc} |")
        parts.append("")

    # Modifiers
    if supports_extent:
        parts.append("## Modifiers")
        parts.append("- Supports `extent` modifier (require entire object inside region)")
        parts.append("")

    # Examples
    if elem_examples:
        parts.append("## Examples")
        parts.append("```")
        for ex in elem_examples:
            parts.append(ex)
        parts.append("```")
        parts.append("")

    # Notes
    if notes:
        parts.append("## Notes")
        for note in notes:
            parts.append(f"- {note}")
        parts.append("")

    # Related
    if related:
        parts.append("## Related")
        for rel in related:
            parts.append(f"- `{rel}`")
        parts.append("")

    # Navigation
    parts.append("---")
    parts.append("Navigation:")
    parts.append('- pfc_browse_reference(topic="range-elements") for overview')

    content = "\n".join(parts)

    return success_response(
        message=f"Range Element: {elem_name}",
        llm_content={"parts": [{"type": "text", "text": content}]},
        data={
            "level": "item",
            "category": "range-elements",
            "item": elem_name
        }
    )
