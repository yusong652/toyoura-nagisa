"""
File mention infrastructure - Extract and inject mentioned file contents.

This module handles @file mentions in user messages:
- Validate and read mentioned files
- Format file contents as system-reminder blocks
- Deduplicate within single message
"""

from .file_mention_processor import FileMentionProcessor

__all__ = ["FileMentionProcessor"]
