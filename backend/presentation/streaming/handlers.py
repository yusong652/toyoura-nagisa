import json
import uuid
import asyncio
from typing import Dict, Any, List, AsyncGenerator
from backend.infrastructure.llm import LLMClientBase
from backend.infrastructure.llm.models import BaseMessage, message_factory, message_factory_no_thinking
from backend.infrastructure.llm.utils import load_all_message_history, load_history
from backend.infrastructure.tts.base import BaseTTS
from backend.infrastructure.tts.utils import split_text_by_punctuations, clean_text_for_tts, extract_and_replace_emoticons, restore_emoticons
from backend.shared.utils.helpers import (
    process_ai_text_message,
    process_tts_sentence,
    should_generate_title,
    generate_title_for_session,
)
from backend.infrastructure.llm.utils import update_session_title
from backend.config import get_llm_config


# 全局状态管理
ACTIVE_REQUESTS: Dict[str, str] = {}  # session_id -> request_id
ACTIVE_REQUESTS_LOCK = asyncio.Lock()


async def handle_llm_response(
    recent_msgs: List[BaseMessage],
    session_id: str,
    llm_client: LLMClientBase,
    tts_engine: BaseTTS
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    SOTA Enhanced LLM Response Handler - 实时流式架构
    
    采用现代化实时流式设计，专为即时工具调用通知优化：
    1. 实时工具调用通知 - 工具执行过程中即时推送状态
    2. 流式响应处理 - 保持原有TTS和内容处理逻辑
    3. 状态隔离 - 防重复机制与业务逻辑分离
    4. 错误传播 - 统一错误处理和恢复
    5. 可观测性 - 完整的执行追踪和监控
    """
    # ========== PHASE 1: 请求初始化和防重复 ==========
    request_id = f"REQ_{str(uuid.uuid4())[:8]}"
    
    async with ACTIVE_REQUESTS_LOCK:
        if session_id in ACTIVE_REQUESTS:
            existing_request = ACTIVE_REQUESTS[session_id]
            error_msg = f"Duplicate request detected. Session {session_id} already has active request {existing_request}"
            yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"
            return
        ACTIVE_REQUESTS[session_id] = request_id

    try:
        # ========== PHASE 2: 客户端验证 ==========
        # 支持所有已实现的LLM客户端
        supported_clients = ['GeminiClient', 'LocalLLMClient', 'AnthropicClient', 'GPTClient']
        if type(llm_client).__name__ not in supported_clients:
            error_msg = f"Unsupported LLM client: {type(llm_client).__name__}. Supported clients: {supported_clients}"
            yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"
            return
        
        if not hasattr(llm_client, 'get_response'):
            error_msg = f"{type(llm_client).__name__} missing get_response method"
            yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"
            return

        # ========== PHASE 3: 流式处理 - 实时工具调用通知 ==========
        print(f"[DEBUG] Processing streaming request {request_id} for session {session_id}")
        
        final_message = None
        execution_metadata = None
        
        # 使用新的流式方法 - 实时获取工具调用通知
        async for item in llm_client.get_response(
            recent_msgs, 
            session_id=session_id,
            max_iterations=10
        ):
            if isinstance(item, tuple):
                # 最终结果: (final_message, execution_metadata)
                final_message, execution_metadata = item
                break
            elif isinstance(item, dict):
                # 实时通知: 工具调用状态更新
                yield f"data: {json.dumps(item)}\n\n"
                # 添加小延迟以确保通知按顺序处理
                await asyncio.sleep(0.05)
        
        # ========== PHASE 4: 内容处理流水线 ==========
        if final_message:
            async for chunk in _process_content_pipeline(final_message, session_id, tts_engine, request_id):
                yield chunk
        
        # ========== PHASE 5: 后处理流水线 ==========
        if execution_metadata:
            async for chunk in _process_post_pipeline(session_id, llm_client, request_id):
                yield chunk
        
    except Exception as e:
        print(f"[ERROR] Streaming request {request_id} failed: {e}")
        import traceback
        traceback.print_exc()
        
        # 确保工具使用结束信号被发送
        yield f"data: {json.dumps({'type': 'NAGISA_TOOL_USE_CONCLUDED'})}\n\n"
        error_data = {'type': 'error', 'error': f"Request processing failed: {str(e)}"}
        yield f"data: {json.dumps(error_data)}\n\n"
        
    finally:
        # ========== PHASE 6: 清理和释放 ==========
        async with ACTIVE_REQUESTS_LOCK:
            if session_id in ACTIVE_REQUESTS and ACTIVE_REQUESTS[session_id] == request_id:
                del ACTIVE_REQUESTS[session_id]
                print(f"[DEBUG] Released streaming request {request_id} for session {session_id}")


async def _process_content_pipeline(
    final_message: BaseMessage,
    session_id: str,
    tts_engine: BaseTTS,
    request_id: str
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    内容处理流水线 - 专门处理最终响应内容
    
    原子性处理最终消息，包括消息保存、TTS处理等
    """
    if not hasattr(final_message, 'content'):
        return
    
    content = final_message.content
    
    # 提取文本内容，过滤掉thinking部分
    text_content = ""
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get('type') == 'text':
                text_content += item.get('text', '')
            # 明确跳过thinking和redacted_thinking类型
            elif isinstance(item, dict) and item.get('type') in ['thinking', 'redacted_thinking']:
                continue
    else:
        text_content = str(content)
    
    if not text_content.strip():
        return 
    
    # 处理AI文本消息 - 保存到历史记录，使用过滤后的内容
    loaded_history = load_all_message_history(session_id)
    history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in loaded_history]
    
    # 创建过滤后的内容用于保存和TTS
    filtered_content = content
    if isinstance(content, list):
        filtered_content = []
        for item in content:
            if isinstance(item, dict) and item.get('type') not in ['thinking', 'redacted_thinking']:
                filtered_content.append(item)
            elif not isinstance(item, dict):
                filtered_content.append(item)
        
        # 如果过滤后没有内容，添加空文本块
        if not filtered_content:
            filtered_content = [{"type": "text", "text": ""}]
    
    ai_msg_id, processed_content = process_ai_text_message(
        filtered_content,
        getattr(final_message, 'keyword', None),
        history_msgs,
        session_id
    )
    
    # 发送消息ID
    yield f"data: {json.dumps({'message_id': ai_msg_id})}\n\n"
    
    # 发送关键词
    if hasattr(final_message, 'keyword') and final_message.keyword:
        yield f"data: {json.dumps({'keyword': final_message.keyword})}\n\n"
    
    # TTS处理流水线
    async for chunk in _process_tts_pipeline(processed_content, tts_engine):
        yield chunk


