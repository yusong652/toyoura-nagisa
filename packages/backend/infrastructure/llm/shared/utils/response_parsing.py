"""
Response parsing utilities shared across LLM providers.

Common response parsing and structured data extraction functions.
"""

import json
import re
from typing import Dict, Any, Optional, Union, List


def extract_json_from_response(response_text: str, debug: bool = False) -> Optional[Dict[str, Any]]:
    """
    Extract JSON content from response text.
    
    Args:
        response_text: Raw response text that may contain JSON
        debug: Enable debug output
        
    Returns:
        Parsed JSON dictionary, or None if extraction failed
    """
    try:
        # Try direct JSON parsing first
        return json.loads(response_text.strip())
    except json.JSONDecodeError:
        pass
    
    # Try to find JSON blocks in the text
    json_patterns = [
        r'```json\s*\n(.*?)\n\s*```',  # JSON code blocks
        r'```\s*\n(\{.*?\})\s*\n```',  # Generic code blocks with JSON
        r'(\{[^}]*\})',                # Simple JSON objects
        r'(\[[^\]]*\])',               # JSON arrays
    ]
    
    for pattern in json_patterns:
        matches = re.findall(pattern, response_text, re.DOTALL)
        for match in matches:
            try:
                parsed = json.loads(match.strip())
                if debug:
                    print(f"[response_parsing] Successfully extracted JSON: {type(parsed)}")
                return parsed
            except json.JSONDecodeError:
                continue
    
    if debug:
        print(f"[response_parsing] Failed to extract JSON from response")
    
    return None


def parse_structured_response(
    response_text: str, 
    expected_fields: List[str],
    debug: bool = False
) -> Dict[str, Any]:
    """
    Parse structured response with expected fields.
    
    Args:
        response_text: Raw response text
        expected_fields: List of expected field names
        debug: Enable debug output
        
    Returns:
        Dictionary with parsed fields (missing fields will have None values)
    """
    result = {field: None for field in expected_fields}
    
    # Try JSON extraction first
    json_data = extract_json_from_response(response_text, debug)
    if json_data and isinstance(json_data, dict):
        for field in expected_fields:
            if field in json_data:
                result[field] = json_data[field]
        return result
    
    # Fallback to pattern matching for each field
    for field in expected_fields:
        patterns = [
            rf'{field}:\s*"([^"]*)"',        # field: "value"
            rf'{field}:\s*\'([^\']*)\'',     # field: 'value'
            rf'{field}:\s*([^\n\r]+)',       # field: value
            rf'"{field}":\s*"([^"]*)"',      # "field": "value"
            rf'"{field}":\s*\'([^\']*)\'',   # "field": 'value'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, response_text, re.IGNORECASE)
            if match:
                result[field] = match.group(1).strip()
                break
    
    if debug:
        print(f"[response_parsing] Parsed structured response: {result}")
    
    return result


def extract_code_blocks(response_text: str, language: Optional[str] = None) -> List[str]:
    """
    Extract code blocks from response text.
    
    Args:
        response_text: Raw response text
        language: Specific language to extract (e.g., 'python', 'json')
        
    Returns:
        List of extracted code block contents
    """
    if language:
        pattern = rf'```{language}\s*\n(.*?)\n\s*```'
    else:
        pattern = r'```(?:\w+)?\s*\n(.*?)\n\s*```'
    
    matches = re.findall(pattern, response_text, re.DOTALL)
    return [match.strip() for match in matches]


def clean_response_content(content: str) -> str:
    """
    Clean response content by removing common artifacts.
    
    Args:
        content: Raw response content
        
    Returns:
        Cleaned content
    """
    if not content:
        return ""
    
    # Remove markdown artifacts
    content = re.sub(r'^#{1,6}\s+', '', content, flags=re.MULTILINE)  # Headers
    content = re.sub(r'\*\*(.*?)\*\*', r'\1', content)               # Bold
    content = re.sub(r'\*(.*?)\*', r'\1', content)                   # Italic
    
    # Remove excessive whitespace
    content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)              # Multiple empty lines
    content = re.sub(r'[ \t]+', ' ', content)                        # Multiple spaces/tabs
    
    return content.strip()