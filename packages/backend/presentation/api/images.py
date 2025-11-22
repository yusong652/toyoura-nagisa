from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

router = APIRouter()

# Get absolute path to project root chat/data directory
# Navigate from backend/presentation/api/ to project root
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "chat" / "data"

@router.get("/images/{image_path:path}")
async def get_image(image_path: str):
    """
    API route for image file access.
    Args:
        image_path: Relative image path in format session_id/filename
    Returns:
        FileResponse: Image file response
    """
    try:
        # Construct full path using absolute path
        full_path = BASE_DIR / image_path
        # Security check: ensure path is within allowed directory
        if not str(full_path.resolve()).startswith(str(BASE_DIR.resolve())):
            raise HTTPException(status_code=403, detail="Access denied")
        # Check if file exists
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Image not found")
        # Return image file
        return FileResponse(
            full_path,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=31536000"}  # Cache for one year
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 