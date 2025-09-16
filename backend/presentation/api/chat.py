"""
Chat API Routes.

This module handles chat streaming endpoints following Clean Architecture principles.
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from backend.domain.services.chat_service import ChatService, get_chat_service
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.shared.utils.app_context import get_llm_client_dependency

router = APIRouter(tags=["chat"])


@router.post("/chat/stream")
async def chat_endpoint(
    request: Request,
    service: ChatService = Depends(get_chat_service),
    llm_client: LLMClientBase = Depends(get_llm_client_dependency)
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
        # Parse and validate request data
        data = await request.json()
        parsed_data, session_id, agent_profile = service.parse_request_data(data)
        
        if not parsed_data:
            raise HTTPException(
                status_code=400,
                detail="Invalid message data format"
            )
        
        # Extract enable_memory flag from request (default to True)
        enable_memory = data.get("enable_memory", True)
        
        # Extract user message ID for status tracking
        user_message_id = parsed_data.get("id") if parsed_data else None

        # Load conversation history
        history_msgs = service.load_and_prepare_history(session_id)
        
        # Process user message
        service.process_user_message_for_session(
            parsed_data, session_id, history_msgs
        )
        
        # Generate streaming response with message ID for status updates
        return await service.create_streaming_response(
            session_id=session_id,
            llm_client=llm_client,
            agent_profile=agent_profile,
            enable_memory=enable_memory,
            user_message_id=user_message_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Chat streaming failed: {str(e)}"
        )