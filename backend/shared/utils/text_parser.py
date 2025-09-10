"""
Text parsing utility module

Provides parsing functionality for LLM output text, including keyword extraction and text processing.
"""

import re
from typing import List, Tuple, Optional
from pathlib import Path


# Keywords cache
_allowed_keywords_cache: Optional[List[str]] = None


def get_allowed_keywords_from_prompt_file() -> List[str]:
    """
    Parse allowed keywords list from prompt file.
    Results are cached.
    """
    global _allowed_keywords_cache
    if _allowed_keywords_cache is not None:
        return _allowed_keywords_cache

    # Use the new location in config/prompts
    project_root = Path(__file__).parent.parent.parent
    file_path = project_root / "config" / "prompts" / "expression_prompt.md"
    keywords = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        matches = re.findall(r'\[\[(\w+)\]\]', content)
        if matches:
            keywords = [keyword.lower() for keyword in matches]
        else:
            print(f"Warning: No keywords found in {file_path}.")
    except FileNotFoundError:
        print(f"Error: Keywords file '{file_path}' not found.")
    
    _allowed_keywords_cache = keywords
    return _allowed_keywords_cache


def parse_llm_output(llm_full_response: str) -> Tuple[str, str]:
    """
    Parse LLM output to extract reply text and keywords.
    Args:
        llm_full_response: Complete response text from LLM
    Returns:
        (response_text, keyword) tuple
    """
    allowed_keywords = get_allowed_keywords_from_prompt_file()
    
    keyword = "neutral"  # Default keyword
    response_text = llm_full_response.strip()

    match = re.search(r'\[\[(\w+)\]\]\s*$', llm_full_response.strip())
    if match:
        extracted_keyword = match.group(1).lower()
        if extracted_keyword in allowed_keywords:
            keyword = extracted_keyword
            response_text = llm_full_response[:match.start()].strip()
        else:
            print(f"Warning: LLM returned undefined keyword '{extracted_keyword}'")
            response_text = llm_full_response[:match.start()].strip()

    return response_text, keyword


def clear_keywords_cache() -> None:
    """Clear keywords cache, force re-reading file"""
    global _allowed_keywords_cache
    _allowed_keywords_cache = None