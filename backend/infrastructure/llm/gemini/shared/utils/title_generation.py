"""
Title generation utility functions for Gemini API operations.

This module contains utility functions specifically for conversation title generation,
including title parsing and formatting.
"""

import re
from typing import Optional
from ..constants.title_generation import DEFAULT_TITLE_MAX_LENGTH


def parse_title_response(
    response_text: str,
    max_length: int = DEFAULT_TITLE_MAX_LENGTH,
    debug: bool = False
) -> Optional[str]:
    """
    Parse title generation response and extract the title.
    
    Args:
        response_text: The raw response text from the model
        max_length: Maximum allowed title length
        debug: Enable debug output
        
    Returns:
        Extracted and cleaned title string, or None if extraction fails
    """
    if not response_text:
        if debug:
            print("[TitleGeneration] Error: Empty response text")
        return None
    
    try:
        # Try to extract title from <title></title> tags first
        title_match = re.search(r'<title>(.*?)</title>', response_text, re.DOTALL)
        if title_match:
            title = title_match.group(1).strip()
            if not title:
                if debug:
                    print("[TitleGeneration] Error: Title tag found but content is empty")
                return None
            
            # Truncate if too long
            if len(title) > max_length:
                title = title[:max_length]
                if debug:
                    print(f"[TitleGeneration] Title truncated to {max_length} characters")
            
            return title
        
        # Fallback: use the entire response as title after cleaning
        cleaned_title = response_text.strip().strip('"\'').strip()
        if cleaned_title and len(cleaned_title) <= max_length:
            if debug:
                print("[TitleGeneration] Using cleaned response as title (fallback)")
            return cleaned_title
        
        if debug:
            print(f"[TitleGeneration] Error: No valid title found in response: {response_text[:100]}...")
        
        return None
        
    except Exception as e:
        if debug:
            print(f"[TitleGeneration] Error parsing title response: {str(e)}")
        return None