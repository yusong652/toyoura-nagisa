"""
Text processing utilities shared across LLM providers.

Common text processing functions that can be reused by different provider implementations.
"""

import re
from typing import Union, List, Dict, Any, Optional, Tuple
from backend.config import get_text_to_image_settings
try:
    from ..constants.prompts import (
        TEXT_TO_IMAGE_PROMPT_PATTERN,
        NEGATIVE_PROMPT_PATTERN,
        TITLE_PROMPT_PATTERN
    )
except ImportError:
    # Fallback values if constants are not available
    DEFAULT_NEGATIVE_PROMPT = "low quality, worst quality, blurry"
    TEXT_TO_IMAGE_PROMPT_PATTERN = r'<prompt>(.*?)</prompt>'
    NEGATIVE_PROMPT_PATTERN = r'<negative_prompt>(.*?)</negative_prompt>'
    TITLE_PROMPT_PATTERN = r'<title>(.*?)</title>'


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
) -> Optional[Tuple[str, str]]:
    """
    Parse text-to-image prompt response and extract text_prompt and negative_prompt.
    
    Args:
        response_text: The raw response text from the model
        debug: Enable debug output
        
    Returns:
        Tuple of (text_prompt, negative_prompt) if successful, None if failed.
        negative_prompt will be empty string if none found in response.
    """
    try:
        from backend.config import get_llm_settings
        debug = get_llm_settings().debug
        # Clean up markdown code blocks if present
        cleaned_text = response_text
        if "```" in response_text:
            # Remove markdown code block markers
            cleaned_text = re.sub(r'```(?:text|xml|html)?\n?', '', response_text)
        # Extract text prompt
        text_prompt_match = re.search(TEXT_TO_IMAGE_PROMPT_PATTERN, cleaned_text, re.DOTALL)
        if not text_prompt_match:
            if debug:
                print(f"[text_to_image] Error: Failed to extract text prompt from response\nFull prompt text: {response_text}", flush=True)
            return None
        
        text_prompt = text_prompt_match.group(1).strip()
        if not text_prompt:
            if debug:
                print(f"[text_to_image] Error: Extracted text prompt is empty", flush=True)
            return None
        
        # Extract negative prompt
        negative_prompt_match = re.search(NEGATIVE_PROMPT_PATTERN, cleaned_text, re.DOTALL)
        negative_prompt = negative_prompt_match.group(1).strip() if negative_prompt_match else ""
        print(f"[text_to_image] Extracted text prompt: '{text_prompt}'", flush=True)
        print(f"[text_to_image] Extracted negative prompt: '{negative_prompt}'", flush=True)
        return text_prompt, negative_prompt
        
    except Exception as e:
        from backend.config import get_llm_settings
        debug = get_llm_settings().debug
        if debug:
            print(f"[text_to_image] Error parsing response text: {str(e)}", flush=True)
        return None


def enhance_prompts_with_defaults(
    text_prompt: str,
    negative_prompt: str,
    debug: bool = False
) -> Tuple[str, str]:
    """
    Enhance text and negative prompts by adding missing default keywords from config.
    
    Args:
        text_prompt: Original text prompt
        negative_prompt: Original negative prompt
        debug: Enable debug output
        
    Returns:
        Tuple of (enhanced_text_prompt, enhanced_negative_prompt)
    """
    # Read default prompts from configuration
    text_to_image_settings = get_text_to_image_settings()
    default_positive_prompt = text_to_image_settings.text_to_image_default_positive_prompt
    default_negative_prompt = text_to_image_settings.text_to_image_default_negative_prompt
    enhanced_text_prompt = text_prompt
    enhanced_negative_prompt = negative_prompt
    
    # Check and supplement default positive keywords
    if default_positive_prompt:
        # Split keywords by comma
        default_keywords = default_positive_prompt.split(",")
        existing_keywords = text_prompt.split(",")
        # Find missing keywords
        missing_keywords = [
            kw for kw in default_keywords 
            if kw.strip() and kw.strip() not in [ek.strip() for ek in existing_keywords]
        ]
        if missing_keywords:
            # Clean original prompt
            enhanced_text_prompt = text_prompt.strip().lstrip(",").strip()
            # Join all keywords with comma
            enhanced_text_prompt = ", ".join(missing_keywords) + (", " + enhanced_text_prompt if enhanced_text_prompt else "")

    # Check and supplement default negative keywords
    if default_negative_prompt:
        # Split keywords by comma
        default_keywords = default_negative_prompt.split(",")
        existing_keywords = negative_prompt.split(",")
        # Find missing keywords
        missing_keywords = [
            kw for kw in default_keywords 
            if kw.strip() and kw.strip() not in [ek.strip() for ek in existing_keywords]
        ]
        if missing_keywords:
            # Clean original prompt
            enhanced_negative_prompt = negative_prompt.strip().lstrip(",").strip()
            # Join all keywords with comma, ensure no leading spaces
            enhanced_negative_prompt = ", ".join(missing_keywords) + (", " + enhanced_negative_prompt.lstrip() if enhanced_negative_prompt else "")

    if debug:
        print(f"[text_to_image] Enhanced text_prompt: {enhanced_text_prompt}")
        print(f"[text_to_image] Enhanced negative_prompt: {enhanced_negative_prompt}")
    
    return enhanced_text_prompt, enhanced_negative_prompt


def parse_title_response(
    response_text: str,
    max_length: int = 50
) -> Optional[str]:
    """
    Parse title generation response and extract clean title.
    
    Args:
        response_text: The raw response text from the model
        max_length: Maximum allowed title length
        debug: Enable debug output
        
    Returns:
        Cleaned title string, or None if parsing failed
    """
    try:
        # Clean up markdown code blocks if present
        cleaned_text = response_text
        if "```" in response_text:
            # Remove markdown code block markers
            cleaned_text = re.sub(r'```(?:text|xml|html)?\n?', '', response_text)
        # Try to extract title using pattern matching
        title_match = re.search(TITLE_PROMPT_PATTERN, cleaned_text, re.DOTALL)
        if title_match:
            title = title_match.group(1).strip()
        else:
            # Fallback: use entire response as title
            title = cleaned_text.strip()
        
        # Clean up the title
        title = title.strip('"').strip("'").strip()
        
        # Truncate if too long
        if len(title) > max_length:
            title = title[:max_length].rsplit(' ', 1)[0] + "..."
        
        return title if title else None
        
    except Exception as e:
        from backend.config import get_llm_settings
        debug = get_llm_settings().debug
        if debug:
            print(f"[title_generation] Error parsing title response: {str(e)}")
        return None


def clean_response_text(text: str) -> str:
    """
    Clean and normalize response text.
    
    Args:
        text: Raw response text
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Remove common artifacts
    text = re.sub(r'^\s*[-*]\s*', '', text)  # Remove leading bullets
    text = re.sub(r'\s*\n\s*', ' ', text)   # Normalize line breaks
    
    return text