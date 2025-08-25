"""
Video generation API endpoints
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import BaseModel
from backend.domain.services.content_service import ContentService
from backend.infrastructure.llm.base.client import LLMClientBase

router = APIRouter()

# 获取后端 chat/data 的绝对路径
BASE_DIR = Path(__file__).parent.parent.parent / "chat" / "data"

class VideoGenerationRequest(BaseModel):
    session_id: str
    motion_type: str = "cinematic"

def get_content_service() -> ContentService:
    """
    Get Content service instance.
    
    Returns:
        ContentService: Service instance for content operations
    """
    return ContentService()

def get_llm_client(request: Request) -> LLMClientBase:
    """
    Get LLM client from app state.
    
    Args:
        request: FastAPI request instance containing app state
        
    Returns:
        LLMClientBase: LLM client instance
    """
    return request.app.state.llm_client

@router.get("/api/videos/{video_path:path}")
async def get_video(video_path: str):
    """
    提供视频文件访问的API路由
    
    Args:
        video_path: 视频的相对路径，格式为 session_id/filename
        
    Returns:
        FileResponse: 视频文件
    """
    try:
        # 用绝对路径拼接
        full_path = BASE_DIR / video_path
        # 安全检查：确保路径在允许的目录内
        if not str(full_path.resolve()).startswith(str(BASE_DIR.resolve())):
            raise HTTPException(status_code=403, detail="Access denied")
        # 检查文件是否存在
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Video not found")
        
        # 根据文件扩展名确定媒体类型
        suffix = full_path.suffix.lower()
        if suffix == '.mp4':
            media_type = "video/mp4"
        elif suffix == '.gif':
            media_type = "image/gif"
        elif suffix == '.webm':
            media_type = "video/webm"
        else:
            media_type = "application/octet-stream"
        
        # 返回视频文件
        return FileResponse(
            full_path,
            media_type=media_type,
            headers={"Cache-Control": "public, max-age=31536000"}  # 缓存一年
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/generate-video")
async def generate_video(
    request: VideoGenerationRequest,
    service: ContentService = Depends(get_content_service),
    llm_client: LLMClientBase = Depends(get_llm_client)
):
    """
    Generate video from the most recent image in conversation context.
    
    Args:
        request: Video generation request with session_id and motion_type
        
    Returns:
        dict: Generation result with success status and video data
    """
    try:
        result = await service.generate_video_for_session(
            session_id=request.session_id,
            motion_type=request.motion_type,
            llm_client=llm_client
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))