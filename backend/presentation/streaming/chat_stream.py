"""
Chat stream orchestrator for the presentation layer.

This module provides the high-level chat streaming functionality,
orchestrating memory injection, LLM response handling, and conversation persistence.
"""

import json
import uuid
from typing import List, AsyncGenerator
from backend.infrastructure.llm import LLMClientBase
from backend.domain.models.messages import BaseMessage
from backend.domain.models.message_factory import message_factory_no_thinking
from backend.infrastructure.storage.session_manager import load_history
from backend.infrastructure.tts.base import BaseTTS
from backend.config import get_llm_settings
from backend.presentation.streaming.llm_response_handler import handle_llm_response
from backend.presentation.streaming.memory_injection_handler import (
    get_system_prompt_with_memory_context,
    save_conversation_memory
)


async def generate_chat_stream(
    session_id: str, 
    recent_msgs: List[BaseMessage], 
    llm_client: LLMClientBase, 
    tts_engine: BaseTTS,
    user_id: str = "default",
    enable_memory: bool = True
) -> AsyncGenerator[str, None]:
    """
    Enhanced chat stream generator with memory injection.
    
    This function integrates the complete streaming pipeline with memory context:
    1. Load conversation history
    2. Inject relevant memory context
    3. Generate LLM response with streaming
    4. Save conversation to memory for future retrieval
    
    Args:
        session_id: Current session ID
        recent_msgs: Recent conversation messages (unused, loaded from history)
        llm_client: LLM client instance
        tts_engine: TTS engine instance
        user_id: User identifier for memory operations
        enable_memory: Flag to enable/disable memory injection
    
    Yields:
        SSE formatted response chunks
    """
    # Generate unique request ID for debugging
    request_id = str(uuid.uuid4())[:8]
    
    yield f"data: {json.dumps({'status': 'sent'})}\n\n"
    
    try:
        yield f"data: {json.dumps({'status': 'read'})}\n\n"
        
        # Load conversation history without images
        recent_history = load_history(session_id)
        # Create messages without thinking blocks
        recent_msgs = [message_factory_no_thinking(msg) if isinstance(msg, dict) else msg for msg in recent_history]
        recent_messages_length = get_llm_settings().recent_messages_length
        recent_msgs = recent_msgs[-recent_messages_length:]
        
        # Get enhanced system prompt with memory context if enabled
        enhanced_system_prompt = None
        memory_status_updates = []
        
        # Memory injection processing
        
        if enable_memory:
            # Extract latest user message for memory query
            user_query = None
            for msg in reversed(recent_msgs):
                if getattr(msg, "role", None) == "user":
                    content = getattr(msg, "content", "")
                    # Extract user query for memory enhancement
                    
                    # Handle multimodal content (list format) or simple string content
                    if isinstance(content, list):
                        # Extract text from list of content items
                        text_parts = []
                        for item in content:
                            if isinstance(item, dict):
                                if "text" in item:
                                    text_parts.append(item["text"])
                                elif item.get("type") == "text":
                                    text_parts.append(item.get("text", ""))
                        user_query = " ".join(text_parts)
                    else:
                        # Simple string content
                        user_query = str(content)
                    
                    # Use extracted query for memory retrieval
                    break
            
            if user_query:
                from backend.config import get_system_prompt
                # Use the LLM client's actual tools_enabled setting
                tools_enabled = llm_client.tool_manager.tools_enabled if hasattr(llm_client, 'tool_manager') else True
                base_system_prompt = get_system_prompt(tools_enabled=tools_enabled)
                # Get enhanced system prompt with memory context
                enhanced_system_prompt, memory_status_updates = await get_system_prompt_with_memory_context(
                    session_id=session_id,
                    user_query=user_query,
                    base_system_prompt=base_system_prompt,
                    user_id=user_id,
                    enable_memory=enable_memory
                )
                # Memory context processing complete
                
                # Send memory status updates
                for status_update in memory_status_updates:
                    yield f"data: {json.dumps(status_update)}\n\n"
            else:
                # No user query available for memory enhancement
                pass
        
        # Process LLM response with messages and enhanced system prompt
        assistant_response = None
        async for chunk in handle_llm_response(
            recent_msgs, 
            session_id, 
            llm_client, 
            tts_engine, 
            enhanced_system_prompt=enhanced_system_prompt
        ):
            # Capture assistant response for memory saving
            if isinstance(chunk, str) and 'data:' in chunk:
                try:
                    # Parse the chunk to extract content
                    json_str = chunk.replace('data: ', '').strip()
                    if json_str:
                        data = json.loads(json_str)
                        if 'text' in data and data['text']:
                            if assistant_response is None:
                                assistant_response = ""
                            assistant_response += data['text']
                except:
                    pass
            
            yield chunk
        
        # Save conversation to memory after successful response
        if enable_memory and assistant_response:
            await save_conversation_memory(
                recent_msgs=recent_msgs,
                assistant_response=assistant_response,
                session_id=session_id,
                user_id=user_id
            )
            
    except Exception as e:
        print(f"[ERROR] API Request {request_id} - Exception in generate(): {e}")
        yield f"data: {json.dumps({'type': 'NAGISA_TOOL_USE_CONCLUDED'})}\n\n"
        error_data = {
            'type': 'error',
            'error': str(e)
        }
        yield f"data: {json.dumps(error_data)}\n\n"
        raise e