"""
Content Filters - Utilities for cleaning message content.

Provides functions to strip system-injected tags from message content,
useful for displaying clean history to users or exporting conversations.

System tags are injected at runtime by ReminderInjector and StatusMonitor
to provide context to the LLM. These should be filtered when:
- Returning session history to frontend
- Exporting chat conversations
- Generating message summaries
"""

import re
from typing import Any, Dict, List, Union

# Top-level tags that need to be filtered
# Note: bash-*, pfc-python etc. are nested inside system-reminder
SYSTEM_TAGS = frozenset({
    "system-reminder",
    "memory-context",
})


def strip_system_tags(
    text: str,
    tags: frozenset[str] = SYSTEM_TAGS
) -> str:
    """
    Remove system-injected XML tags and their content from text.

    Args:
        text: Text content potentially containing system tags
        tags: Set of tag names to strip (default: SYSTEM_TAGS)

    Returns:
        Cleaned text with specified tags and their content removed

    Example:
        >>> text = "Hello<system-reminder>internal</system-reminder>World"
        >>> strip_system_tags(text)
        'HelloWorld'
    """
    if not text:
        return text

    result = text
    for tag in tags:
        # Pattern matches: <tag>...content...</tag> (including newlines)
        # Using DOTALL flag via (?s) for multiline content
        pattern = rf"(?s)<{tag}>.*?</{tag}>"
        result = re.sub(pattern, "", result)

    # Clean up extra whitespace left by removal
    # - Multiple newlines -> double newline (preserve paragraph breaks)
    # - Leading/trailing whitespace
    result = re.sub(r"\n{3,}", "\n\n", result)
    result = result.strip()

    return result


def filter_message_content(
    content: Union[str, List[Dict[str, Any]]],
    tags: frozenset[str] = SYSTEM_TAGS
) -> Union[str, List[Dict[str, Any]]]:
    """
    Filter system tags from message content.

    Handles both string content and content block list formats.
    Recursively filters nested content in tool_result blocks.

    Args:
        content: Message content (string or list of content blocks)
        tags: Set of tag names to strip (default: SYSTEM_TAGS)

    Returns:
        Filtered content in the same format as input
    """
    if isinstance(content, str):
        return strip_system_tags(content, tags)

    if isinstance(content, list):
        filtered_blocks = []
        for block in content:
            if isinstance(block, dict):
                filtered_block = block.copy()

                # Filter text content in text blocks
                if block.get("type") == "text" and "text" in block:
                    filtered_block["text"] = strip_system_tags(block["text"], tags)

                # Filter nested content in tool_result blocks
                # Structure: {"type": "tool_result", "content": {"parts": [{"type": "text", "text": "..."}]}}
                elif block.get("type") == "tool_result" and "content" in block:
                    nested_content = block["content"]
                    if isinstance(nested_content, dict) and "parts" in nested_content:
                        filtered_parts = []
                        for part in nested_content.get("parts", []):
                            if isinstance(part, dict):
                                filtered_part = part.copy()
                                if part.get("type") == "text" and "text" in part:
                                    filtered_part["text"] = strip_system_tags(part["text"], tags)
                                filtered_parts.append(filtered_part)
                            else:
                                filtered_parts.append(part)
                        filtered_block["content"] = {**nested_content, "parts": filtered_parts}

                filtered_blocks.append(filtered_block)
            else:
                filtered_blocks.append(block)
        return filtered_blocks

    # Unknown format, return as-is
    return content
