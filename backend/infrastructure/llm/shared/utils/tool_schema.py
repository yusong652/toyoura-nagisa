"""
Shared tool schema models and utilities for LLM providers.

Provides common data structures and processing logic for tool schemas
across different LLM providers (Gemini, Anthropic, OpenAI, etc.).
"""

from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


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
    def auto_infer_required(self):
        """Auto-infer required fields if not explicitly set."""
        if not self.required and self.properties:
            self.required = list(self.properties.keys())
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
            "inputSchema": self.inputSchema.model_dump(exclude_none=True)
        }
    

class ToolSchemaProcessor:
    """Utility class for processing tool schemas."""
    
    @staticmethod
    def normalize_tool_list(tools: List[Dict[str, Any]]) -> List[ToolSchema]:
        """Normalize a list of tool dictionaries to ToolSchema objects."""
        normalized = []
        for tool_dict in tools:
            try:
                tool_schema = ToolSchema.from_dict(tool_dict)
                normalized.append(tool_schema)
            except Exception as e:
                print(f"[WARNING] Failed to normalize tool {tool_dict.get('name', 'unknown')}: {e}")
                continue
        return normalized
    
    @staticmethod
    def convert_mcp_tools(mcp_tools: List[Any]) -> List[ToolSchema]:
        """Convert MCP tools to ToolSchema objects."""
        converted = []
        for mcp_tool in mcp_tools:
            try:
                tool_schema = ToolSchema.from_mcp_tool(mcp_tool)
                converted.append(tool_schema)
            except Exception as e:
                print(f"[WARNING] Failed to convert MCP tool {getattr(mcp_tool, 'name', 'unknown')}: {e}")
                continue
        return converted