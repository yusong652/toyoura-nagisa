from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

router = APIRouter()

# 获取后端 chat/data 的绝对路径
BASE_DIR = Path(__file__).parent.parent / "chat" / "data"

@router.get("/api/images/{image_path:path}")
async def get_image(image_path: str):
    """
    提供图片访问的API路由
    Args:
        image_path: 图片的相对路径，格式为 session_id/filename
    Returns:
        FileResponse: 图片文件
    """
    try:
        # 用绝对路径拼接
        full_path = BASE_DIR / image_path
        # 安全检查：确保路径在允许的目录内
        if not str(full_path.resolve()).startswith(str(BASE_DIR.resolve())):
            raise HTTPException(status_code=403, detail="Access denied")
        # 检查文件是否存在
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Image not found")
        # 返回图片文件
        return FileResponse(
            full_path,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=31536000"}  # 缓存一年
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 