async def _process_tts_pipeline(
    content: str,
    tts_engine: BaseTTS
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    TTS处理流水线 - 专门处理语音合成
    
    分句处理，支持表情符号和颜文字
    """
    # 处理表情和颜文字
    text_with_placeholders, kaomoji_list, emoji_list = extract_and_replace_emoticons(content)
    
    # 分句处理
    sentences = split_text_by_punctuations(text_with_placeholders)
    
    for sentence in sentences:
        tts_text = clean_text_for_tts(sentence)
        tts_result = await process_tts_sentence(tts_text, tts_engine)
        
        if tts_result:
            tts_result['text'] = restore_emoticons(sentence, kaomoji_list, emoji_list)
            yield f"data: {json.dumps(tts_result)}\n\n"


async def _process_post_pipeline(
    session_id: str,
    llm_client: LLMClientBase,
    request_id: str
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    后处理流水线 - 专门处理标题生成等后续任务
    
    非阻塞的后台处理，失败不影响主流程
    """
    try:
        loaded_history = load_all_message_history(session_id)
        history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in loaded_history]
        
        if should_generate_title(session_id, history_msgs):
            new_title = await generate_title_for_session(session_id, llm_client)
            if new_title:
                update_success = update_session_title(session_id, new_title)
                if update_success:
                    title_update_data = {
                        'type': 'TITLE_UPDATE',
                        'payload': {
                            'session_id': session_id,
                            'title': new_title
                        }
                    }
                    yield f"data: {json.dumps(title_update_data)}\n\n"
    except Exception as e:
        # 后处理失败不应影响主流程，只记录日志
        print(f"[WARNING] Post-processing failed for request {request_id}: {e}")


async def generate_chat_stream(session_id: str, recent_msgs: List[BaseMessage], llm_client: LLMClientBase, tts_engine: BaseTTS) -> AsyncGenerator[str, None]:
    """
    聊天流式响应生成器 - 封装完整的流式处理流程
    
    这个函数整合了完整的流式处理逻辑，包括：
    1. 状态管理
    2. 错误处理  
    3. 流式响应生成
    """
    # Generate unique request ID for debugging
    request_id = str(uuid.uuid4())[:8]
    print(f"[DEBUG] API Request {request_id} started - Session: {session_id}")
    
    yield f"data: {json.dumps({'status': 'sent'})}\n\n"
    
    try:
        yield f"data: {json.dumps({'status': 'read'})}\n\n"
        
        # 使用 load_history 获取不含图片消息的最近对话
        recent_history = load_history(session_id)  # load history without image
        # 使用 message_factory_no_thinking 创建历史消息，过滤掉 thinking 块
        recent_msgs = [message_factory_no_thinking(msg) if isinstance(msg, dict) else msg for msg in recent_history]
        recent_messages_length = get_llm_config().get("recent_messages_length", 20)
        recent_msgs = recent_msgs[-recent_messages_length:]
        
        async for chunk in handle_llm_response(recent_msgs, session_id, llm_client, tts_engine):
            yield chunk
            
    except Exception as e:
        print(f"[ERROR] API Request {request_id} - Exception in generate(): {e}")
        yield f"data: {json.dumps({'type': 'NAGISA_TOOL_USE_CONCLUDED'})}\n\n"
        error_data = {
            'type': 'error',
            'error': str(e)
        }
        yield f"data: {json.dumps(error_data)}\n\n"
        raise e