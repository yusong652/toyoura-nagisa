"""
File search API for @ mention functionality.

Provides file path search and suggestion for frontend file mention feature.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Query, HTTPException

from backend.shared.utils.workspace import get_workspace_for_profile
from backend.infrastructure.mcp.utils.path_normalization import path_to_llm_format

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["files"])


def _fuzzy_match_score(query: str, filename: str) -> float:
    """
    Calculate fuzzy match score for filename.

    Scoring algorithm:
    - Exact match: 100
    - Starts with query: 80-90
    - Contains query: 60-70
    - Character sequence match: 40-50
    - No match: 0

    Args:
        query: Search query string
        filename: Filename to match against

    Returns:
        Match score (0-100)
    """
    query_lower = query.lower()
    filename_lower = filename.lower()

    # Exact match
    if filename_lower == query_lower:
        return 100.0

    # Starts with query
    if filename_lower.startswith(query_lower):
        # Longer match is better
        return 80.0 + (len(query) / len(filename)) * 10

    # Contains query as substring
    if query_lower in filename_lower:
        # Position affects score
        index = filename_lower.index(query_lower)
        position_score = (1 - (index / len(filename))) * 10
        return 60.0 + position_score

    # Character sequence match (every character of query appears in order)
    query_idx = 0
    for char in filename_lower:
        if query_idx < len(query_lower) and char == query_lower[query_idx]:
            query_idx += 1

    if query_idx == len(query_lower):
        # All query characters found in order
        return 40.0 + (len(query) / len(filename)) * 10

    return 0.0


async def _search_files_in_workspace(
    workspace_root: Path,
    query: str,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Search files in workspace with fuzzy matching.

    Args:
        workspace_root: Workspace root directory
        query: Search query string
        limit: Maximum number of results

    Returns:
        List of file info dictionaries with path and score
    """
    results = []

    try:
        # Walk through workspace directory
        for file_path in workspace_root.rglob('*'):
            # Skip directories
            if not file_path.is_file():
                continue

            # Skip hidden files and directories
            if any(part.startswith('.') for part in file_path.parts):
                continue

            # Get relative path from workspace
            try:
                relative_path = file_path.relative_to(workspace_root)
            except ValueError:
                continue  # Skip if path is not relative to workspace

            # Calculate match score for both filename and full path
            filename = file_path.name
            path_str = str(relative_path).replace('\\', '/')

            filename_score = _fuzzy_match_score(query, filename)
            path_score = _fuzzy_match_score(query, path_str)

            # Use higher score
            score = max(filename_score, path_score)

            if score > 0:
                results.append({
                    'path': path_str,
                    'filename': filename,
                    'score': score
                })

        # Sort by score (highest first)
        results.sort(key=lambda x: x['score'], reverse=True)

        # Limit results
        return results[:limit]

    except Exception as e:
        logger.error(f"Error searching files in workspace: {e}")
        return []


@router.get("/search")
async def search_files(
    query: str = Query(..., description="Search query for file names/paths"),
    session_id: Optional[str] = Query(None, description="Session ID for workspace resolution"),
    agent_profile: str = Query("general", description="Agent profile (general, pfc, coding, etc.)"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of results")
) -> Dict[str, Any]:
    """
    Search files in workspace with fuzzy matching.

    This endpoint supports @ mention functionality by providing file path
    suggestions based on partial input.

    Query Parameters:
        - query: Search query string (required)
        - session_id: Session ID for workspace resolution (optional)
        - agent_profile: Agent profile to determine workspace (default: general)
        - limit: Maximum results to return (default: 50, max: 200)

    Returns:
        {
            "status": "success",
            "query": "search query",
            "workspace": "workspace path",
            "results": [
                {
                    "path": "relative/path/to/file.py",
                    "filename": "file.py",
                    "score": 85.5
                },
                ...
            ],
            "total": 10
        }

    Example:
        GET /api/files/search?query=sample&agent_profile=general
        → Returns files matching "sample" in general workspace
    """
    try:
        # Get workspace root based on agent profile
        workspace_root = await get_workspace_for_profile(agent_profile, session_id)

        # Search files
        results = await _search_files_in_workspace(workspace_root, query, limit)

        # Format workspace path for response
        workspace_display = path_to_llm_format(workspace_root)

        return {
            "status": "success",
            "query": query,
            "workspace": workspace_display,
            "results": results,
            "total": len(results)
        }

    except Exception as e:
        logger.error(f"File search failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"File search failed: {str(e)}"
        )
