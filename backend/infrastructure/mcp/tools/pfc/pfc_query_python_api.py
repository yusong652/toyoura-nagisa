"""PFC Python API Query Tool - MCP wrapper for SDK documentation queries.

This MCP tool enables LLM to query PFC Python API documentation and should
be used FIRST before falling back to itasca.command() strings.

This is a thin wrapper around the core SDK documentation utilities in
backend.infrastructure.pfc.sdk_docs, handling only MCP protocol integration
and error response formatting.
"""

from typing import Dict, Any
from fastmcp import FastMCP
from fastmcp.server.context import Context
from pydantic import Field

from backend.infrastructure.pfc.sdk_docs import search_api, load_api_doc, format_api_doc, load_index
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response


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
                "Keyword query for PFC Python SDK. Use short phrases like "
                "'create ball', 'list balls', 'ball velocity', 'delete contact'."
            )
        )
    ) -> Dict[str, Any]:
        """
        Search PFC Python SDK documentation by keywords - ALWAYS TRY THIS FIRST!

        Uses keyword matching to find Python API methods. Python SDK is preferred
        over itasca.command() for type safety and maintainability.

        Examples:
        - "create ball" → itasca.ball.create()
        - "list balls" → itasca.ball.list()
        - "ball velocity" → Ball.vel()

        If no Python SDK exists for your operation, this tool will suggest
        using pfc_query_command instead.
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
                        f"⚠️ {hints[0]}\n\n"
                        f"Use pfc_query_command tool to search for PFC commands instead."
                    )

                return error_response(
                    f"No Python SDK API found for '{operation}'.\n\n"
                    f"**Next step**: Use pfc_query_command tool to search for PFC commands."
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
