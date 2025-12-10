"""PFC Contact Models Browse Tool - Navigate and retrieve contact model documentation.

This tool provides navigation through PFC Contact Model documentation,
which is separate from Command documentation in the official PFC docs.

Contact Models define mechanical behavior at contact points (stiffness, friction, bonding).
Commands (like 'contact property') are used to SET these properties.

Use this tool to understand what properties are available for each contact model.
"""

from typing import Dict, Any, Optional
from fastmcp import FastMCP
from pydantic import Field

from backend.infrastructure.pfc.commands import CommandLoader, CommandFormatter
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response


def register_pfc_browse_contact_models_tool(mcp: FastMCP):
    """Register PFC contact models browse tool with the MCP server."""

    @mcp.tool(
        tags={"pfc", "contact", "model", "browse", "documentation"},
        annotations={"category": "pfc", "tags": ["pfc", "contact-model", "browse"]}
    )
    async def pfc_browse_contact_models(
        model: Optional[str] = Field(
            None,
            description=(
                "Contact model name to browse. Examples:\n"
                "- None or '': List all available contact models\n"
                "- 'linear': Linear elastic-frictional model (default)\n"
                "- 'hertz': Hertzian nonlinear model\n"
                "- 'linearpbond': Linear parallel bond model\n"
                "- 'linearcbond': Linear contact bond model\n"
                "- 'rrlinear': Rolling resistance linear model"
            )
        )
    ) -> Dict[str, Any]:
        """Browse PFC contact model properties (like glob + cat for model docs).

        Contact models define mechanical behavior at contact points (kn, ks, fric, etc.).

        Navigation levels:
        - No model: List all 5 built-in contact models
        - Model name (e.g., "linear"): Full property documentation

        When to use:
        - Need to know property names for contact model configuration
        - Setting up "contact cmat add model ... property ..." commands

        Related tools:
        - pfc_browse_commands: Command syntax (e.g., "contact cmat")
        - pfc_query_command: Search commands by keywords
        """
        try:
            # Normalize model input
            model = _normalize_model(model)

            if not model:
                return _browse_models_index()
            else:
                return _browse_model_doc(model)

        except FileNotFoundError as e:
            return error_response(f"Documentation not found: {str(e)}")
        except Exception as e:
            return error_response(f"Error browsing contact models: {str(e)}")

    print("[DEBUG] Registered PFC contact models browse tool: pfc_browse_contact_models")


def _normalize_model(model: Optional[str]) -> str:
    """Normalize model input."""
    if model is None:
        return ""
    return model.strip().lower()


def _browse_models_index() -> Dict[str, Any]:
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
- pfc_browse_contact_models(model="<name>") for model properties

Usage with commands:
- contact cmat add model <name> property <prop> <value>
- contact property <prop> <value> range ...
"""

    return success_response(
        message=f"PFC Contact Models: {len(models)} models",
        llm_content={"parts": [{"type": "text", "text": content}]},
        data={
            "level": "index",
            "models": [m.get("name") for m in models]
        }
    )


def _browse_model_doc(model_name: str) -> Dict[str, Any]:
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
- pfc_browse_contact_models() for all models list

Usage:
- contact cmat add model {model} property <prop> <value>
- contact property <prop> <value> range model {model}
""".format(model=model_name)

    full_content = formatted_doc + navigation

    return success_response(
        message=f"Contact Model: {model_name}",
        llm_content={"parts": [{"type": "text", "text": full_content}]},
        data={
            "level": "model",
            "model": model_name
        }
    )
