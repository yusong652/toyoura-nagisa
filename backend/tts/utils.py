# 放在 backend/tts/utils.py (或者 backend/utils.py) 里

import re
import emoji # 需要 pip install emoji
from backend.config import get_tts_config

# 预编译一些可能用到的、比较安全的正则表达式
# 匹配括号及内部2-15个非括号字符 (尝试匹配简单颜文字如 (^_^) )
KAOMOJI_PATTERN_PARENS = re.compile(r'\([^\(\)]{2,15}\)')
# 匹配我们之前定义的关键词标记 [[...]] (如果它可能残留的话)
KEYWORD_MARKER_PATTERN = re.compile(r'\[\[\w+\]\]\s*$')
# 匹配连续的空白字符
WHITESPACE_PATTERN = re.compile(r'\s+')

# 从配置文件获取默认值
TTS_CONFIG = get_tts_config()
DEFAULT_SPLIT_PUNCTUATIONS = TTS_CONFIG.get("split_punctuations", ['。', '！', '？', '!', '?', '.', '，', ',', '~', '、', '…', '—', '：', '；', '...', '..'])
DEFAULT_PUNCTUATION_LIMIT = int(TTS_CONFIG.get("split_size", 4))

def clean_text_for_tts(text: str) -> str:
    """
    更精确地清理文本，用于TTS，主要移除Emoji和部分简单颜文字。
    保留 CJK 字符和大部分标点。
    """
    if not isinstance(text, str) or not text:
        return text

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

    return cleaned_text

# --- 在 /api/tts 处理函数中调用 ---
# text_from_frontend = ...
# cleaned_text = clean_text_for_tts_revised(text_from_frontend)
# call_actual_tts_engine(cleaned_text)

def split_text_by_punctuations(text: str, punctuations: list[str] = None, punctuation_limit: int = None) -> list[str]:
    """
    根据标点符号将文本分割成多个段落。
    使用正则表达式实现，更高效且能处理更多边界情况。

    Args:
        text: 要分割的文本
        punctuations: 用作分割的标点符号列表，默认使用配置文件中的值
        punctuation_limit: 每多少个标点符号分割一次，默认使用配置文件中的值

    Returns:
        分割后的文本列表
    """
    # 使用配置文件中的默认值
    if punctuations is None:
        punctuations = DEFAULT_SPLIT_PUNCTUATIONS
    if punctuation_limit is None:
        punctuation_limit = DEFAULT_PUNCTUATION_LIMIT
        
    if not text or not punctuations or punctuation_limit <= 0:
        return [text] if text else []

    # 构建标点符号的正则表达式模式
    punctuation_pattern = '|'.join(re.escape(p) for p in punctuations)
    
    # 使用正则表达式查找所有标点符号的位置
    matches = list(re.finditer(f'[{punctuation_pattern}]', text))
    
    if not matches:
        return [text]

    segments = []
    start_pos = 0
    
    # 每 punctuation_limit 个标点符号分割一次
    for i in range(0, len(matches), punctuation_limit):
        if i + punctuation_limit <= len(matches):
            # 获取当前分组的最后一个标点符号的位置
            end_pos = matches[i + punctuation_limit - 1].end()
        else:
            # 处理最后一组（不足 punctuation_limit 个标点的情况）
            end_pos = matches[-1].end()
        
        # 提取当前段落并清理空白
        segment = text[start_pos:end_pos].strip()
        if segment:
            segments.append(segment)
        
        start_pos = end_pos
    
    # 处理最后剩余的文本
    if start_pos < len(text):
        remaining = text[start_pos:].strip()
        if remaining:
            segments.append(remaining)
    
    return segments