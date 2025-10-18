"""
PFC Python API Query Tool - documentation lookup for PFC Python SDK.

This tool enables LLM to query PFC Python API documentation and should
be used FIRST before falling back to itasca.command() strings.
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastmcp import FastMCP
from fastmcp.server.context import Context
from pydantic import Field
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response

DOCS_DIR = Path(__file__).parent / "docs" / "python_sdk"


def load_index() -> Dict[str, Any]:
    """Load the index file for fast lookups."""
    index_path = DOCS_DIR / "index.json"
    if not index_path.exists():
        raise FileNotFoundError(f"Index file not found: {index_path}")

    with open(index_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def search_api(query: str) -> Optional[str]:
    """
    Search for API based on query keywords.

    Args:
        query: Natural language query like "create a ball"

    Returns:
        API name like "itasca.ball.create" or None if not found
    """
    index = load_index()
    query_lower = query.lower()

    # Try direct API name match first
    if query in index["quick_ref"]:
        return query

    # Try keyword match with flexible word matching
    # Split both keyword and query into words and check if all keyword words are in query
    query_words = set(query_lower.split())

    best_match = None
    best_score = 0

    for keyword, apis in index["keywords"].items():
        keyword_words = set(keyword.split())
        # Calculate how many keyword words match
        matching_words = keyword_words & query_words
        score = len(matching_words)

        # If all keyword words are in query, it's a valid match
        if matching_words == keyword_words and score > best_score:
            best_match = apis[0]
            best_score = score

    return best_match


def load_api_doc(api_name: str) -> Optional[Dict[str, Any]]:
    """
    Load documentation for a specific API.

    Args:
        api_name: Full API name like "itasca.ball.create"

    Returns:
        API documentation dict or None if not found
    """
    index = load_index()

    # Get file reference from index
    ref = index["quick_ref"].get(api_name)
    if not ref:
        return None

    # Parse file path and anchor
    file_name, anchor = ref.split('#')
    doc_path = DOCS_DIR / file_name

    if not doc_path.exists():
        return None

    with open(doc_path, 'r', encoding='utf-8') as f:
        doc = json.load(f)

    # Find the specific function or method
    if anchor.startswith("Ball."):
        # Object method
        method_name = anchor.replace("Ball.", "")
        for method in doc.get("object_methods", []):
            if method["name"] == method_name:
                return method
    else:
        # Module function
        for func in doc.get("functions", []):
            if func["name"] == anchor:
                return func

    return None


def format_api_doc(api_doc: Dict[str, Any], api_name: str) -> str:
    """
    Format API documentation as LLM-friendly markdown.

    Args:
        api_doc: API documentation dictionary
        api_name: Full API name for reference

    Returns:
        Formatted markdown string
    """
    lines = []

    # Header
    lines.append(f"# {api_name}")
    lines.append("")
    lines.append(f"**Signature**: `{api_doc['signature']}`")
    lines.append("")

    # Description
    lines.append(api_doc['description'])
    lines.append("")

    # Parameters
    if api_doc.get('parameters'):
        lines.append("## Parameters")
        for param in api_doc['parameters']:
            required = "**required**" if param['required'] else "*optional*"
            lines.append(f"- **`{param['name']}`** ({param['type']}, {required}): {param['description']}")
        lines.append("")

    # Returns
    if api_doc.get('returns'):
        ret = api_doc['returns']
        lines.append(f"## Returns")
        lines.append(f"**`{ret['type']}`**: {ret['description']}")
        lines.append("")

    # Examples
    if api_doc.get('examples'):
        lines.append("## Examples")
        for i, ex in enumerate(api_doc['examples'], 1):
            lines.append(f"### Example {i}: {ex['description']}")
            lines.append("```python")
            lines.append(ex['code'])
            lines.append("```")
            lines.append("")

    # Limitations (IMPORTANT - guides to command fallback)
    if api_doc.get('limitations'):
        lines.append("## ⚠️ Limitations")
        lines.append(api_doc['limitations'])
        lines.append("")

        if api_doc.get('fallback_commands'):
            lines.append(f"**When to use commands instead**: {', '.join(api_doc['fallback_commands'])}")
            lines.append("")

    # Best Practices
    if api_doc.get('best_practices'):
        lines.append("## 💡 Best Practices")
        for bp in api_doc['best_practices']:
            lines.append(f"- {bp}")
        lines.append("")

    # Notes
    if api_doc.get('notes'):
        lines.append("## 📝 Notes")
        for note in api_doc['notes']:
            lines.append(f"- {note}")
        lines.append("")

    # See Also
    if api_doc.get('see_also'):
        lines.append(f"**See Also**: {', '.join(api_doc['see_also'])}")
        lines.append("")

    return "\n".join(lines)


def register_pfc_query_python_api_tool(mcp: FastMCP):
    """Register PFC Python API query tool with the MCP server."""

    @mcp.tool(
        tags={"pfc", "python", "api", "documentation"},
        annotations={"category": "pfc", "tags": ["pfc", "python", "documentation"]}
    )
    async def pfc_query_python_api(
        context: Context,
        operation: str = Field(
            ...,
            description=(
                "Describe what you want to do with PFC Python SDK. "
                "Examples: 'create a ball', 'list all balls', 'get ball velocity', 'find ball by id'"
            )
        )
    ) -> Dict[str, Any]:
        """
        Query PFC Python SDK documentation - ALWAYS TRY THIS FIRST!

        This tool searches for Python API methods to accomplish your goal.
        Python SDK is preferred over itasca.command() for type safety and better code quality.

        If Python SDK cannot do what you need, this tool will suggest command fallback.

        Usage strategy:
        1. Query this tool FIRST for any PFC operation
        2. If SDK exists, use the returned Python API (preferred)
        3. If SDK insufficient, see the fallback command suggestion
        4. Only use pfc_query_command tool if explicitly needed

        Examples:
        - "create a ball" → returns itasca.ball.create()
        - "list all balls" → returns itasca.ball.list()
        - "create 1000 balls in cubic packing" → returns ball.create() with limitation note
        """
        try:
            # Search for matching API
            api_name = search_api(operation)

            if not api_name:
                # Check fallback hints
                index = load_index()
                hints = []
                for hint_key, hint_msg in index.get("fallback_hints", {}).items():
                    if hint_key in operation.lower():
                        hints.append(hint_msg)

                if hints:
                    return error_response(
                        f"No Python SDK API found for '{operation}'.\n\n"
                        f"Suggestion: {hints[0]}\n\n"
                        f"Use pfc_query_command tool to search for PFC commands instead.",
                        llm_content={
                            "parts": [{
                                "type": "text",
                                "text": f"⚠️ Python SDK cannot do this operation.\n\n{hints[0]}"
                            }]
                        }
                    )

                return error_response(
                    f"No Python SDK API found for '{operation}'. "
                    f"Try pfc_query_command tool to search for commands instead.",
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": f"⚠️ No Python SDK API found for: {operation}\n\n"
                                   f"**Next step**: Use pfc_query_command tool to search for PFC commands."
                        }]
                    }
                )

            # Load API documentation
            api_doc = load_api_doc(api_name)

            if not api_doc:
                return error_response(f"API documentation not found for {api_name}")

            # Format documentation
            formatted_doc = format_api_doc(api_doc, api_name)

            return success_response(
                message=f"Found Python SDK API: {api_name}",
                llm_content={
                    "parts": [{
                        "type": "text",
                        "text": f"✅ **Python SDK Available** (preferred approach)\n\n{formatted_doc}"
                    }]
                },
                data={
                    "api_name": api_name,
                    "signature": api_doc['signature'],
                    "has_limitations": bool(api_doc.get('limitations')),
                    "fallback_commands": api_doc.get('fallback_commands', [])
                }
            )

        except FileNotFoundError as e:
            return error_response(f"Documentation files not found: {str(e)}")
        except Exception as e:
            return error_response(f"Error querying Python API: {str(e)}")

    print("[DEBUG] Registered PFC Python API query tool: pfc_query_python_api")
