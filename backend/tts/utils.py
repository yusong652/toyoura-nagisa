# 放在 backend/tts/utils.py (或者 backend/utils.py) 里

import re
import emoji # 需要 pip install emoji

# 预编译一些可能用到的、比较安全的正则表达式
# 匹配括号及内部2-15个非括号字符 (尝试匹配简单颜文字如 (^_^) )
KAOMOJI_PATTERN_PARENS = re.compile(r'\([^\(\)]{2,15}\)')
# 匹配我们之前定义的关键词标记 [[...]] (如果它可能残留的话)
KEYWORD_MARKER_PATTERN = re.compile(r'\[\[\w+\]\]\s*$')
# 匹配连续的空白字符
WHITESPACE_PATTERN = re.compile(r'\s+')

def clean_text_for_tts(text: str) -> str:
    """
    更精确地清理文本，用于TTS，主要移除Emoji和部分简单颜文字。
    保留 CJK 字符和大部分标点。
    """
    if not isinstance(text, str) or not text:
        return text

    print(f"原始 TTS 文本: '{text}'")
    cleaned_text = text

    # 1. 移除可能残留的关键词标记 (如果在末尾)
    cleaned_text = KEYWORD_MARKER_PATTERN.sub('', cleaned_text).strip()

    # 2. 使用 emoji 库移除 Emoji
    # replace_emoji 会将 emoji 替换为空字符串
    cleaned_text = emoji.replace_emoji(cleaned_text, replace='')

    # 3. 移除括号式简单颜文字 (可以根据需要添加更多精确的 kaomoji pattern)
    cleaned_text = KAOMOJI_PATTERN_PARENS.sub('', cleaned_text)

    # --- 在这里可以谨慎地添加更多针对特定颜文字的 re.sub() ---
    # 例如，非常确定要移除的特定符号组合，但要非常小心
    # cleaned_text = re.sub(r'特定的复杂模式', '', cleaned_text)

    # 4. 将可能产生的多个连续空白替换为单个空格
    cleaned_text = WHITESPACE_PATTERN.sub(' ', cleaned_text)

    # 5. 最后再清理一次首尾空白
    cleaned_text = cleaned_text.strip()

    print(f"清理后 TTS 文本 (修订版): '{cleaned_text}'")
    return cleaned_text

# --- 在 /api/tts 处理函数中调用 ---
# text_from_frontend = ...
# cleaned_text = clean_text_for_tts_revised(text_from_frontend)
# call_actual_tts_engine(cleaned_text)