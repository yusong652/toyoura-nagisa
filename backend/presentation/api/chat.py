"""
Chat API Routes.

This module handles chat streaming endpoints following Clean Architecture principles.
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from backend.domain.services.chat_service import ChatService, get_chat_service

router = APIRouter(tags=["chat"])


@router.post("/chat/stream")
async def chat_endpoint(
    request: Request,
    service: ChatService = Depends(get_chat_service)
) -> StreamingResponse:
    """
    Stream chat responses with real-time LLM generation and optional TTS.
    
    This endpoint:
    1. Parses and validates incoming message data
    2. Loads conversation history for context
    3. Processes user message and stores it
    4. Generates streaming LLM response with tool calling support
    5. Optionally synthesizes TTS audio for responses
    
    Args:
        request: FastAPI request containing message data in JSON body:
            - message content and metadata
            - session_id for conversation context
            - agent_profile for tool selection ("general", "coding", "lifestyle", etc.)
            - enable_memory (optional): Whether to enable memory injection (default: True)
            - optional configuration flags
        
    Returns:
        StreamingResponse: Server-Sent Events stream with:
            - media_type: "text/event-stream"
            - Real-time LLM response chunks
            - Tool execution results
            - Optional TTS audio data
    
    Raises:
        HTTPException: 
            - 400 if message data is invalid or malformed
            - 500 if streaming generation fails
    
    Example:
        POST /api/chat/stream
        Content-Type: application/json
        
        {
            "message": "Hello, how can you help me?",
            "session_id": "550e8400-e29b-41d4-a716-446655440000",
            "agent_profile": "general",
            "type": "text"
        }
    """
    try:
        # Parse request and extract configuration
        result, enable_memory = await service.parse_request(request)

        # Save user message to session
        service.save_user_message_to_session(result)

        # Generate streaming response
        return await service.create_streaming_response(result, enable_memory)
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Chat streaming failed: {str(e)}"
        )