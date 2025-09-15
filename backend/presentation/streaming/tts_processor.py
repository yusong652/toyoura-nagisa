"""
TTS (Text-to-Speech) processing pipeline.

This module handles the sequential processing of text content into audio,
optimized for first-chunk latency and robust error handling.
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, AsyncGenerator, Optional
from backend.infrastructure.tts.base import BaseTTS
from backend.infrastructure.tts.utils import (
    split_text_by_punctuations, 
    clean_text_for_tts, 
    extract_and_replace_emoticons, 
    restore_emoticons
)
from backend.shared.utils.helpers import process_tts_sentence

# TTS processing optimization
TTS_PROCESSING_POOL = asyncio.BoundedSemaphore(5)  # Limit concurrent TTS processing
logger = logging.getLogger(__name__)


async def process_tts_pipeline(
    content: str,
    tts_engine: BaseTTS
) -> AsyncGenerator[str, None]:
    """
    Sequential TTS Processing Pipeline - Optimized for First-Chunk Latency.
    
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
        str: TTS results in SSE format string, yielded sequentially as processed
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
                if not tts_text or not tts_text.strip():  # Skip empty sentences
                    logger.debug(f"Skipping empty sentence after text cleaning: '{sentence}' -> '{tts_text}'")
                    continue
                    
                sentence_start = time.time()
                
                try:
                    # Process single sentence synchronously for immediate delivery
                    result = await process_single_sentence_tts(
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


async def process_single_sentence_tts(
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