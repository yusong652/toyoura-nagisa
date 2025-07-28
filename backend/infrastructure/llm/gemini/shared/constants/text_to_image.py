"""
Text-to-image related constants for Gemini API operations.

This module contains constants specifically for text-to-image functionality,
including default prompts, regex patterns, and other text-to-image specific values.
"""

# 默认的负面提示词
DEFAULT_NEGATIVE_PROMPT = "blurry, low quality, distorted, extra limbs, bad anatomy, text, watermark, ugly"

# 文生图响应解析的正则表达式模式
TEXT_TO_IMAGE_PROMPT_PATTERN = r'<text_to_image_prompt>(.*?)</text_to_image_prompt>'
NEGATIVE_PROMPT_PATTERN = r'<negative_prompt>(.*?)</negative_prompt>'

# 文生图历史文件名
TEXT_TO_IMAGE_HISTORY_FILENAME = "text_to_image_history.json"

# 默认的few-shot学习配置
DEFAULT_FEW_SHOT_MAX_LENGTH = 9
DEFAULT_CONTEXT_MESSAGE_COUNT = 4
DEFAULT_MAX_HISTORY_LENGTH = 10

# 默认的系统提示词
DEFAULT_TEXT_TO_IMAGE_SYSTEM_PROMPT = (
    "You are a professional prompt engineer. Please generate a detailed and creative "
    "text-to-image prompt based on the following conversation. The prompt should be "
    "suitable for high-quality image generation."
)

# 对话文本引导提示词
CONVERSATION_TEXT_PROMPT_PREFIX = "Please generate text to image prompt based on the following conversation:\n\n"