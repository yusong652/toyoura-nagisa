"""
Image File Serving API (2025 Standard).

Provides static file serving for generated images stored in chat/data.

Routes:
    GET /images/{image_path} - Serve image file

Note: This endpoint returns FileResponse (binary data), not ApiResponse.
"""
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse

from backend.presentation.exceptions import FileNotFoundError, AccessDeniedError

router = APIRouter(tags=["media"])

# Get absolute path to project root chat/data directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "chat" / "data"


@router.get("/images/{image_path:path}")
async def get_image(image_path: str) -> FileResponse:
    """Serve image file from chat/data storage.

    Args:
        image_path: Relative image path in format session_id/filename

    Returns:
        FileResponse with image data
    """
    full_path = BASE_DIR / image_path

    # Security check: ensure path is within allowed directory
    if not str(full_path.resolve()).startswith(str(BASE_DIR.resolve())):
        raise AccessDeniedError(
            resource=f"image:{image_path}",
            reason="Path traversal not allowed"
        )

    # Check if file exists
    if not full_path.exists():
        raise FileNotFoundError(file_path=image_path)

    # Determine media type based on extension
    suffix = full_path.suffix.lower()
    media_type_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    media_type = media_type_map.get(suffix, "application/octet-stream")

    return FileResponse(
        full_path,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=31536000"}
    )
