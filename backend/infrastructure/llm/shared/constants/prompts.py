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

# Default system prompt for video generation from image
DEFAULT_VIDEO_PROMPT_SYSTEM_PROMPT = (
    "You are an expert at transforming static image prompts into dynamic video prompts for AI video generation. "
    "Based on the original image prompt and motion type, generate optimized prompts for video creation. "
    "Your response must include both a video prompt and a negative prompt in the specified format:\n\n"
    "<video_prompt>[enhanced prompt with motion descriptions here]</video_prompt>\n"
    "<negative_prompt>[negative prompt for video generation here]</negative_prompt>\n\n"
    "The video prompt should add motion, camera movements, and temporal changes while preserving the core "
    "subject and artistic style. The negative prompt should specify what to avoid in video generation."
)

# === PROMPT TEMPLATES ===

# Title generation request text
TITLE_GENERATION_REQUEST_TEXT = "Please generate a title for the above conversation"

# Conversation context prefix for text-to-image
CONVERSATION_TEXT_PROMPT_PREFIX = "Based on the following conversation, please generate a text-to-image prompt:\n\n"

# Conversation context prefix for image-to-video
CONVERSATION_VIDEO_PROMPT_PREFIX = "Based on the following conversation, please generate an optimized video prompt for image-to-video generation:\n\n"

# === REGEX PATTERNS ===

# Pattern for extracting text prompts from responses
TEXT_TO_IMAGE_PROMPT_PATTERN = r'<text_to_image_prompt>(.*?)</text_to_image_prompt>'

# Pattern for extracting negative prompts from responses
NEGATIVE_PROMPT_PATTERN = r'<negative_prompt>(.*?)</negative_prompt>'

# Pattern for extracting video prompts from responses
VIDEO_PROMPT_PATTERN = r'<video_prompt>(.*?)</video_prompt>'

# Pattern for extracting titles from responses
TITLE_PROMPT_PATTERN = r'<title>(.*?)</title>'

# Alternative title patterns for fallback
TITLE_FALLBACK_PATTERNS = [
    r'Title:\s*(.+?)(?:\n|$)',
    r'"(.+?)"',
    r'(.+?)(?:\n|$)'
]