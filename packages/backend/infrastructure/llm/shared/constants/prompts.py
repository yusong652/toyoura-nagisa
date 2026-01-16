"""
Prompt templates and patterns shared across LLM providers.

Common prompt templates, system prompts, and regex patterns for response parsing.
"""

# === SYSTEM PROMPTS ===

# Default system prompt for title generation
DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT = (
    "You are a professional conversation title generator. Based on the provided conversation content, "
    "generate a concise title (5-15 words). The title should accurately summarize the main topic or intent "
    "of the conversation. IMPORTANT: Generate the title in the same language as the conversation - if the "
    "conversation is in Chinese, generate a Chinese title; if in English, generate an English title, etc. "
    "You must place the title within <title></title> tags, and output nothing else "
    "except these tags and the title itself."
)

# Default system prompt for web search
DEFAULT_WEB_SEARCH_SYSTEM_PROMPT = (
    "You are a helpful assistant with access to web search. When users ask questions that require "
    "current information or recent events, use the web search tool to find accurate and up-to-date "
    "information. Provide comprehensive answers based on your search results."
)

# === PROMPT TEMPLATES ===

# Title generation request text
TITLE_GENERATION_REQUEST_TEXT = "Please generate a title for the above conversation"

# === REGEX PATTERNS ===

# Pattern for extracting titles from responses
TITLE_PROMPT_PATTERN = r'<title>(.*?)</title>'

# Alternative title patterns for fallback
TITLE_FALLBACK_PATTERNS = [
    r'Title:\s*(.+?)(?:\n|$)',
    r'"(.+?)"',
    r'(.+?)(?:\n|$)'
]
