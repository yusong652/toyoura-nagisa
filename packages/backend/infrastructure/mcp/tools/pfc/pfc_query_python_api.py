"""PFC Python API Query Tool - Keyword search for SDK documentation.

This tool searches PFC Python SDK documentation by keywords (like grep).
Returns matching API paths with brief signatures for LLM to identify relevant APIs.

For full documentation, use pfc_browse_python_api with the returned API path.

Workflow:
1. pfc_query_python_api(query="ball position") → Returns matching API paths
2. pfc_browse_python_api(api="itasca.ball.Ball.pos") → Get full documentation
"""

from typing import Dict, Any
from fastmcp import FastMCP
from fastmcp.server.context import Context

from backend.infrastructure.pfc.python_api import (
    DocumentationLoader,
    APIDocFormatter
)
from backend.infrastructure.pfc.shared.query import APISearch
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from .utils import SearchQuery, SearchLimit


def register_pfc_query_python_api_tool(mcp: FastMCP):
    """Register PFC Python API query tool with the MCP server."""

    @mcp.tool(
        tags={"pfc", "python", "api", "documentation", "search"},
        annotations={"category": "pfc", "tags": ["pfc", "python", "search"]}
    )
    async def pfc_query_python_api(
        context: Context,
        query: SearchQuery,
        limit: SearchLimit = 10,
    ) -> Dict[str, Any]:
        """Search PFC Python SDK documentation by keywords (like grep).

        Returns matching API paths with signatures. Use pfc_browse_python_api for full documentation.

        When to use:
        - You have keywords but don't know exact API path
        - Example: "ball velocity", "create", "contact force"

        Related tools:
        - pfc_browse_python_api: Get full documentation for a known API path
        - pfc_query_command: Search PFC commands by keywords
        """
        try:
            # Search for matching APIs
            matches = APISearch.search(query, top_k=limit)

            # No results found
            if not matches:
                # Check fallback hints
                index = DocumentationLoader.load_index()
                hints = []
                for hint_key, hint_msg in index.get("fallback_hints", {}).items():
                    if hint_key in query.lower():
                        hints.append(hint_msg)

                llm_text = APIDocFormatter.format_no_results_response(query, hints)

                return success_response(
                    message=f"No Python SDK API found for '{query}'",
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": llm_text
                        }]
                    },
                    data={
                        "query": query,
                        "matches_found": 0,
                        "suggestion": "Try pfc_query_command or different keywords"
                    }
                )

            # Format results as list of signatures
            result_lines = [f"Found {len(matches)} API(s) for '{query}':", ""]

            for result in matches:
                api_path = result.document.name
                sig = APIDocFormatter.format_signature(api_path, result.document.metadata)
                if sig:
                    result_lines.append(f"- {api_path}: {sig}")
                else:
                    result_lines.append(f"- {api_path}")

            result_lines.append("")
            result_lines.append("Use pfc_browse_python_api(api=\"<path>\") for full documentation")

            return success_response(
                message=f"Found {len(matches)} Python SDK API(s) for '{query}'",
                llm_content={
                    "parts": [{
                        "type": "text",
                        "text": "\n".join(result_lines)
                    }]
                },
                data={
                    "query": query,
                    "matches_found": len(matches),
                    "api_paths": [r.document.name for r in matches]
                }
            )

        except FileNotFoundError as e:
            return error_response(f"Documentation files not found: {str(e)}")
        except Exception as e:
            return error_response(f"Error querying Python API: {str(e)}")

