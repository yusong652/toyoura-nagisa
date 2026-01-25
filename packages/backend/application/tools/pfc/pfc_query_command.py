"""PFC Command Query Tool - Keyword search for command documentation.

This tool searches PFC command documentation by keywords (like grep).
Returns matching command paths with brief descriptions for LLM to identify relevant commands.

For full documentation, use pfc_browse_commands with the returned command path.

Workflow:
1. pfc_query_command(query="ball create") → Returns matching command paths
2. pfc_browse_commands(command="ball create") → Get full documentation
"""

from typing import Dict, Any

from backend.application.tools.registrar import ToolRegistrar
from fastmcp.server.context import Context

from backend.infrastructure.pfc.commands import CommandFormatter
from backend.infrastructure.pfc.shared.query import CommandSearch
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from .utils import SearchQuery, SearchLimit


def register_pfc_query_command_tool(registrar: ToolRegistrar):
    """Register PFC command query tool with the registrar."""

    @registrar.tool(
        tags={"pfc", "command", "documentation", "search"},
        annotations={"category": "pfc", "tags": ["pfc", "command", "search"]}
    )
    async def pfc_query_command(
        context: Context,
        query: SearchQuery,
        limit: SearchLimit = 10,
    ) -> Dict[str, Any]:
        """Search PFC command documentation by keywords (like grep).

        Returns matching command paths. Use pfc_browse_commands for full documentation.

        When to use:
        - You have keywords but don't know exact command path
        - Example: "ball create", "contact property", "model solve"

        Related tools:
        - pfc_browse_commands: Get full documentation for a known command path
        - pfc_browse_reference: Browse reference docs (e.g., "contact-models linear")
        - pfc_query_python_api: Search Python SDK by keywords
        """
        try:
            # Parameters are pre-validated by Pydantic Annotated types
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
