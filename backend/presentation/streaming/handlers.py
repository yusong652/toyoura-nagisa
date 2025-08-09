import json
import uuid
import asyncio
import logging
import time
from typing import Dict, Any, List, AsyncGenerator, Optional
from backend.infrastructure.llm import LLMClientBase
from backend.domain.models.messages import BaseMessage
from backend.domain.models.message_factory import message_factory, message_factory_no_thinking
from backend.infrastructure.storage.session_manager import load_all_message_history, load_history
from backend.infrastructure.tts.base import BaseTTS
from backend.infrastructure.tts.utils import split_text_by_punctuations, clean_text_for_tts, extract_and_replace_emoticons, restore_emoticons
from backend.shared.utils.helpers import (
    process_ai_text_message,
    process_tts_sentence,
    should_generate_title,
    generate_title_for_session,
)
from backend.infrastructure.storage.session_manager import update_session_title
from backend.config import get_llm_settings
from backend.presentation.models.websocket_messages import (
    create_error_message, create_status_message, create_tool_use_message
)

# TTS处理优化
TTS_PROCESSING_POOL = asyncio.BoundedSemaphore(5)  # 限制并发TTS处理数量
logger = logging.getLogger(__name__)


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
    
    # 优化的防重复机制 - 减少锁竞争
    async with ACTIVE_REQUESTS_LOCK:
        if session_id in ACTIVE_REQUESTS:
            existing_request = ACTIVE_REQUESTS[session_id]
            error_msg = f"Duplicate request detected. Session {session_id} already has active request {existing_request}"
            error_data = create_error_message(
                error=error_msg,
                session_id=session_id,
                recoverable=False
            )
            yield f"data: {json.dumps(error_data)}\n\n"
            return
        ACTIVE_REQUESTS[session_id] = request_id

    try:
        # ========== PHASE 2: 客户端验证 ==========
        # 支持所有已实现的LLM客户端
        supported_clients = ['GeminiClient', 'LocalLLMClient', 'AnthropicClient', 'OpenAIClient']
        if type(llm_client).__name__ not in supported_clients:
            error_msg = f"Unsupported LLM client: {type(llm_client).__name__}. Supported clients: {supported_clients}"
            error_data = create_error_message(
                error=error_msg,
                session_id=session_id,
                details={"client_type": type(llm_client).__name__, "supported": supported_clients}
            )
            yield f"data: {json.dumps(error_data)}\n\n"
            return
        
        if not hasattr(llm_client, 'get_response'):
            error_msg = f"{type(llm_client).__name__} missing get_response method"
            error_data = create_error_message(
                error=error_msg,
                session_id=session_id,
                details={"client_type": type(llm_client).__name__}
            )
            yield f"data: {json.dumps(error_data)}\n\n"
            return

        # ========== PHASE 3: 流式处理 - 实时工具调用通知 ==========
        print(f"[DEBUG] Processing streaming request {request_id} for session {session_id}")
        
        final_message = None
        execution_metadata = None
        
        # 使用新的流式方法 - 实时获取工具调用通知
        async for item in llm_client.get_response(
            recent_msgs, 
            session_id=session_id,
        ):
            if isinstance(item, tuple):
                # 最终结果: (final_message, execution_metadata)
                final_message, execution_metadata = item
                break
            elif isinstance(item, dict):
                # 实时通知: 工具调用状态更新
                yield f"data: {json.dumps(item)}\n\n"
        
        # ========== PHASE 4: 内容处理流水线 ==========
        if final_message:
            async for chunk in _process_content_pipeline(final_message, session_id, tts_engine, request_id, execution_metadata):
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
        tool_end_msg = create_tool_use_message(is_using=False, session_id=session_id)
        yield f"data: {json.dumps(tool_end_msg)}\n\n"
        
        error_data = create_error_message(
            error=f"Request processing failed: {str(e)}",
            session_id=session_id,
            details={"request_id": request_id, "traceback": traceback.format_exc()}
        )
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
    request_id: str,
    execution_metadata: Optional[Dict[str, Any]] = None
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    内容处理流水线 - 专门处理最终响应内容
    
    原子性处理最终消息，包括消息保存、TTS处理等
    """
    if not hasattr(final_message, 'content'):
        return
    
    content = final_message.content
    
    # 提取文本内容用于TTS（不包含thinking）
    text_content = ""
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get('type') == 'text':
                text_content += item.get('text', '')
            # thinking内容不用于TTS，但会保存到历史记录
    else:
        text_content = str(content)
    
    # 处理AI文本消息 - 保存到历史记录，包含完整content（包括thinking）
    # 注意：即使text_content为空，也要处理，因为可能只有关键词
    loaded_history = load_all_message_history(session_id)
    history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in loaded_history]
    
    # 提取关键词 - 优先使用metadata中的关键词，回退到文本解析
    extracted_keyword = None
    if execution_metadata and 'keyword' in execution_metadata:
        extracted_keyword = execution_metadata['keyword']
    else:
        # 回退：从文本内容中解析表情关键词
        from backend.shared.utils.text_parser import parse_llm_output
        _, extracted_keyword = parse_llm_output(text_content)
    
    # 直接保存完整内容，包括thinking
    ai_msg_id, processed_content = process_ai_text_message(
        content,  # 保存完整content，包括thinking内容
        extracted_keyword,  # 使用提取的关键词
        history_msgs,
        session_id
    )
    
    
    # 发送消息ID
    yield f"data: {json.dumps({'message_id': ai_msg_id})}\n\n"
    
    # 发送关键词 - 发送所有有效关键词（包括neutral）
    if extracted_keyword:
        yield f"data: {json.dumps({'keyword': extracted_keyword})}\n\n"
    
    # TTS处理流水线 - 仅在有文本内容时处理（不包含thinking）
    if text_content.strip():
        async for chunk in _process_tts_pipeline(text_content, tts_engine):
            yield chunk
    else:
        # 只有关键词的情况，发送一个空的文本块以保持流的完整性
        yield f"data: {json.dumps({'text': '', 'audio': None, 'index': 0})}\n\n"


async def _process_tts_pipeline(
    content: str,
    tts_engine: BaseTTS
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Sequential TTS Processing Pipeline - Optimized for First-Chunk Latency
    
    Sequential processing architecture designed to minimize time-to-first-audio:
    1. Processes sentences one at a time to eliminate resource contention
    2. Yields results immediately as they become available
    3. Prioritizes first-chunk delivery over total throughput
    4. Maintains TTS server resource efficiency
    
    Architecture Benefits:
    - Eliminates concurrent TTS request congestion
    - Guarantees predictable first-chunk latency
    - Reduces memory pressure from buffered requests
    - Provides graceful error handling per sentence
    
    Performance Monitoring:
    - Tracks first-chunk latency for optimization feedback
    - Monitors per-sentence processing times
    - Logs performance metrics for analysis
    
    Args:
        content: Text content to process for TTS synthesis
        tts_engine: BaseTTS implementation for audio generation
        
    Yields:
        Dict[str, Any]: TTS results in SSE format, yielded sequentially as processed
    """
    pipeline_start = time.time()
    first_chunk_delivered = False
    total_sentences_processed = 0
    
    async with TTS_PROCESSING_POOL:  # Maintain resource pool constraint
        try:
            # Process emoticons and kaomoji with placeholders
            text_with_placeholders, kaomoji_list, emoji_list = extract_and_replace_emoticons(content)
            
            # Split into sentences for sequential processing
            sentences = split_text_by_punctuations(text_with_placeholders)
            logger.debug(f"TTS pipeline processing {len(sentences)} sentences")
            
            # Sequential processing for optimal first-chunk latency
            sentence_index = 0
            
            for i, sentence in enumerate(sentences):
                tts_text = clean_text_for_tts(sentence)
                if not tts_text.strip():  # Skip empty sentences
                    continue
                    
                sentence_start = time.time()
                
                try:
                    # Process single sentence synchronously for immediate delivery
                    result = await _process_single_sentence_tts(
                        tts_text, sentence, kaomoji_list, emoji_list, sentence_index, tts_engine
                    )
                    
                    sentence_duration = time.time() - sentence_start
                    
                    if result:
                        # Track first-chunk latency metrics
                        if not first_chunk_delivered:
                            first_chunk_latency = time.time() - pipeline_start
                            logger.info(f"First-chunk TTS latency: {first_chunk_latency:.3f}s")
                            first_chunk_delivered = True
                        
                        # Add performance metadata to result
                        result['processing_time'] = round(sentence_duration, 3)
                        
                        # Immediate yield for minimal latency
                        yield f"data: {json.dumps(result)}\n\n"
                        sentence_index += 1
                        total_sentences_processed += 1
                        
                        logger.debug(f"TTS sentence {sentence_index-1} processed in {sentence_duration:.3f}s")
                        
                except Exception as e:
                    # Individual sentence errors don't block subsequent processing
                    sentence_duration = time.time() - sentence_start
                    error_msg = f"TTS processing error for sentence {i} '{tts_text[:50]}...': {e}"
                    logger.warning(error_msg)
                    
                    # Yield error result to maintain stream continuity
                    error_result = {
                        'text': restore_emoticons(sentence, kaomoji_list, emoji_list),
                        'audio': None,
                        'error': str(e),
                        'index': sentence_index,
                        'processing_time': round(sentence_duration, 3),
                        'failed': True
                    }
                    yield f"data: {json.dumps(error_result)}\n\n"
                    sentence_index += 1
                    
        except Exception as e:
            # Pipeline-level error handling
            logger.error(f"Critical TTS pipeline error: {e}")
            pipeline_error = {
                'error': f"TTS pipeline failed: {str(e)}",
                'pipeline_failed': True,
                'total_processed': total_sentences_processed
            }
            yield f"data: {json.dumps(pipeline_error)}\n\n"
            
        finally:
            # Log pipeline performance summary
            total_duration = time.time() - pipeline_start
            logger.info(f"TTS pipeline completed: {total_sentences_processed} sentences in {total_duration:.3f}s "
                       f"(avg: {total_duration/max(1, total_sentences_processed):.3f}s per sentence)")


