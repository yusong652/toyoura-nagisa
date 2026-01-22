"""
Text processing utilities shared across LLM providers.

Common text processing functions that can be reused by different provider implementations.
"""

import re
from typing import Union, List, Optional

try:
    from ..constants.prompts import TITLE_PROMPT_PATTERN
except ImportError:
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


def parse_title_response(
    response_text: str,
    max_length: int = 50
) -> Optional[str]:
    """
    Parse title generation response and extract clean title.

    Args:
        response_text: The raw response text from the model
        max_length: Maximum allowed title length

    Returns:
        Cleaned title string, or None if parsing failed
    """
    try:
        # Handle None or empty response
        if not response_text:
            return None

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
        from backend.config.dev import get_dev_config
        debug = get_dev_config().debug_mode
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
