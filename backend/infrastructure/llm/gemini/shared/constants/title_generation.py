"""
Title generation related constants for Gemini API operations.

This module contains constants specifically for conversation title generation,
including default system prompts, temperature settings, and other title generation specific values.
"""

# 默认的标题生成系统提示词
DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT = (
    "You are a professional conversation title generator. Based on the provided conversation content, "
    "generate a concise title (5-15 words). The title should accurately summarize the main topic or intent "
    "of the conversation. You must place the title within <title></title> tags, and output nothing else "
    "except these tags and the title itself."
)

# 默认的标题生成温度设置
DEFAULT_TITLE_GENERATION_TEMPERATURE = 2.0

# 标题长度限制
DEFAULT_TITLE_MAX_LENGTH = 30

# 标题生成请求提示词
TITLE_GENERATION_REQUEST_TEXT = "Please generate a title for the above conversation"