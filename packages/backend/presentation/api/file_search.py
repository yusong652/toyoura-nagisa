"""
File Search API (2025 Standard).

Provides file path search and suggestion for frontend file mention feature.

Routes:
    GET /api/files/search - Search files with fuzzy matching
"""
import logging
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from backend.presentation.models.api_models import ApiResponse
from backend.presentation.exceptions import InternalServerError
from backend.shared.utils.workspace import resolve_workspace_root
from backend.shared.utils.path_normalization import path_to_llm_format
from backend.domain.models.agent_types import AgentProfileLiteral, DEFAULT_AGENT_PROFILE

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["files"])


# =====================
# Response Data Models
# =====================
class FileMatch(BaseModel):
    """File search result item."""
    path: str = Field(..., description="Relative path from workspace")
    filename: str = Field(..., description="File name")
    score: float = Field(..., description="Match score (0-100)")


class FileSearchData(BaseModel):
    """Response data for file search."""
    query: str = Field(..., description="Search query")
    workspace: str = Field(..., description="Workspace path")
    results: List[FileMatch] = Field(..., description="Matching files")
    total: int = Field(..., description="Total matches found")


# =====================
# Helper Functions
# =====================
def _fuzzy_match_score(query: str, filename: str) -> float:
    """Calculate fuzzy match score for filename.

    Scoring algorithm:
    - Exact match: 100
    - Starts with query: 80-90
    - Contains query: 60-70
    - Character sequence match: 40-50
    - No match: 0
    """
    query_lower = query.lower()
    filename_lower = filename.lower()

    # Exact match
    if filename_lower == query_lower:
        return 100.0

    # Starts with query
    if filename_lower.startswith(query_lower):
        return 80.0 + (len(query) / len(filename)) * 10

    # Contains query as substring
    if query_lower in filename_lower:
        index = filename_lower.index(query_lower)
        position_score = (1 - (index / len(filename))) * 10
        return 60.0 + position_score

    # Character sequence match
    query_idx = 0
    for char in filename_lower:
        if query_idx < len(query_lower) and char == query_lower[query_idx]:
            query_idx += 1

    if query_idx == len(query_lower):
        return 40.0 + (len(query) / len(filename)) * 10

    return 0.0


async def _search_files_in_workspace(
    workspace_root: Path,
    query: str,
    limit: int = 50
) -> List[FileMatch]:
    """Search files in workspace with fuzzy matching."""
    results = []

    try:
        for file_path in workspace_root.rglob('*'):
            if not file_path.is_file():
                continue

            # Skip hidden files and directories
            if any(part.startswith('.') for part in file_path.parts):
                continue

            try:
                relative_path = file_path.relative_to(workspace_root)
            except ValueError:
                continue

            filename = file_path.name
            path_str = str(relative_path).replace('\\', '/')

            filename_score = _fuzzy_match_score(query, filename)
            path_score = _fuzzy_match_score(query, path_str)
            score = max(filename_score, path_score)

            if score > 0:
                results.append(FileMatch(
                    path=path_str,
                    filename=filename,
                    score=score
                ))

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]

    except Exception as e:
        logger.error(f"Error searching files in workspace: {e}")
        return []


# =====================
# API Endpoints
# =====================
@router.get("/search", response_model=ApiResponse[FileSearchData])
async def search_files(
    query: str = Query(..., description="Search query for file names/paths"),
    session_id: Optional[str] = Query(default=None, description="Session ID"),
    agent_profile: AgentProfileLiteral = Query(default=DEFAULT_AGENT_PROFILE, description="Agent profile"),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum results"),
) -> ApiResponse[FileSearchData]:
    """Search files in workspace with fuzzy matching.

    Supports @ mention functionality by providing file path suggestions
    based on partial input.
    """
    try:
        workspace_root = await resolve_workspace_root(session_id)
        results = await _search_files_in_workspace(workspace_root, query, limit)
        workspace_display = path_to_llm_format(workspace_root)

        return ApiResponse(
            success=True,
            message=f"Found {len(results)} matches",
            data=FileSearchData(
                query=query,
                workspace=workspace_display,
                results=results,
                total=len(results)
            )
        )
    except Exception as e:
        logger.error(f"File search failed: {e}")
        raise InternalServerError(
            message=f"File search failed: {str(e)}"
        )
