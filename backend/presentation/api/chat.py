"""
Chat API Routes.

This module handles chat streaming endpoints following Clean Architecture principles.
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from backend.domain.services.chat_service import ChatService
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.infrastructure.tts.base import BaseTTS

router = APIRouter(tags=["chat"])


def get_chat_service() -> ChatService:
    """
    Dependency injection for ChatService.
    
    Returns:
        ChatService: Chat streaming service instance
    """
    return ChatService()


def get_llm_client(request: Request) -> LLMClientBase:
    """
    Get LLM client from app state.
    
    Args:
        request: FastAPI request object
        
    Returns:
        LLMClientBase: LLM client instance
    """
    return request.app.state.llm_client


def get_tts_engine(request: Request) -> BaseTTS:
    """
    Get TTS engine from app state.
    
    Args:
        request: FastAPI request object
        
    Returns:
        BaseTTS: TTS engine instance
    """
    return request.app.state.tts_engine


@router.post("/chat/stream")
async def chat_endpoint(
    request: Request,
    service: ChatService = Depends(get_chat_service),
    llm_client: LLMClientBase = Depends(get_llm_client),
    tts_engine: BaseTTS = Depends(get_tts_engine)
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
        
        # Load conversation history
        history_msgs = service.load_and_prepare_history(session_id)
        
        # Process user message
        service.process_user_message_for_session(
            parsed_data, session_id, history_msgs
        )
        
        # Generate streaming response
        return await service.create_streaming_response(
            session_id=session_id,
            llm_client=llm_client,
            tts_engine=tts_engine,
            agent_profile=agent_profile
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