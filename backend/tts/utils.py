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

# 默认的分割尺寸
DEFAULT_SPLIT_SIZE = 4
# 默认的分割句读点
DEFAULT_SPLIT_PUNCTUATIONS = ['，', '。', ',', '~', '～', '*', '！', '？', '、', '!', '?', '…', '—', '：', '；', '...', '..'] # もっと色々追加してもOK！

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

def split_text_by_punctuations(text: str, group_size: int = DEFAULT_SPLIT_SIZE, punctuations: list[str] = DEFAULT_SPLIT_PUNCTUATIONS) -> list[str]:
    """
    テキストを指定された句読点の出現回数に基づいて分割する関数。

    Args:
        text: 分割対象のテキスト。
        group_size: 何個の句読点が出現したら区切るかのサイズ。
        punctuations: 区切り文字として認識する句読点のリスト (例: ['，', '。', ',', '~'])。
    Returns:
        分割されたテキストのリスト。
    """
    if not text or not punctuations or group_size <= 0:
        return [text] if text else []

    # 句読点を正規表現で扱えるようにエスケープし、OR条件で結合する
    # 例: '，|。|,'
    punctuation_pattern = '|'.join(re.escape(p) for p in punctuations)
    
    # 正規表現で、句読点を含む区切り位置を見つける
    # (句読点の直後までを一つの区切りと見なす)
    # (.*? (?:句読点パターン|$)) を group_size 回繰り返す感じのイメージだけど、
    # もう少し賢くやる必要があるね。

    segments = []
    current_segment = ""
    punctuation_count = 0
    
    # 一文字ずつ見ていく方法（もっと効率的な方法もあるかも！）
    temp_buffer = "" # 句読点までを一時的に保持するバッファ
    for char in text:
        temp_buffer += char
        if char in punctuations:
            punctuation_count += 1
        
        if punctuation_count >= group_size:
            # group_size 個の句読点が見つかったら、そこまでをセグメントとする
            segments.append(temp_buffer.strip())
            temp_buffer = ""
            punctuation_count = 0
        elif char in punctuations and punctuation_count < group_size:
            # 句読点だけどまだgroup_sizeに達していない場合、
            # ここで区切るか、次の句読点まで続けるか、仕様によるね！
            # 今回の「3つ出てくるたびに区切る」だと、このままでOKかな。
            pass # 次の文字へ

    # 最後の残りの部分を追加
    if temp_buffer.strip():
        segments.append(temp_buffer.strip())
    
    # もし空のセグメントができてしまったら除去する (例: 連続する句読点の場合など)
    return [s for s in segments if s]