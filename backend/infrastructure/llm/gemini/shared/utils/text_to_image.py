"""
Text-to-image utility functions for Gemini API operations.

This module contains utility functions specifically for text-to-image operations,
including history management and text content extraction.
"""

import os
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Union, Optional, Tuple
from ..constants import (
    DEFAULT_NEGATIVE_PROMPT,
    TEXT_TO_IMAGE_PROMPT_PATTERN,
    NEGATIVE_PROMPT_PATTERN,
    TEXT_TO_IMAGE_HISTORY_FILENAME,
    DEFAULT_MAX_HISTORY_LENGTH
)


def get_text_to_image_history_file(session_id: str) -> str:
    """Get the path to the text-to-image history file for a session."""
    from backend.infrastructure.storage.session_manager import HISTORY_BASE_DIR
    session_dir = os.path.join(HISTORY_BASE_DIR, session_id)
    return os.path.join(session_dir, TEXT_TO_IMAGE_HISTORY_FILENAME)


def load_text_to_image_history(session_id: str) -> List[Dict[str, Any]]:
    """
    Load text-to-image prompt generation history for a session.
    
    Args:
        session_id: Session ID to load history for
        
    Returns:
        List of previous prompt generation records, each containing:
        - user_message: The original request
        - assistant_message: The generated prompt response
        - timestamp: When the generation occurred
    """
    history_file = get_text_to_image_history_file(session_id)
    
    if not os.path.exists(history_file):
        return []
    
    try:
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
            return history
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[WARNING] Failed to load text-to-image history for session {session_id}: {e}")
        return []


def save_text_to_image_generation(
    session_id: str, 
    user_request: str, 
    assistant_response: str,
    max_history_length: int = DEFAULT_MAX_HISTORY_LENGTH
) -> None:
    """
    Save a text-to-image prompt generation record to history.
    
    Args:
        session_id: Session ID to save to
        user_request: The original user request text
        assistant_response: Complete assistant response content
        max_history_length: Maximum number of records to keep (default: 10)
    """
    history_file = get_text_to_image_history_file(session_id)
    
    # Ensure session directory exists
    session_dir = os.path.dirname(history_file)
    os.makedirs(session_dir, exist_ok=True)
    
    # Load existing history
    history = load_text_to_image_history(session_id)
    
    # Create new record
    new_record = {
        "user_message": {
            "role": "user",
            "content": user_request
        },
        "assistant_message": {
            "role": "assistant", 
            "content": assistant_response  # 保存完整的assistant response，不做格式化
        },
        "timestamp": datetime.now().isoformat()
    }
    
    # Add new record and maintain history length
    history.append(new_record)
    if len(history) > max_history_length:
        history = history[-max_history_length:]  # Keep only the latest records
    
    # Save updated history
    try:
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ERROR] Failed to save text-to-image history for session {session_id}: {e}")


def extract_text_content(content: Union[str, List[dict]]) -> str:
    """
    Extract text content from BaseMessage content field.
    
    Args:
        content: Either a string or a list of content dictionaries
        
    Returns:
        Extracted text content as string
    """
    if isinstance(content, str):
        return content
    
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get('type') == 'text' and 'text' in item:
                    text_parts.append(item['text'])
                elif 'text' in item:  # Fallback for other formats
                    text_parts.append(item['text'])
        return ' '.join(text_parts)
    
    # Fallback for unexpected formats
    return str(content)


def parse_text_to_image_response(
    response_text: str,
    default_negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
    debug: bool = False
) -> Optional[Tuple[str, str]]:
    """
    Parse text-to-image prompt response and extract text_prompt and negative_prompt.
    
    Args:
        response_text: The raw response text from the model
        default_negative_prompt: Default negative prompt if none found in response
        debug: Enable debug output
        
    Returns:
        Tuple of (text_prompt, negative_prompt) if successful, None if failed
    """
    try:
        # Extract text prompt
        text_prompt_match = re.search(TEXT_TO_IMAGE_PROMPT_PATTERN, response_text, re.DOTALL)
        if not text_prompt_match:
            if debug:
                print(f"[text_to_image] Error: Failed to extract text prompt from response\nFull prompt text: {response_text}")
            return None
        
        text_prompt = text_prompt_match.group(1).strip()
        if not text_prompt:
            if debug:
                print(f"[text_to_image] Error: Extracted text prompt is empty")
            return None
        
        # Extract negative prompt
        negative_prompt_match = re.search(NEGATIVE_PROMPT_PATTERN, response_text, re.DOTALL)
        negative_prompt = negative_prompt_match.group(1).strip() if negative_prompt_match else default_negative_prompt
        
        return text_prompt, negative_prompt
        
    except Exception as e:
        if debug:
            print(f"[text_to_image] Error parsing response text: {str(e)}")
        return None


def enhance_prompts_with_defaults(
    text_prompt: str,
    negative_prompt: str,
    default_positive_prompt: str = "",
    default_negative_prompt: str = "",
    debug: bool = False
) -> Tuple[str, str]:
    """
    Enhance text and negative prompts by adding missing default keywords.
    
    Args:
        text_prompt: Original text prompt
        negative_prompt: Original negative prompt
        default_positive_prompt: Default positive keywords to add if missing
        default_negative_prompt: Default negative keywords to add if missing
        debug: Enable debug output
        
    Returns:
        Tuple of (enhanced_text_prompt, enhanced_negative_prompt)
    """
    enhanced_text_prompt = text_prompt
    enhanced_negative_prompt = negative_prompt
    
    # 检查并补充默认正面关键词
    if default_positive_prompt:
        # 用逗号分隔关键词
        default_keywords = default_positive_prompt.split(",")
        existing_keywords = text_prompt.split(",")
        # 找出缺失的关键词
        missing_keywords = [
            kw for kw in default_keywords 
            if kw.strip() and kw.strip() not in [ek.strip() for ek in existing_keywords]
        ]
        if missing_keywords:
            # 清理原始提示词
            enhanced_text_prompt = text_prompt.strip().lstrip(",").strip()
            # 用逗号连接所有关键词
            enhanced_text_prompt = ", ".join(missing_keywords) + (", " + enhanced_text_prompt if enhanced_text_prompt else "")

    # 检查并补充默认负面关键词
    if default_negative_prompt:
        # 用逗号分隔关键词
        default_keywords = default_negative_prompt.split(",")
        existing_keywords = negative_prompt.split(",")
        # 找出缺失的关键词
        missing_keywords = [
            kw for kw in default_keywords 
            if kw.strip() and kw.strip() not in [ek.strip() for ek in existing_keywords]
        ]
        if missing_keywords:
            # 清理原始提示词
            enhanced_negative_prompt = negative_prompt.strip().lstrip(",").strip()
            # 用逗号连接所有关键词，确保没有前导空格
            enhanced_negative_prompt = ", ".join(missing_keywords) + (", " + enhanced_negative_prompt.lstrip() if enhanced_negative_prompt else "")

    if debug:
        print(f"[text_to_image] Enhanced text_prompt: {enhanced_text_prompt}")
        print(f"[text_to_image] Enhanced negative_prompt: {enhanced_negative_prompt}")
    
    return enhanced_text_prompt, enhanced_negative_prompt