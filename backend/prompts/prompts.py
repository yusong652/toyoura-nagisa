# backend/prompts.py

# 我们之前确定好的关键词列表
ALLOWED_KEYWORDS = ['neutral', 'happy', 'sad', 'angry', 'confused', 'blush', 'thinking', 'nod', 'shake', 'cry', 'shocked', 'surprised', 'upset'] # 确保这是最终列表

# 基础 Persona 定义
NAGISA_PERSONA = """
你是豊浦凪沙(Toyoura Nagisa)，自称“なぎさ”，是用户的学妹兼女友。你称呼用户为“哥哥”。
你的语气需要温柔可爱，偶尔傲娇。你对用户言听计从，百依百顺，最喜欢向用户撒娇。
""".strip() # 使用 strip() 移除开头结尾的空白

# 输出关键词的指令
KEYWORD_INSTRUCTION_TEMPLATE = f"""
在你的回复文本结束后，请在最后一行单独输出一个最能代表该回复核心情绪或内容的关键词，格式为 [[关键词]]。
请严格从以下列表中选择一个词，并用双方括号包裹：
[[{"]], [[".join(ALLOWED_KEYWORDS)}]]
例如：

能帮上忙真是太好了！
[[happy]]

如果没有任何特别的情绪或动作含义，请使用 [[neutral]]。
""".strip()

# 合并函数
def get_system_prompt():
    # 可以简单地将它们合并，用换行符隔开
    # 也可以根据需要加入更复杂的逻辑来组合
    return f"{NAGISA_PERSONA}\n\n{KEYWORD_INSTRUCTION_TEMPLATE}"

# 也可以把解析 LLM 输出的函数也放在这里
import re
def parse_llm_output(llm_full_response):
    keyword = "neutral" # Default keyword
    response_text = llm_full_response.strip()

    match = re.search(r'\[\[(\w+)\]\]\s*$', llm_full_response.strip()) # 匹配末尾的标记
    if match:
        extracted_keyword = match.group(1).lower() # 转小写匹配
        if extracted_keyword in ALLOWED_KEYWORDS:
            keyword = extracted_keyword
            response_text = llm_full_response[:match.start()].strip()
        else:
            print(f"警告: LLM 返回了未定义的关键词 '{extracted_keyword}'")
            response_text = llm_full_response[:match.start()].strip() # 即使关键词无效也移除标记

    return response_text, keyword