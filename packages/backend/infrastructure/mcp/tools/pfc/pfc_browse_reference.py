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
                "- 'range-elements': Range filtering syntax overview\n"
                "- 'range-elements range-phrase': Full range element reference"
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
    index_path = PFC_REFERENCES_ROOT / "range-elements" / "index.json"

    if not index_path.exists():
        return error_response("Range elements documentation not found")

    with open(index_path, 'r', encoding='utf-8') as f:
        index_data = json.load(f)

    documents = index_data.get("documents", [])
    quick_ref = index_data.get("quick_reference", {})
    examples = index_data.get("common_examples", [])

    # Build content
    doc_lines = []
    for doc in documents:
        name = doc.get("name", "")
        title = doc.get("title", name)
        desc = doc.get("description", "")
        doc_lines.append(f"- {name}: {title}")
        if desc:
            doc_lines.append(f"  {desc}")

    # Quick reference by category
    quick_lines = []
    for cat, elements in quick_ref.items():
        quick_lines.append(f"- {cat}: {', '.join(elements)}")

    content = f"""## PFC Range Elements Reference

Range elements filter objects by geometric regions, attributes, or logical conditions.
Used after the 'range' keyword in PFC commands.

**Usage Pattern**: `<command> ... range <element> [params]`

### Available Documents
{chr(10).join(doc_lines)}

### Quick Reference
{chr(10).join(quick_lines)}

### Common Examples
```
{chr(10).join(examples)}
```

Navigation:
- pfc_browse_reference(topic="range-elements range-phrase") for full reference
- pfc_browse_reference() for all categories

Usage examples:
- ball delete range position-x 0 10
- ball attribute density 2650 range group 'sample'
- contact property fric 0.5 range cylinder end-1 0 0 0 end-2 0 0 10 radius 5
"""

    return success_response(
        message=f"Range Elements: {len(documents)} documents",
        llm_content={"parts": [{"type": "text", "text": content}]},
        data={
            "level": "category",
            "category": "range-elements",
            "documents": [d.get("name") for d in documents]
        }
    )


def _browse_range_element_doc(doc_name: str) -> Dict[str, Any]:
    """Return full documentation for a specific range element document."""
    doc_path = PFC_REFERENCES_ROOT / "range-elements" / f"{doc_name}.json"

    if not doc_path.exists():
        # Try to list available documents
        index_path = PFC_REFERENCES_ROOT / "range-elements" / "index.json"
        available = []
        if index_path.exists():
            with open(index_path, 'r', encoding='utf-8') as f:
                index_data = json.load(f)
                available = [d.get("name") for d in index_data.get("documents", [])]
        return error_response(
            f"Document '{doc_name}' not found. Available: {', '.join(available)}"
        )

    with open(doc_path, 'r', encoding='utf-8') as f:
        doc_data = json.load(f)

    # Format the range elements documentation
    content = _format_range_elements_doc(doc_data)

    return success_response(
        message=f"Range Elements: {doc_data.get('title', doc_name)}",
        llm_content={"parts": [{"type": "text", "text": content}]},
        data={
            "level": "item",
            "category": "range-elements",
            "item": doc_name
        }
    )


def _format_range_elements_doc(doc: Dict[str, Any]) -> str:
    """Format range elements documentation as markdown."""
    parts = []

    # Header
    title = doc.get("title", "Range Elements")
    parts.append(f"# {title}")
    parts.append("")

    description = doc.get("description", "")
    if description:
        parts.append(description)
        parts.append("")

    # Usage pattern
    usage = doc.get("usage_pattern", {})
    if usage:
        syntax = usage.get("syntax", "")
        examples = usage.get("examples", [])
        notes = usage.get("notes", [])

        parts.append("## Usage Pattern")
        if syntax:
            parts.append(f"**Syntax**: `{syntax}`")
            parts.append("")
        if examples:
            parts.append("**Examples**:")
            parts.append("```")
            for ex in examples:
                parts.append(ex)
            parts.append("```")
            parts.append("")
        if notes:
            parts.append("**Notes**:")
            for note in notes:
                parts.append(f"- {note}")
            parts.append("")

    # Categories
    categories = doc.get("categories", [])
    for cat in categories:
        cat_name = cat.get("name", "")
        cat_desc = cat.get("description", "")
        elements = cat.get("elements", [])

        parts.append(f"## {cat_name}")
        if cat_desc:
            parts.append(f"*{cat_desc}*")
            parts.append("")

        for elem in elements:
            elem_name = elem.get("name", "")
            elem_syntax = elem.get("syntax", "")
            alt_syntax = elem.get("alt_syntax", "")
            elem_desc = elem.get("description", "")
            elem_examples = elem.get("examples", [])
            supports_extent = elem.get("supports_extent", False)

            parts.append(f"### {elem_name}")
            if elem_syntax:
                parts.append(f"**Syntax**: `{elem_syntax}`")
            if alt_syntax:
                parts.append(f"**Alt**: `{alt_syntax}`")
            if elem_desc:
                parts.append(f"**Description**: {elem_desc}")
            if supports_extent:
                parts.append("*Supports `extent` modifier*")
            if elem_examples:
                parts.append("**Examples**:")
                for ex in elem_examples:
                    parts.append(f"- `{ex}`")
            parts.append("")

    # Common patterns
    patterns = doc.get("common_patterns", [])
    if patterns:
        parts.append("## Common Patterns")
        for pattern in patterns:
            name = pattern.get("name", "")
            example = pattern.get("example", "")
            desc = pattern.get("description", "")
            parts.append(f"### {name}")
            if desc:
                parts.append(desc)
            if example:
                parts.append("```")
                parts.append(example)
                parts.append("```")
            parts.append("")

    # Navigation footer
    parts.append("---")
    parts.append("Navigation:")
    parts.append("- pfc_browse_reference(topic=\"range-elements\") for overview")
    parts.append("- pfc_browse_reference() for all categories")

    return "\n".join(parts)
