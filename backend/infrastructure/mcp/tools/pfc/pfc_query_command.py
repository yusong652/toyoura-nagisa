"""PFC Command Query Tool - MCP wrapper for command documentation queries.

This MCP tool enables LLM to query PFC command documentation including
integrated contact model properties support.

This tool complements pfc_query_python_api by providing access to command-level
documentation when Python SDK doesn't support an operation.
"""

from typing import Dict, Any
from fastmcp import FastMCP
from fastmcp.server.context import Context
from pydantic import Field

from backend.infrastructure.pfc.commands import (
    CommandSearcher,
    CommandLoader,
    CommandFormatter,
    DocumentType
)
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response

# Default and maximum limits for search results
DEFAULT_SEARCH_LIMIT = 10
MAX_SEARCH_LIMIT = 20


def register_pfc_query_command_tool(mcp: FastMCP):
    """Register PFC command query tool with the MCP server."""

    # Create searcher instance once
    searcher = CommandSearcher()

    @mcp.tool(
        tags={"pfc", "command", "documentation"},
        annotations={"category": "pfc", "tags": ["pfc", "command", "documentation"]}
    )
    async def pfc_query_command(
        context: Context,
        query: str = Field(
            ...,
            description=(
                "Search for PFC commands or contact model properties. Examples: "
                "'ball create', 'contact property', 'kn stiffness', 'model solve'. "
                "Case-insensitive, supports partial matching."
            )
        ),
        limit: int = Field(
            DEFAULT_SEARCH_LIMIT,
            description=(
                "Number of results to return (1-20). Use higher values for "
                "exploring related commands."
            ),
            ge=1,
            le=MAX_SEARCH_LIMIT
        ),
        include_model_properties: bool = Field(
            True,
            description=(
                "Include contact model properties in search (default: True). "
                "Set to False to search only commands."
            )
        )
    ) -> Dict[str, Any]:
        """Query PFC command documentation with optional model properties.

        Searches the complete PFC command catalog (115 commands across 7 categories)
        and optionally includes contact model properties (5 models with detailed
        property documentation).

        Use this tool when:
        - Python SDK doesn't support an operation (check pfc_query_python_api first)
        - Need command syntax and parameters
        - Looking for contact model properties (kn, ks, fric, etc.)
        - Exploring available commands in a category

        Returns command documentation with syntax, examples, and Python SDK alternatives.
        """
        try:
            # Validate limit is within bounds
            if limit < 1 or limit > MAX_SEARCH_LIMIT:
                return error_response(
                    f"Limit must be between 1 and {MAX_SEARCH_LIMIT}, got {limit}"
                )

            # Search for matching commands/properties
            results = searcher.search(
                query,
                top_n=limit,
                include_model_properties=include_model_properties
            )

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
                        "include_model_properties": include_model_properties,
                        "suggestion": "Try pfc_query_python_api for Python SDK alternatives"
                    }
                )

            # Format best result (full documentation)
            best_result = results[0]
            formatted_doc = ""

            if best_result.doc_type == DocumentType.COMMAND:
                # Load full command documentation
                category = best_result.category
                command_name = best_result.name.split(maxsplit=1)[1]  # Remove category prefix
                cmd_doc = CommandLoader.load_command_doc(category, command_name)

                if cmd_doc:
                    formatted_doc = CommandFormatter.format_command(cmd_doc, category)
                else:
                    formatted_doc = f"# {best_result.name}\n\n*Documentation not available*"

            elif best_result.doc_type == DocumentType.MODEL_PROPERTY:
                # Load full model documentation (model-level, not individual property)
                model_name = best_result.category
                model_doc = CommandLoader.load_model_property_doc(model_name)

                if model_doc:
                    formatted_doc = CommandFormatter.format_full_model(model_doc)
                else:
                    formatted_doc = f"# {best_result.name}\n\n*Documentation not available*"

            # Format related results (if multiple matches)
            related_section = ""
            if len(results) > 1:
                related_section = "\n\n---\n\n## Related Results\n\n"
                related_section += CommandFormatter.format_search_results(results[1:])

            full_response = formatted_doc + related_section

            return success_response(
                message=f"Found {len(results)} command(s): {best_result.name}" +
                        (f" + {len(results)-1} more" if len(results) > 1 else ""),
                llm_content={
                    "parts": [{
                        "type": "text",
                        "text": full_response
                    }]
                },
                data={
                    "query": query,
                    "best_match": best_result.name,
                    "match_type": best_result.doc_type.value,
                    "category": best_result.category,
                    "score": best_result.score,
                    "total_results": len(results),
                    "include_model_properties": include_model_properties,
                    "python_alternative": best_result.metadata.get("python_available") if best_result.metadata and best_result.doc_type == DocumentType.COMMAND else None,
                    "related_results": [
                        {
                            "name": r.name,
                            "type": r.doc_type.value,
                            "score": r.score
                        }
                        for r in results[1:]
                    ] if len(results) > 1 else []
                }
            )

        except FileNotFoundError as e:
            return error_response(f"Documentation files not found: {str(e)}")
        except Exception as e:
            return error_response(f"Error querying command documentation: {str(e)}")

    print("[DEBUG] Registered PFC command query tool: pfc_query_command")
