"""PFC Python API Query Tool - MCP wrapper for SDK documentation queries.

This MCP tool enables LLM to query PFC Python API documentation and should
be used FIRST before falling back to itasca.command() strings.

This is a thin wrapper around the core SDK documentation utilities in
backend.infrastructure.pfc.python_api, handling only MCP protocol integration
and error response formatting.
"""

from typing import Dict, Any
from fastmcp import FastMCP
from fastmcp.server.context import Context
from pydantic import Field

from backend.infrastructure.pfc.python_api import (
    DocumentationLoader,
    APIDocFormatter
)
from backend.infrastructure.pfc.shared.query import APISearch
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response

# Default and maximum limits for search results
DEFAULT_SEARCH_LIMIT = 10
MAX_SEARCH_LIMIT = 20

# Confidence threshold for query results
# Score ranges (designed for future semantic search integration):
#   950-999: Exact path match (PathSearchStrategy)
#   800-949: High-quality semantic match (SemanticSearchStrategy - future)
#   700-799: Good keyword match (KeywordSearchStrategy)
#   400-699: Low-quality partial match (triggers fallback suggestion)
#   0-399:   Noise-level match (treated as no results)
HIGH_CONFIDENCE_THRESHOLD = 700  # Filters out low-quality matches
MAX_LOW_CONFIDENCE_DISPLAY = 2   # Show only top 2 results for low confidence


def register_pfc_query_python_api_tool(mcp: FastMCP):
    """Register PFC Python API query tool with the MCP server."""

    @mcp.tool(
        tags={"pfc", "python", "api", "documentation"},
        annotations={"category": "pfc", "tags": ["pfc", "python", "documentation"]}
    )
    async def pfc_query_python_api(
        context: Context,
        query: str = Field(
            ...,
            description=(
                "Search for PFC Python API. Examples: 'Ball.pos', 'ball velocity', "
                "'create a ball', 'pos'. Case-insensitive, supports partial matching."
            )
        ),
        limit: int = Field(
            DEFAULT_SEARCH_LIMIT,
            description=(
                "Number of results to return. Use higher values for exploring "
                "related APIs, lower values for focused searches."
            ),
            ge=1,
            le=MAX_SEARCH_LIMIT
        )
    ) -> Dict[str, Any]:
        """Query PFC Python API documentation - preferred for PFC operations.

        Searches complete API catalog using exact paths, keywords, or natural language.
        Returns best matches with full documentation and related alternatives.

        The limit parameter controls how many results to return. Use higher values
        when exploring related APIs, lower values when you know what you're looking for.
        """
        try:
            # Search for matching APIs with user-specified limit using new search system
            matches = APISearch.search(query, top_k=limit)

            # ===== Condition 1: No results found =====
            if not matches:
                # Check fallback hints
                index = DocumentationLoader.load_index()
                hints = []
                for hint_key, hint_msg in index.get("fallback_hints", {}).items():
                    if hint_key in query.lower():
                        hints.append(hint_msg)

                # No match is not an error - it's a normal query result
                # Return success to guide LLM to the next step (query commands)
                message = f"No Python SDK API found for '{query}'"
                llm_text = APIDocFormatter.format_no_results_response(query, hints)

                return success_response(
                    message=message,
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": llm_text
                        }]
                    },
                    data={
                        "query": query,
                        "matches_found": 0,
                        "reason": "no_results",
                        "suggestion": "Use pfc_query_command tool"
                    }
                )

            # ===== Condition 2: Low confidence results =====
            best_score = matches[0].score

            if best_score < HIGH_CONFIDENCE_THRESHOLD:
                # Low-quality match - show simplified results and recommend fallback
                low_conf_matches = matches[:MAX_LOW_CONFIDENCE_DISPLAY]

                message = f"Found {len(low_conf_matches)} low-confidence matches (best score: {best_score}/{HIGH_CONFIDENCE_THRESHOLD})"
                llm_text = APIDocFormatter.format_low_confidence_response(
                    query,
                    low_conf_matches,
                    best_score,
                    HIGH_CONFIDENCE_THRESHOLD
                )

                return success_response(
                    message=message,
                    llm_content={
                        "parts": [{
                            "type": "text",
                            "text": llm_text
                        }]
                    },
                    data={
                        "query": query,
                        "matches_found": len(matches),
                        "displayed_count": len(low_conf_matches),
                        "best_score": best_score,
                        "confidence": "low",
                        "reason": "low_confidence",
                        "suggestion": "Strongly recommended to use pfc_query_command",
                        "partial_results": [
                            {"name": result.document.id, "score": result.score}
                            for result in low_conf_matches
                        ]
                    }
                )

            # ===== Condition 3: High confidence results (score >= 700) =====
            best_result = matches[0]
            api_path = best_result.document.id

            # Load full documentation for best match
            api_doc = DocumentationLoader.load_api_doc(api_path)

            if not api_doc:
                return error_response(f"API documentation not found for {api_path}")

            # Format full documentation for best match (pass metadata for Contact types)
            # Note: APIDocFormatter expects old SearchResult format, so we pass document.metadata
            formatted_doc = APIDocFormatter.format_full_doc(api_doc, best_result)

            # Format related APIs (if multiple matches)
            related_section = ""
            if len(matches) > 1:
                related_apis = []
                for result in matches[1:]:
                    # Pass metadata to formatter for Contact type handling
                    sig = APIDocFormatter.format_signature(result.document.id, result.document.metadata)
                    if sig:
                        related_apis.append(f"- {sig}")

                if related_apis:
                    related_section = (
                        f"\n\n---\n\n"
                        f"## Related APIs\n\n"
                        f"Query again with exact name if needed:\n\n"
                        + "\n".join(related_apis)
                    )

            # Optional gentle hint for medium-confidence results with few matches
            # (score 700-899, less than 3 results)
            optional_hint = ""
            if best_score < 900 and len(matches) < 3:
                optional_hint = (
                    f"\n\n---\n\n"
                    f"**Note**: If these don't match your needs, you may also try pfc_query_command."
                )

            return success_response(
                message=f"Found {len(matches)} Python SDK API(s): {api_path}" + (f" + {len(matches)-1} more" if len(matches) > 1 else ""),
                llm_content={
                    "parts": [{
                        "type": "text",
                        "text": f"**STATUS**: Python SDK Available (preferred approach)\n\n{formatted_doc}{related_section}{optional_hint}"
                    }]
                },
                data={
                    "api_name": api_path,
                    "signature": api_doc['signature'],
                    "has_limitations": bool(api_doc.get('limitations')),
                    "fallback_commands": api_doc.get('fallback_commands', []),
                    "match_count": len(matches),
                    "is_contact_type": bool(best_result.document.metadata and 'contact_type' in best_result.document.metadata),
                    "contact_type": best_result.document.metadata.get('contact_type') if best_result.document.metadata else None,
                    "related_apis": [
                        {"name": result.document.id, "score": result.score}
                        for result in matches[1:]
                    ] if len(matches) > 1 else []
                }
            )

        except FileNotFoundError as e:
            return error_response(f"Documentation files not found: {str(e)}")
        except Exception as e:
            return error_response(f"Error querying Python API: {str(e)}")

    print("[DEBUG] Registered PFC Python API query tool: pfc_query_python_api")