async def _process_single_sentence_tts(
    tts_text: str, 
    original_sentence: str, 
    kaomoji_list: list, 
    emoji_list: list,
    index: int,
    tts_engine: BaseTTS
) -> Optional[Dict[str, Any]]:
    """
    Enhanced single sentence TTS processing with robust error handling.
    
    Implements graceful degradation and comprehensive error classification
    to ensure stream continuity even when individual sentences fail.
    
    Args:
        tts_text: Cleaned text for TTS synthesis
        original_sentence: Original sentence with emoticons/kaomoji
        kaomoji_list: List of extracted kaomoji placeholders
        emoji_list: List of extracted emoji placeholders
        index: Sentence index for ordering
        tts_engine: BaseTTS implementation for audio generation
        
    Returns:
        Optional[Dict[str, Any]]: TTS result with enhanced metadata, None on failure
            - text: str - Restored text with emoticons
            - audio: Optional[str] - Base64 encoded audio or None
            - index: int - Sentence ordering index
            - error: Optional[str] - Error details if synthesis failed
            - engine_status: str - TTS engine status indicator
    """
    try:
        # Validate TTS engine readiness
        if not tts_engine.enabled:
            logger.debug(f"TTS engine disabled, returning text-only result for sentence {index}")
            return {
                'text': restore_emoticons(original_sentence, kaomoji_list, emoji_list),
                'audio': None,
                'index': index,
                'engine_status': 'disabled'
            }
        
        # Process TTS with timeout protection
        try:
            tts_result = await asyncio.wait_for(
                process_tts_sentence(tts_text, tts_engine),
                timeout=30.0  # Prevent stuck requests
            )
            
            if tts_result:
                # Restore emoticons in the display text
                tts_result['text'] = restore_emoticons(original_sentence, kaomoji_list, emoji_list)
                tts_result['index'] = index
                tts_result['engine_status'] = 'success'
                
                # Validate audio data integrity
                if tts_result.get('audio') and not tts_result.get('error'):
                    logger.debug(f"TTS synthesis successful for sentence {index}")
                else:
                    logger.warning(f"TTS synthesis returned empty audio for sentence {index}")
                    tts_result['engine_status'] = 'partial_failure'
                
                return tts_result
            
        except asyncio.TimeoutError:
            logger.error(f"TTS synthesis timeout for sentence {index} '{tts_text[:50]}...'")
            return {
                'text': restore_emoticons(original_sentence, kaomoji_list, emoji_list),
                'audio': None,
                'index': index,
                'error': 'TTS synthesis timeout',
                'engine_status': 'timeout'
            }
            
        except Exception as synthesis_error:
            logger.error(f"TTS synthesis error for sentence {index}: {synthesis_error}")
            return {
                'text': restore_emoticons(original_sentence, kaomoji_list, emoji_list),
                'audio': None,
                'index': index,
                'error': f'Synthesis failed: {str(synthesis_error)}',
                'engine_status': 'synthesis_error'
            }
            
    except Exception as e:
        # Catch-all error handler for unexpected failures
        logger.error(f"Critical error processing sentence {index} '{tts_text[:50]}...': {e}")
        return {
            'text': restore_emoticons(original_sentence, kaomoji_list, emoji_list),
            'audio': None,
            'index': index,
            'error': f'Critical processing error: {str(e)}',
            'engine_status': 'critical_error'
        }
    
    return None


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
        recent_messages_length = get_llm_settings().recent_messages_length
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