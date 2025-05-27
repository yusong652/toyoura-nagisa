# 放在 backend/tts/utils.py (或者 backend/utils.py) 里

import re
import emoji # 需要 pip install emoji
from backend.config import get_tts_config

# 预编译一些可能用到的、比较安全的正则表达式
# 匹配括号及内部2-15个非括号字符 (尝试匹配简单颜文字如 (^_^) )
KAOMOJI_PATTERN_PARENS = re.compile(r'\([^()]{2,15}\)')
# 匹配我们之前定义的关键词标记 [[...]] (如果它可能残留的话)
KEYWORD_MARKER_PATTERN = re.compile(r'\[\[\w+\]\]\s*$')
# 匹配连续的空白字符
WHITESPACE_PATTERN = re.compile(r'\s+')

# 从配置文件获取默认值
TTS_CONFIG = get_tts_config()
DEFAULT_SPLIT_PUNCTUATIONS = TTS_CONFIG.get("split_punctuations", ['。', '！', '？', '!', '?', '.', '，', ',', '~', '、', '…', '—', '：', '；', '...', '..'])
DEFAULT_PUNCTUATION_LIMIT = int(TTS_CONFIG.get("split_size", 4))

# 新增：提取并替换emoji和kaomoji为占位符
KAOMOJI_PLACEHOLDER = "__KAOMOJI_{}__"
EMOJI_PLACEHOLDER = "__EMOJI_{}__"

# 1. 提取并替换
def extract_and_replace_emoticons(text: str):
    if not isinstance(text, str) or not text:
        return text, [], []
    text = KEYWORD_MARKER_PATTERN.sub('', text).strip()
    kaomoji_list = []
    emoji_list = []
    # 先替换kaomoji
    kaomoji_idx = [0]  # 用列表包裹以便在lambda中修改
    def _kaomoji_repl(match):
        idx = kaomoji_idx[0]
        kaomoji_list.append(match.group(0))
        kaomoji_idx[0] += 1
        return KAOMOJI_PLACEHOLDER.format(idx)
    text = KAOMOJI_PATTERN_PARENS.sub(_kaomoji_repl, text)
    # 再替换emoji
    emoji_idx = [0]
    def _emoji_repl(char):
        idx = emoji_idx[0]
        emoji_list.append(char)
        emoji_idx[0] += 1
        return EMOJI_PLACEHOLDER.format(idx)
    text = emoji.replace_emoji(text, replace=_emoji_repl)
    return text, kaomoji_list, emoji_list

# 2. 还原占位符
def restore_emoticons(text: str, kaomoji_list, emoji_list):
    text = re.sub(r'__KAOMOJI_(\d+)__', lambda m: kaomoji_list[int(m.group(1))] if int(m.group(1)) < len(kaomoji_list) else '', text)
    text = re.sub(r'__EMOJI_(\d+)__', lambda m: emoji_list[int(m.group(1))] if int(m.group(1)) < len(emoji_list) else '', text)
    return text

# 3. 清理TTS文本（去除所有占位符和多余空白）
def clean_text_for_tts(text: str) -> str:
    if not isinstance(text, str) or not text:
        return text
    # 新增：去除占位符
    text = re.sub(r'__KAOMOJI_\d+__', '', text)
    text = re.sub(r'__EMOJI_\d+__', '', text)
    text = WHITESPACE_PATTERN.sub(' ', text)
    return text.strip()

# 4. 分句（不变）
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