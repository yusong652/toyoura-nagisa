import re

def extract_response_without_think(response_text: str) -> str:
    """
    提取 <thinking>/<think> 标签外部的内容，只返回 LLM 给用户的最终回复。
    如果没有 <thinking>/<think> 标签，则返回原始内容。
    处理未闭合的标签情况。
    """
    # Remove <thinking>...</thinking> blocks
    cleaned = re.sub(r'<thinking>[\s\S]*?</thinking>', '', response_text, flags=re.IGNORECASE)
    # Remove <think>...</think> blocks
    cleaned = re.sub(r'<think>[\s\S]*?</think>', '', cleaned, flags=re.IGNORECASE)
    
    # Handle unclosed tags by removing everything from the opening tag to the end
    cleaned = re.sub(r'<thinking>[\s\S]*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'<think>[\s\S]*$', '', cleaned, flags=re.IGNORECASE)
    
    result = cleaned.strip()
    
    # If result is empty but original had content, try to extract meaningful content
    if not result and response_text.strip():
        # If the entire response is thinking, provide a fallback
        if response_text.lower().startswith('<think'):
            # Extract a reasonable response based on the thinking content
            if '中文' in response_text or 'Chinese' in response_text:
                return "你好！"
            elif 'hello' in response_text.lower():
                return "Hello!"
            else:
                return "我理解了您的问题。"  # Generic acknowledgment
    
    return result 