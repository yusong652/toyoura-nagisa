"""
文本解析工具模块

提供LLM输出文本的解析功能，包括关键词提取和文本处理。
"""

import re
from typing import List, Tuple, Optional
from pathlib import Path


# 关键词缓存
_allowed_keywords_cache: Optional[List[str]] = None


def get_allowed_keywords_from_prompt_file() -> List[str]:
    """
    从 prompt 文件中解析允许的关键词列表。
    结果会被缓存。
    """
    global _allowed_keywords_cache
    if _allowed_keywords_cache is not None:
        return _allowed_keywords_cache

    # Use the new location in config/prompts
    project_root = Path(__file__).parent.parent.parent
    file_path = project_root / "config" / "prompts" / "expression_prompt.md"
    keywords = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        matches = re.findall(r'\\[\\[(\\w+)\\]\\]', content)
        if matches:
            keywords = [keyword.lower() for keyword in matches]
        else:
            print(f"警告: 在 {file_path} 中没有找到关键词。")
    except FileNotFoundError:
        print(f"错误: 关键词文件 '{file_path}' 未找到。")
    
    _allowed_keywords_cache = keywords
    return _allowed_keywords_cache


def parse_llm_output(llm_full_response: str) -> Tuple[str, str]:
    """
    解析 LLM 的输出，提取回复文本和关键词。
    Args:
        llm_full_response: LLM 的完整响应文本
    Returns:
        (response_text, keyword) 元组
    """
    allowed_keywords = get_allowed_keywords_from_prompt_file()
    
    keyword = "neutral"  # Default keyword
    response_text = llm_full_response.strip()

    match = re.search(r'\\[\\[(\\w+)\\]\\]\\s*$', llm_full_response.strip())
    if match:
        extracted_keyword = match.group(1).lower()
        if extracted_keyword in allowed_keywords:
            keyword = extracted_keyword
            response_text = llm_full_response[:match.start()].strip()
        else:
            print(f"警告: LLM 返回了未定义的关键词 '{extracted_keyword}'")
            response_text = llm_full_response[:match.start()].strip()

    return response_text, keyword


def clear_keywords_cache() -> None:
    """清除关键词缓存，强制重新读取文件"""
    global _allowed_keywords_cache
    _allowed_keywords_cache = None