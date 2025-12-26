"""PFC Reference Browse Tool - Navigate syntax elements and model properties.

This tool provides unified navigation through PFC reference documentation,
which covers syntax elements used within commands (not standalone commands).

Reference Categories:
- contact-models: Contact model properties (kn, ks, fric, pb_*, etc.)
- range-elements: Range filtering syntax (position, cylinder, group, id, etc.)

Use this tool to understand syntax elements that modify command behavior.
"""

from typing import Dict, Any, Optional, cast
from fastmcp import FastMCP
from pydantic import Field

from backend.infrastructure.pfc.references import ReferenceLoader, ReferenceFormatter
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.mcp.tools.pfc.utils import normalize_input


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
            topic = normalize_input(topic, lowercase=True)

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


def _browse_references_root() -> Dict[str, Any]:
    """Level 0: Return overview of all reference categories."""
    refs_index = ReferenceLoader.load_index()
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
    refs_index = ReferenceLoader.load_index()
    categories = refs_index.get("categories", {})

    if category not in categories:
        available = ", ".join(categories.keys())
        return error_response(
            f"Category '{category}' not found. Available: {available}"
        )

    # Use unified loader to get category index (category already validated above)
    cat_index = cast(Dict[str, Any], ReferenceLoader.load_category_index(category))

    # Use unified formatter
    content = ReferenceFormatter.format_index(category, cat_index)

    # Extract item names for data field
    items = cat_index.get("models", []) or cat_index.get("elements", [])
    item_names = [i.get("name", "") for i in items]

    return success_response(
        message=f"{category}: {len(item_names)} items",
        llm_content={"parts": [{"type": "text", "text": content}]},
        data={
            "level": "category",
            "category": category,
            "items": item_names
        }
    )


def _browse_item(category: str, item: str) -> Dict[str, Any]:
    """Level 2: Return full documentation for a specific item."""
    # Use unified loader
    item_doc = ReferenceLoader.load_item_doc(category, item)

    if not item_doc:
        # Get available items for error message
        items = ReferenceLoader.get_item_list(category)
        available = [i.get("name", "") for i in items]
        return error_response(
            f"Item '{item}' not found in '{category}'. Available: {', '.join(available[:15])}{'...' if len(available) > 15 else ''}"
        )

    # Use unified formatter based on category
    if category == "contact-models":
        content = ReferenceFormatter.format_contact_model(item_doc)
        item_name = item_doc.get("model", item)
    elif category == "range-elements":
        content = ReferenceFormatter.format_range_element(item_doc)
        item_name = item_doc.get("name", item)
    else:
        return error_response(f"Category '{category}' not yet implemented")

    return success_response(
        message=f"{category}: {item_name}",
        llm_content={"parts": [{"type": "text", "text": content}]},
        data={
            "level": "item",
            "category": category,
            "item": item_name
        }
    )
