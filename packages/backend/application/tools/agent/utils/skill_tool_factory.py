"""Utility for dynamically creating Literal type for skill names.

Provides type construction helpers for the trigger_skill tool.
"""

import logging
from typing import Any, Dict, List, Literal, Optional

from backend.infrastructure.skills import get_skills_loader

logger = logging.getLogger(__name__)


def get_skill_literal_type():
    """
    Create a Literal type containing all available skill names.

    Returns:
        Literal type with skill names, or str as fallback if no skills
    """
    try:
        loader = get_skills_loader()
        names = loader.list_skills()
        if names:
            return Literal[tuple(names)]  # type: ignore
        return str
    except Exception as e:
        logger.warning(f"Failed to load skills for type construction: {e}")
        return str


def get_skill_description() -> str:
    """
    Generate skill parameter description with examples.

    Returns:
        Description string with available skill examples
    """
    try:
        loader = get_skills_loader()
        names = loader.list_skills()
        if names:
            examples = ", ".join(f'"{s}"' for s in names[:3])
            return f'The skill name. E.g., {examples}'
        return "The skill name"
    except Exception:
        return "The skill name"


def build_session_skill_input_schema(
    base_schema: Dict[str, Any],
    enabled_skills: List[str],
) -> Dict[str, Any]:
    """
    Build a session-specific input schema for trigger_skill tool.

    Creates a new schema dict with the 'skill' parameter's enum updated
    to only include session-enabled skills. Does NOT mutate the original schema.

    Args:
        base_schema: Original input_schema from the registered tool
        enabled_skills: List of skill names enabled for the current session

    Returns:
        New input_schema dict with session-specific skill enum
    """
    import copy

    # Deep copy to avoid mutating the original
    schema = copy.deepcopy(base_schema)

    if "properties" not in schema:
        return schema

    skill_prop = schema["properties"].get("skill")
    if not isinstance(skill_prop, dict):
        return schema

    if enabled_skills:
        skill_prop["enum"] = enabled_skills
        examples = ", ".join(f'"{s}"' for s in enabled_skills[:3])
        skill_prop["description"] = f"The skill name. Available: {examples}"
    else:
        # No skills enabled - set empty enum
        skill_prop["enum"] = []
        skill_prop["description"] = "No skills enabled for this session"

    return schema


def customize_trigger_skill_schema(
    original_tool_schema: Any,
    enabled_skills: List[str],
) -> Any:
    """
    Create a session-customized ToolSchema for trigger_skill.

    Returns a NEW ToolSchema with session-specific skill enum.
    Does NOT mutate the original schema object.

    Args:
        original_tool_schema: The original ToolSchema from registry
        enabled_skills: List of skill names enabled for the session

    Returns:
        New ToolSchema with customized inputSchema
    """
    from backend.infrastructure.llm.shared.utils.tool_schema import ToolSchema, JSONSchema

    # Get the original input schema as dict
    original_input = original_tool_schema.inputSchema.model_dump(exclude_none=True, by_alias=True)

    # Build session-specific schema (creates new dict)
    customized_input = build_session_skill_input_schema(original_input, enabled_skills)

    # Create new ToolSchema with customized input
    return ToolSchema(
        name=original_tool_schema.name,
        description=original_tool_schema.description,
        inputSchema=JSONSchema(**customized_input),
    )
