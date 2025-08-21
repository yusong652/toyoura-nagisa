# LLM Tool Schema Payload Format

This document details how tool schemas flow from FastMCP to LLMs (Gemini and Anthropic) through aiNagisa's architecture.

## Overview

The tool schema payload process follows this flow:
```
FastMCP → ToolSchema → GeminiToolManager → Gemini API → Gemini LLM
```

## 1. FastMCP Schema Generation

FastMCP automatically generates JSON schemas based on Pydantic Field definitions:

```python
@mcp.tool()
def create_calendar_event(
    summary: str = Field(..., description="Event summary (required)"),
    start: Dict[str, int] = Field(..., description="Start time (required)"),
    end: Optional[Dict[str, int]] = Field(None, description="End time (optional)"),
    location: Optional[str] = Field(None, description="Location (optional)"),
) -> Dict[str, Any]:
    """Create a new event in Google Calendar."""
    pass
```

Generates this JSON schema:
```json
{
  "type": "object",
  "properties": {
    "summary": {
      "type": "string",
      "description": "Event summary (required)"
    },
    "start": {
      "type": "object", 
      "description": "Start time (required)"
    },
    "end": {
      "anyOf": [{"type": "object"}, {"type": "null"}],
      "default": null,
      "description": "End time (optional)"
    },
    "location": {
      "anyOf": [{"type": "string"}, {"type": "null"}], 
      "default": null,
      "description": "Location (optional)"
    }
  },
  "required": ["summary", "start"]  // ← Key: only fields with Field(...) 
}
```

### Field Mapping Rules
- `Field(...)` → Added to `required` array
- `Field(None, ...)` or `Optional[Type]` → Not in `required` array
- `anyOf` structure for optional fields to allow `null`

## 2. ToolSchema Conversion

The `ToolSchema` class converts MCP tools to standardized format:

```python
class ToolSchema(BaseModel):
    name: str
    description: str
    inputSchema: JSONSchema

@classmethod
def from_mcp_tool(cls, mcp_tool) -> "ToolSchema":
    input_schema_dict = getattr(mcp_tool, "inputSchema", {}) or {}
    return cls(
        name=mcp_tool.name,
        description=mcp_tool.description,
        inputSchema=JSONSchema(**input_schema_dict)  # Preserves 'required' array
    )
```

**Key Fix Applied**: `JSONSchema` no longer auto-infers all fields as required when `required` array is empty.

## 3. GeminiToolManager Processing  

Converts ToolSchema to Gemini's `FunctionDeclaration` format:

```python
def _convert_tool_schema_to_gemini_declaration(self, tool_schema: ToolSchema):
    func_decl_dict = {
        "name": tool_schema.name,
        "description": tool_schema.description,
        "parameters": self._sanitize_jsonschema_for_gemini(
            tool_schema.inputSchema.model_dump(exclude_none=True)
        )
    }
    return types.FunctionDeclaration(**func_decl_dict)
```

### Schema Sanitization

The sanitization preserves `required` fields:

```python
def _sanitize_jsonschema_for_gemini(self, schema: dict) -> dict:
    ALLOWED_KEYS = {
        "type", "properties", "required", "description",  # ← 'required' preserved
        "enum", "items", "default", "title"
    }
    
    cleaned = {}
    for key, value in schema.items():
        if key in ALLOWED_KEYS:
            cleaned[key] = value  # ← Preserves original 'required' array
    
    # Key Fix: Removed auto-inference logic that made all fields required
    return cleaned
```

## 4. Final Gemini API Payload

The complete payload structure sent to Gemini:

```python
config = types.GenerateContentConfig(
    system_instruction="...",
    tools=[
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name='create_calendar_event',
                    description='Create a new event in Google Calendar.',
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        required=['summary', 'start'],  # ← Critical: tells Gemini which are required
                        properties={
                            'summary': types.Schema(
                                type=types.Type.STRING,
                                description='Event summary (required)'
                            ),
                            'start': types.Schema(
                                type=types.Type.OBJECT,
                                description='Start time (required)'
                            ),
                            'end': types.Schema(
                                type=types.Type.OBJECT,
                                description='End time (optional)',
                                # Note: Optional fields can be omitted from call
                            ),
                            'location': types.Schema(
                                type=types.Type.STRING,
                                description='Location (optional)'
                            )
                        }
                    )
                )
            ]
        )
    ],
    temperature=0.7,
    max_output_tokens=4096
)

# API call
response = client.models.generate_content(
    model="gemini-2.0-flash-exp",
    contents=[...],
    config=config
)
```

## 5. Gemini LLM Understanding

Gemini receives the schema and understands:

### Required Parameters (must be provided)
- `summary`: String - Event title
- `start`: Object - Start time

### Optional Parameters (can be omitted)
- `end`: Object or null - End time  
- `location`: String or null - Location
- `description`: String or null - Description

## Tool Call Examples

### Valid Call (required fields provided)
```json
{
  "name": "create_calendar_event",
  "arguments": {
    "summary": "Team Meeting",
    "start": {"year": 2025, "month": 1, "day": 15, "hour": 14, "minute": 0}
  }
}
```

### Invalid Call (missing required field)
```json
{
  "name": "create_calendar_event", 
  "arguments": {
    "end": {"year": 2025, "month": 1, "day": 15, "hour": 15, "minute": 0}
    // ❌ Missing 'summary' and 'start' - Gemini should not generate this
  }
}
```

## Key Insights

1. **`required` Array is Critical**: This tells Gemini LLM which parameters must be included in function calls.

2. **FastMCP Handles Detection**: Uses Pydantic `Field(...)` vs `Field(None, ...)` to determine requirements.

3. **Preservation Through Pipeline**: Each stage preserves the `required` array without modification.

4. **LLM Compliance**: Gemini respects the schema and won't call functions with missing required parameters.

## Debugging Tools

To inspect the full payload flow:

```bash
python test_gemini_payload.py  # Shows complete schema transformation
python test_final_validation.py  # Validates end-to-end flow
```

## Common Issues (Fixed)

1. **Auto-inference Bug**: Previously, empty `required` arrays were interpreted as "all required"
2. **Schema Sanitization**: Gemini sanitizer was adding all fields to `required`
3. **ToolSchema Conversion**: Was not preserving original `required` specifications

All these issues have been resolved to ensure accurate parameter requirement communication to Gemini LLM.