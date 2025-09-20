# TTS utility functions for text processing and emoticon handling

import re
import emoji  # requires pip install emoji
from typing import Optional
from backend.config import get_tts_settings

# Pre-compiled regular expression patterns for safe text processing
# Match parentheses with 2-15 non-parentheses characters inside (for simple kaomoji like (^_^))
KAOMOJI_PATTERN_PARENS = re.compile(r'\([^()]{2,15}\)')
# Match keyword markers [[...]] (in case they remain from previous processing)
KEYWORD_MARKER_PATTERN = re.compile(r'\[\[\w+\]\]\s*$')
# Match consecutive whitespace characters
WHITESPACE_PATTERN = re.compile(r'\s+')

# Get default values from configuration file
tts_settings = get_tts_settings()
DEFAULT_SPLIT_PUNCTUATIONS = getattr(tts_settings, 'split_punctuations', ['。', '！', '？', '!', '?', '.', '，', ',', '~', '、', '…', '—', '：', '；', '...', '..'])
DEFAULT_PUNCTUATION_LIMIT = getattr(tts_settings, 'split_size', 12)

# Extract and replace emoji and kaomoji with placeholders
KAOMOJI_PLACEHOLDER = "__KAOMOJI_{}__"
EMOJI_PLACEHOLDER = "__EMOJI_{}__"

# 1. Extract and replace emoticons
def extract_and_replace_emoticons(text: str):
    if not isinstance(text, str) or not text:
        return text, [], []
    text = KEYWORD_MARKER_PATTERN.sub('', text).strip()
    kaomoji_list = []
    emoji_list = []
    # Replace kaomoji first
    kaomoji_idx = [0]  # Use list wrapper to allow modification in lambda
    def _kaomoji_repl(match):
        idx = kaomoji_idx[0]
        kaomoji_list.append(match.group(0))
        kaomoji_idx[0] += 1
        return KAOMOJI_PLACEHOLDER.format(idx)
    text = KAOMOJI_PATTERN_PARENS.sub(_kaomoji_repl, text)
    # Then replace emoji
    emoji_idx = [0]
    def _emoji_repl(char, _data=None):  # Fix: accept two parameters
        idx = emoji_idx[0]
        emoji_list.append(char)
        emoji_idx[0] += 1
        return EMOJI_PLACEHOLDER.format(idx)
    text = emoji.replace_emoji(text, replace=_emoji_repl)
    return text, kaomoji_list, emoji_list

# 2. Restore placeholders
def restore_emoticons(text: str, kaomoji_list, emoji_list):
    text = re.sub(r'__KAOMOJI_(\d+)__', lambda m: kaomoji_list[int(m.group(1))] if int(m.group(1)) < len(kaomoji_list) else '', text)
    text = re.sub(r'__EMOJI_(\d+)__', lambda m: emoji_list[int(m.group(1))] if int(m.group(1)) < len(emoji_list) else '', text)
    return text

# 3. Clean text for TTS (remove all placeholders and extra whitespace)
def clean_text_for_tts(text: str) -> str:
    if not isinstance(text, str) or not text:
        return text
    # Remove placeholders
    text = re.sub(r'__KAOMOJI_\d+__', '', text)
    text = re.sub(r'__EMOJI_\d+__', '', text)
    text = WHITESPACE_PATTERN.sub(' ', text)
    return text.strip()

# 4. Text segmentation
def split_text_by_punctuations(text: str, punctuations: Optional[list[str]] = None, punctuation_limit: Optional[int] = None) -> list[str]:
    """
    Split text into multiple segments based on punctuation marks.
    Uses regular expressions for better efficiency and edge case handling.

    Args:
        text: Text to be split
        punctuations: List of punctuation marks for splitting, defaults to config file values
        punctuation_limit: Split after how many punctuation marks, defaults to config file values

    Returns:
        List of split text segments
    """
    # Use default values from configuration file
    if punctuations is None:
        punctuations = DEFAULT_SPLIT_PUNCTUATIONS
    if punctuation_limit is None:
        punctuation_limit = DEFAULT_PUNCTUATION_LIMIT

    # Type check to ensure not None
    assert punctuations is not None and punctuation_limit is not None

    if not text or not punctuations or punctuation_limit <= 0:
        return [text] if text else []

    # Build regular expression pattern for punctuation marks
    punctuation_pattern = '|'.join(re.escape(p) for p in punctuations)
    
    # Use regular expression to find all punctuation mark positions
    matches = list(re.finditer(f'[{punctuation_pattern}]', text))
    
    if not matches:
        return [text]

    segments = []
    start_pos = 0
    
    # Split every punctuation_limit punctuation marks
    for i in range(0, len(matches), punctuation_limit):
        if i + punctuation_limit <= len(matches):
            # Get the position of the last punctuation mark in current group
            end_pos = matches[i + punctuation_limit - 1].end()
        else:
            # Handle the last group (when less than punctuation_limit punctuation marks)
            end_pos = matches[-1].end()
        
        # Extract current segment and clean whitespace
        segment = text[start_pos:end_pos].strip()
        if segment:
            segments.append(segment)
        
        start_pos = end_pos
    
    # Handle remaining text at the end
    if start_pos < len(text):
        remaining = text[start_pos:].strip()
        if remaining:
            segments.append(remaining)
    
    return segments