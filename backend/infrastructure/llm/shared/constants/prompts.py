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

# Default system prompt for text-to-image generation
DEFAULT_TEXT_TO_IMAGE_SYSTEM_PROMPT = (
    "You are an expert at creating detailed, artistic text-to-image prompts. Based on the conversation "
    "context provided, generate a comprehensive and creative prompt for image generation. "
    "Your response must include both a positive prompt and a negative prompt in the specified format:\n\n"
    "<text_to_image_prompt>[detailed positive prompt here]</text_to_image_prompt>\n"
    "<negative_prompt>[negative prompt here]</negative_prompt>\n\n"
    "The positive prompt should be descriptive, artistic, and include relevant style, lighting, "
    "composition, and quality keywords. The negative prompt should specify what to avoid."
)

# === PROMPT TEMPLATES ===

# Title generation request text
TITLE_GENERATION_REQUEST_TEXT = "Please generate a title for the above conversation"

# Conversation context prefix for text-to-image
CONVERSATION_TEXT_PROMPT_PREFIX = "Based on the following conversation, please generate a text-to-image prompt:\n\n"

# === REGEX PATTERNS ===

# Pattern for extracting text prompts from responses
TEXT_TO_IMAGE_PROMPT_PATTERN = r'<text_to_image_prompt>(.*?)</text_to_image_prompt>'

# Pattern for extracting negative prompts from responses
NEGATIVE_PROMPT_PATTERN = r'<negative_prompt>(.*?)</negative_prompt>'

# Pattern for extracting titles from responses
TITLE_PROMPT_PATTERN = r'<title>(.*?)</title>'

# Alternative title patterns for fallback
TITLE_FALLBACK_PATTERNS = [
    r'Title:\s*(.+?)(?:\n|$)',
    r'"(.+?)"',
    r'(.+?)(?:\n|$)'
]