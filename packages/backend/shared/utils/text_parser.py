"""
Text parsing utility module

Provides parsing functionality for LLM output text, including keyword extraction and text processing.
"""

import re
from typing import List, Optional
from pathlib import Path


def parse_llm_output(llm_full_response: str) -> dict:
    """
    Parse LLM output to extract reply text.
    Strips [[keyword]] tags from the end of the message to keep the UI clean,
    even though Live2D animations are no longer triggered.

    Args:
        llm_full_response: Complete response text from LLM
    Returns:
        Dictionary with 'text' and 'keyword' keys
    """
    text = llm_full_response.strip()
    keyword = "neutral"
    
    # Strip [[keyword]] from the end if present
    match = re.search(r'\[\[(\w+)\]\]\s*$', text)
    if match:
        text = text[:match.start()].strip()
        keyword = match.group(1).lower()

    return {
        'text': text,
        'keyword': keyword
    }