"""PFC Reference Browse Tool - Navigate syntax elements and model properties.

This tool provides unified navigation through PFC reference documentation,
which covers syntax elements used within commands (not standalone commands).

Reference Categories:
- contact-models: Contact model properties (kn, ks, fric, pb_*, etc.)
- range-elements: Range filtering syntax (future)

Use this tool to understand syntax elements that modify command behavior.
"""

from typing import Dict, Any, Optional
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
                "- 'contact-models hertz': Hertz model properties"
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
        - Setting up "contact cmat add model ... property ..." commands

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
