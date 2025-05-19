from typing import Optional, List
from backend.chat.base import LLMClientBase
from backend.chat.models import Message
from datetime import datetime
import re
import traceback

async def generate_conversation_title(
    first_user_message_text: str,
    first_assistant_message_text: str,
    llm_client: LLMClientBase
) -> Optional[str]:
    """
    根据对话的第一轮消息生成一个简洁的对话标题。
    
    Args:
        first_user_message_text: 用户的第一条消息内容
        first_assistant_message_text: AI助手对第一条消息的回复内容
        llm_client: LLM客户端实例
        
    Returns:
        生成的对话标题，如果生成失败则返回None
    """
    try:
        # 安全检查
        if not first_user_message_text or not first_assistant_message_text:
            return None

        # 限制输入长度以防止过长的提示
        max_length = 500
        if len(first_user_message_text) > max_length:
            first_user_message_text = first_user_message_text[:max_length] + "..."
        
        if len(first_assistant_message_text) > max_length:
            first_assistant_message_text = first_assistant_message_text[:max_length] + "..."
        
        # 创建系统消息
        system_message = Message(
            role="system",
            content="你是一个专业的对话标题生成助手。请根据提供的对话内容，生成一个简洁的标题（5-15个字）。标题应准确概括对话的主要主题或意图。你必须将标题放在<title></title>标签中，并且除了这些标签和标题本身外，不要输出任何其他内容。"
        )
        
        # 构造用于生成标题的消息列表
        prompt_message = Message(
            role="user",
            content=f"""以下是用户和AI助手之间的对话开始部分，请为这个对话生成一个简洁的标题：

用户：{first_user_message_text}

助手：{first_assistant_message_text}

请生成一个5-15个字的标题，并将标题放在<title></title>标签中。
你的回复应该只包含这对标签和标题内容，不要包含任何其他文字。

例如，回复应该是这样的格式：<title>这是一个标题示例</title>"""
        )
        
        # 准备消息列表
        messages = [system_message, prompt_message]
        
        # 调用LLM生成标题
        try:
            title_response_text, _ = await llm_client.get_response(messages)
        except Exception:
            return None
        
        # 从回复中提取标题（使用正则表达式提取<title>和</title>之间的内容）
        title_match = re.search(r'<title>(.*?)</title>', title_response_text, re.DOTALL)
        
        if title_match:
            # 提取并清理标题
            title = title_match.group(1).strip()
            
            # 确保标题长度合理
            if not title:
                return None
                
            if len(title) > 30:
                title = title[:30]
                
            return title
        else:
            # 如果没有找到标签，尝试直接使用整个回复作为标题（备选方案）
            cleaned_title = title_response_text.strip().strip('"\'').strip()
            # 确保标题不超过合理长度
            if cleaned_title and len(cleaned_title) <= 30:
                return cleaned_title
            return None
    
    except Exception:
        return None 