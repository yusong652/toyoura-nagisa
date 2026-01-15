"""
Shared tool schema models and utilities for LLM providers.

Provides common data structures and processing logic for tool schemas
across different LLM providers (Gemini, Anthropic, OpenAI, etc.).
"""

from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


def transform_schema_for_openai_compat(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform JSON Schema to OpenAI-compatible format.

    OpenAI function calling (and compatible APIs like OpenRouter, Zhipu, Moonshot)
    have limited support for:
    - $ref references (need to be inlined)
    - anyOf with null (should use "type": ["<type>", "null"] instead)

    This function:
    1. Dereferences all $ref by inlining definitions from $defs
    2. Converts anyOf: [{...}, {type: null}] to type: [<type>, "null"]

    Args:
        schema: Original JSON Schema (may contain $ref and anyOf)

    Returns:
        Transformed schema compatible with OpenAI function calling
    """
    if not isinstance(schema, dict):
        return schema

    # Extract $defs for reference resolution
    defs = schema.get("$defs", schema.get("definitions", {}))

    def resolve_ref(ref_path: str) -> Dict[str, Any] | None:
        """Resolve a $ref path to its definition."""
        if ref_path.startswith("#/$defs/") or ref_path.startswith("#/definitions/"):
            def_name = ref_path.split("/")[-1]
            if def_name in defs:
                return defs[def_name].copy()
        return None

    def transform_value(value: Any) -> Any:
        """Recursively transform a schema value."""
        if not isinstance(value, dict):
            return value

        # Handle $ref - inline the referenced definition
        if "$ref" in value:
            resolved = resolve_ref(value["$ref"])
            if resolved:
                # Preserve description from original if not in resolved
                if "description" in value and "description" not in resolved:
                    resolved["description"] = value["description"]
                return transform_value(resolved)
            return value

        # Handle anyOf with null - convert to type array format
        if "anyOf" in value:
            any_of = value["anyOf"]
            # Check if this is Optional pattern: anyOf: [{...}, {type: null}]
            if len(any_of) == 2:
                null_item = None
                other_item = None
                for item in any_of:
                    if isinstance(item, dict):
                        if item.get("type") == "null":
                            null_item = item
                        else:
                            other_item = item

                if null_item is not None and other_item is not None:
                    # Transform the non-null item first (may contain $ref)
                    transformed_other = transform_value(other_item)

                    # Build result with nullable flag (more compatible than type array)
                    # Gemini uses nullable:true, OpenAI accepts both formats
                    result = transformed_other.copy()

                    # Mark as nullable
                    result["nullable"] = True

                    # Copy description from original anyOf wrapper if not in transformed
                    if "description" in value and "description" not in result:
                        result["description"] = value["description"]
                    if "default" in value:
                        result["default"] = value["default"]

                    return result

            # For other anyOf patterns, transform each item
            result = value.copy()
            result["anyOf"] = [transform_value(item) for item in any_of]
            return result

        # Handle properties recursively
        result = {}
        for key, val in value.items():
            if key == "properties" and isinstance(val, dict):
                result[key] = {k: transform_value(v) for k, v in val.items()}
            elif key == "items":
                result[key] = transform_value(val) if isinstance(val, dict) else val
            elif key in ("$defs", "definitions"):
                # Remove $defs from output - we've inlined everything
                continue
            else:
                result[key] = val

        return result

    return transform_value(schema)


class JSONSchema(BaseModel):
    """JSON Schema representation for tool parameters."""
    
    type: str = "object"
    properties: Dict[str, Any] = Field(default_factory=dict)
    required: List[str] = Field(default_factory=list)
    description: Optional[str] = None
    title: Optional[str] = None
    default: Optional[Any] = None
    enum: Optional[List[Any]] = None
    items: Optional[Union[Dict[str, Any], "JSONSchema"]] = None
    # Allow common JSON Schema fields
    definitions: Optional[Dict[str, Any]] = Field(default=None, alias="$defs")
    defs: Optional[Dict[str, Any]] = Field(default=None, alias="definitions")
    
    model_config = {"extra": "allow"}  # Allow additional JSON Schema fields
        
    @field_validator('properties')
    @classmethod
    def ensure_property_descriptions(cls, v):
        """Ensure all properties have descriptions."""
        if isinstance(v, dict):
            for prop_schema in v.values():
                if isinstance(prop_schema, dict) and "description" not in prop_schema:
                    prop_schema["description"] = "Parameter value"
        return v
    
    @model_validator(mode='after')
    def validate_required(self):
        """Validate that required fields exist in properties."""
        # Don't auto-infer required fields - respect what the schema provides
        # An empty required list means all fields are optional
        if self.required:
            # Only validate that required fields exist in properties
            for field in self.required:
                if field not in self.properties:
                    # Remove invalid required field
                    self.required.remove(field)
        return self


class ToolSchema(BaseModel):
    """Standardized tool schema representation."""
    
    name: str
    description: str = "No description available"
    inputSchema: JSONSchema = Field(default_factory=JSONSchema)
    
    @classmethod
    def from_mcp_tool(cls, mcp_tool) -> "ToolSchema":
        """Create ToolSchema from MCP tool object."""
        input_schema_dict = getattr(mcp_tool, "inputSchema", {}) or {}
        
        # Ensure proper structure
        if not isinstance(input_schema_dict, dict):
            input_schema_dict = {"type": "object", "properties": {}}
        
        return cls(
            name=mcp_tool.name,
            description=mcp_tool.description or "No description available",
            inputSchema=JSONSchema(**input_schema_dict)
        )
    
    @classmethod
    def from_dict(cls, tool_dict: Dict[str, Any]) -> "ToolSchema":
        """Create ToolSchema from dictionary representation."""
        input_schema = tool_dict.get("inputSchema", {})
        
        # Handle legacy 'parameters' field
        if not input_schema and "parameters" in tool_dict:
            parameters = tool_dict["parameters"]
            if isinstance(parameters, dict):
                if "type" in parameters and "properties" in parameters:
                    input_schema = parameters
                else:
                    input_schema = {
                        "type": "object",
                        "properties": parameters,
                        "required": list(parameters.keys()) if parameters else []
                    }
        
        # Ensure proper structure
        if not isinstance(input_schema, dict):
            input_schema = {"type": "object", "properties": {}}
            
        return cls(
            name=tool_dict["name"],
            description=tool_dict.get("description", "No description available"),
            inputSchema=JSONSchema(**input_schema)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.inputSchema.model_dump(exclude_none=True, by_alias=True)
        }