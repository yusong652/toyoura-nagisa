"""PFC Command Query Tool - Keyword search for command documentation.

This tool searches PFC command documentation by keywords (like grep).
Returns matching command paths with brief descriptions for LLM to identify relevant commands.

For full documentation, use pfc_browse_commands with the returned command path.

Workflow:
1. pfc_query_command(query="ball create") → Returns matching command paths
2. pfc_browse_commands(command="ball create") → Get full documentation
"""

from typing import Dict, Any
from fastmcp import FastMCP
from fastmcp.server.context import Context
from pydantic import Field

from backend.infrastructure.pfc.commands import CommandFormatter
from backend.infrastructure.pfc.shared.query import CommandSearch
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response

# Default and maximum limits for search results
DEFAULT_SEARCH_LIMIT = 10
MAX_SEARCH_LIMIT = 20


def register_pfc_query_command_tool(mcp: FastMCP):
    """Register PFC command query tool with the MCP server."""

    @mcp.tool(
        tags={"pfc", "command", "documentation", "search"},
        annotations={"category": "pfc", "tags": ["pfc", "command", "search"]}
    )
    async def pfc_query_command(
        context: Context,
        query: str = Field(
            ...,
            description=(
                "Search keywords for PFC commands. Examples: 'ball create', "
                "'contact property', 'model solve'. Case-insensitive."
            )
        ),
        limit: int = Field(
            DEFAULT_SEARCH_LIMIT,
            description="Maximum number of results to return (1-20).",
            ge=1,
            le=MAX_SEARCH_LIMIT
        )
    ) -> Dict[str, Any]:
        """Search PFC command documentation by keywords.

        Returns matching command paths with brief descriptions. Use this tool when
        you don't know the exact command but have keywords to search.

        WORKFLOW:
        1. Use this tool to find matching command paths
        2. Use pfc_browse_commands(command="<category> <cmd>") for full documentation

        For contact model properties, use pfc_browse_contact_models directly.
        For direct path navigation when you know the command, use pfc_browse_commands.
        """
        try:
            # Validate limit is within bounds
            if limit < 1 or limit > MAX_SEARCH_LIMIT:
                return error_response(
                    f"Limit must be between 1 and {MAX_SEARCH_LIMIT}, got {limit}"
                )

            # Search for matching commands only (model properties have separate browse tool)
            results = CommandSearch.search_commands_only(query, top_k=limit)

            # No results found
            if not results:
                no_results_text = CommandFormatter.format_no_results_response(query)

                return success_response(
                    message=f"No command documentation found for '{query}'",
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": no_results_text
                        }]
                    },
                    data={
                        "query": query,
                        "matches_found": 0,
                        "suggestion": "Try different keywords or pfc_browse_commands()"
                    }
                )

            # Format results as list
            result_lines = [f"Found {len(results)} command(s) for '{query}':", ""]

            for result in results:
                title = result.document.title
                category = result.document.category

                # Extract command name from title (e.g., "ball create" -> "create")
                cmd_parts = title.split(maxsplit=1)
                cmd_name = cmd_parts[1] if len(cmd_parts) > 1 else title
                browse_path = f"{category} {cmd_name}" if category else title
                result_lines.append(f"- {title}: pfc_browse_commands(command=\"{browse_path}\")")

            result_lines.append("")
            result_lines.append("Use pfc_browse_commands(command=\"...\") for full documentation")

            return success_response(
                message=f"Found {len(results)} command(s) for '{query}'",
                llm_content={
                    "parts": [{
                        "type": "text",
                        "text": "\n".join(result_lines)
                    }]
                },
                data={
                    "query": query,
                    "matches_found": len(results),
                    "results": [
                        {
                            "title": r.document.title,
                            "type": r.document.doc_type.value,
                            "category": r.document.category
                        }
                        for r in results
                    ]
                }
            )

        except FileNotFoundError as e:
            return error_response(f"Documentation files not found: {str(e)}")
        except Exception as e:
            return error_response(f"Error querying command documentation: {str(e)}")

    print("[DEBUG] Registered PFC command query tool: pfc_query_command")
