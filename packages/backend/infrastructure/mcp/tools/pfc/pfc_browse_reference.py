"""PFC Reference Browse Tool - Navigate syntax elements and model properties.

This tool provides unified navigation through PFC reference documentation,
which covers syntax elements used within commands (not standalone commands).

Reference Categories:
- contact-models: Contact model properties (kn, ks, fric, pb_*, etc.)
- range-elements: Range filtering syntax (position, cylinder, group, id, etc.)

Use this tool to understand syntax elements that modify command behavior.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from fastmcp import FastMCP
from pydantic import Field

from backend.infrastructure.pfc.commands import CommandLoader, CommandFormatter
from backend.infrastructure.pfc.config import PFC_REFERENCES_ROOT
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

    # Dispatch to category-specific handler
    if category == "contact-models":
        return _browse_contact_models_index()
    elif category == "range-elements":
        return _browse_range_elements_index()
    else:
        return error_response(f"Category '{category}' not yet implemented")


def _browse_contact_models_index() -> Dict[str, Any]:
    """Return list of available contact models."""
    model_index = CommandLoader.load_model_properties_index()

    if not model_index:
        return error_response("Contact model documentation not found")

    models = model_index.get("models", [])

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
            "models": [m.get("name") for m in models]
        }
    )


def _browse_item(category: str, item: str) -> Dict[str, Any]:
    """Level 2: Return full documentation for a specific item."""
    if category == "contact-models":
        return _browse_contact_model_doc(item)
    elif category == "range-elements":
        return _browse_range_element_doc(item)
    else:
        return error_response(f"Category '{category}' not yet implemented")


def _browse_contact_model_doc(model_name: str) -> Dict[str, Any]:
    """Return full documentation for a specific contact model."""
    model_doc = CommandLoader.load_model_property_doc(model_name)

    if not model_doc:
        # Get available models for error message
        model_index = CommandLoader.load_model_properties_index()
        available = [m.get("name") for m in model_index.get("models", [])]
        return error_response(
            f"Model '{model_name}' not found. Available: {', '.join(available)}"
        )

    # Format the model documentation
    formatted_doc = CommandFormatter.format_full_model(model_doc)

    # Add navigation footer
    navigation = """

Navigation:
- pfc_browse_reference(topic="contact-models") for all models list
- pfc_browse_reference() for reference categories

Usage:
- contact cmat add model {model} property <prop> <value>
- contact property <prop> <value> range model {model}
""".format(model=model_name)

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


def _browse_range_elements_index() -> Dict[str, Any]:
    """Return overview of range elements reference."""
    # Load the main range-phrase document to get element list
    doc_path = PFC_REFERENCES_ROOT / "range-elements" / "range-phrase.json"

    if not doc_path.exists():
        return error_response("Range elements documentation not found")

    with open(doc_path, 'r', encoding='utf-8') as f:
        doc_data = json.load(f)

    # Build element list by category
    category_lines = []
    all_elements = []
    for category in doc_data.get("categories", []):
        cat_name = category.get("name", "")
        elements = category.get("elements", [])
        element_names = [e.get("name", "") for e in elements]
        all_elements.extend(element_names)
        category_lines.append(f"**{cat_name}**: {', '.join(element_names)}")

    # Common examples
    examples = doc_data.get("common_patterns", [])[:3]
    example_lines = []
    for ex in examples:
        example_lines.append(f"- {ex.get('example', '')}")

    content = f"""## PFC Range Elements Reference

Range elements filter objects by geometric regions, attributes, or logical conditions.
Used after the 'range' keyword in PFC commands.

**Usage Pattern**: `<command> ... range <element> [params]`

### Available Elements ({len(all_elements)} total)

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
        message=f"Range Elements: {len(all_elements)} elements",
        llm_content={"parts": [{"type": "text", "text": content}]},
        data={
            "level": "category",
            "category": "range-elements",
            "elements": all_elements
        }
    )


def _browse_range_element_doc(element_name: str) -> Dict[str, Any]:
    """Return documentation for a specific range element.

    Args:
        element_name: Element keyword like 'position', 'cylinder', 'group', etc.
    """
    doc_path = PFC_REFERENCES_ROOT / "range-elements" / "range-phrase.json"

    if not doc_path.exists():
        return error_response("Range elements documentation not found")

    with open(doc_path, 'r', encoding='utf-8') as f:
        doc_data = json.load(f)

    # Search for specific element in categories
    found_element = None
    found_category = None
    for category in doc_data.get("categories", []):
        for element in category.get("elements", []):
            if element.get("name") == element_name:
                found_element = element
                found_category = category.get("name", "")
                break
        if found_element:
            break

    if not found_element:
        # List available elements
        available = _get_all_range_element_names(doc_data)
        return error_response(
            f"Element '{element_name}' not found. Available: {', '.join(available[:20])}..."
        )

    # Format single element documentation
    content = _format_single_range_element(found_element, found_category, doc_data)

    return success_response(
        message=f"Range Element: {element_name}",
        llm_content={"parts": [{"type": "text", "text": content}]},
        data={
            "level": "item",
            "category": "range-elements",
            "item": element_name
        }
    )


def _get_all_range_element_names(doc_data: Dict[str, Any]) -> list:
    """Extract all element names from range-phrase document."""
    names = []
    for category in doc_data.get("categories", []):
        for element in category.get("elements", []):
            name = element.get("name", "")
            if name:
                names.append(name)
    return names


def _format_single_range_element(element: Dict[str, Any], category_name: str, doc_data: Dict[str, Any]) -> str:
    """Format a single range element as markdown."""
    parts = []

    elem_name = element.get("name", "")
    elem_syntax = element.get("syntax", "")
    alt_syntax = element.get("alt_syntax", "")
    elem_desc = element.get("description", "")
    elem_examples = element.get("examples", [])
    parameters = element.get("parameters", [])
    supports_extent = element.get("supports_extent", False)
    notes = element.get("notes", [])
    related = element.get("related", [])

    # Header
    parts.append(f"# range {elem_name}")
    parts.append(f"*Category: {category_name}*")
    parts.append("")

    # Syntax
    if elem_syntax:
        parts.append("## Syntax")
        parts.append(f"```")
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

    # Usage pattern reminder
    usage = doc_data.get("usage_pattern", {})
    usage_notes = usage.get("notes", [])
    if usage_notes:
        parts.append("## General Notes")
        for note in usage_notes:
            parts.append(f"- {note}")
        parts.append("")

    # Navigation
    parts.append("---")
    parts.append("Navigation:")
    parts.append('- pfc_browse_reference(topic="range-elements") for overview')

    return "\n".join(parts)
