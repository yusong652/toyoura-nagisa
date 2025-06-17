import re

def extract_response_without_think(response_text: str) -> str:
    """
    提取 <thinking> 标签外部的内容，只返回 LLM 给用户的最终回复。
    如果没有 <thinking> 标签，则返回原始内容。
    """
    return re.sub(r'<thinking>[\s\S]*?</thinking>', '', response_text, flags=re.IGNORECASE).strip() 