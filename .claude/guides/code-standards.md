# Code Quality and Documentation Standards

**For aiNagisa project development**

## Type Validation and Logic Redundancy

### Principles
- **Avoid Redundant Validation**: Do not add type validation or existence checks for data structures that are already validated by our established logic flow
- **Trust Internal APIs**: Internal function calls within our controlled codebase should not re-validate data that has already been processed and validated
- **Readability Priority**: Excessive type checking and defensive programming significantly reduces code readability and maintainability
- **Focus on Business Logic**: Code should focus on the core business logic rather than redundant defensive checks

### Example
If a `ToolResult` object is passed from our standardized tool pipeline, trust that it contains the expected structure rather than re-validating every field.

---

## Function Documentation Requirements

All functions MUST follow these documentation standards:

### Type Annotations
- **Required**: All function parameters and return types must have explicit type annotations
- **Imports**: Import all required types from `typing` or appropriate modules
- **Specificity**: Use specific types (e.g., `CallToolResult`) rather than generic `Any` when possible

### Docstring Format
```python
def function_name(param: SpecificType) -> ReturnType:
    """
    Brief function description in imperative mood.

    Detailed explanation of function behavior, including any important
    implementation details or architectural considerations.

    Args:
        param: Description with structure details when applicable:
            - field1: Description of nested field
            - field2: Description of nested field

    Returns:
        ReturnType: Description with complete structure:
            - field1: Type - Description
            - field2: Type - Description
            - field3: Optional[Type] - Description when optional

    Example:
        # Practical usage example when helpful
        result = function_name(example_param)

    Note:
        Important implementation notes or cross-references to related modules.
    """
```

### Documentation Quality Standards
- **Language**: Professional English, concise and effective
- **Structure**: Clear Args/Returns sections with nested field descriptions
- **Cross-references**: Reference related modules/classes when relevant
- **Examples**: Include practical examples for complex functions
- **Return Structure**: Document complete return structure matching actual models (e.g., ToolResult schema)

### Example Implementation
```python
from typing import Dict, Any
from mcp.types import CallToolResult

def extract_tool_result_from_mcp(result: CallToolResult) -> Dict[str, Any]:
    """
    Extract ToolResult object from MCP CallToolResult response.

    Parses standardized ToolResult JSON from MCP CallToolResult.content[0].text
    and applies MCP error flags when necessary.

    Args:
        result: MCP CallToolResult object with structure:
            - content: List[ContentBlock] containing TextContent
            - isError: bool indicating MCP-level error

    Returns:
        Dict[str, Any]: ToolResult dictionary with structure:
            - status: Literal["success", "error"] - Operation outcome
            - message: str - User-facing summary for display
            - llm_content: Optional[Any] - Structured data for LLM conversation
            - data: Optional[Dict[str, Any]] - Tool-specific payload and metadata
            - error: Optional[str] - Detailed error info when status="error"
            - is_error: bool - Added when MCP marks result as error

    Note:
        All tools return ToolResult.model_dump() as standardized JSON,
        ensuring consistent structure across the MCP ecosystem.
    """
```

---

## Git Configuration

### Commit Message Requirements

When creating commits, follow these guidelines for attribution and project identification:

1. **Project Attribution**: Always reference the aiNagisa project repository URL `https://github.com/yusong652/aiNagisa` in commit messages rather than external tools
2. **Co-authorship**: Use "Co-authored-with: Nagisa Toyoura" to reflect collaborative development instead of external tool attribution
3. **Project Context**: Ensure commit messages reflect the aiNagisa project context and goals

### Example Commit Format
```
feat: improve tool extraction logic

Enhance MCP tool result processing for better LLM integration
in the aiNagisa voice-enabled AI assistant.

https://github.com/yusong652/aiNagisa

Co-authored-with: Nagisa Toyoura <nagisa.toyoura@gmail.com>
```

---

**These standards ensure consistent, maintainable, and well-documented code across the aiNagisa project.**
