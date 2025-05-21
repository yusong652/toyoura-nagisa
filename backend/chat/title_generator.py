from typing import Optional, List
from backend.chat.base import LLMClientBase
from backend.chat.models import Message
import traceback

async def generate_conversation_title(
    first_user_message_text: str,
    first_assistant_message_text: str,
    llm_client: LLMClientBase,
    title_specific_system_prompt: Optional[str] = "你是一个专业的对话标题生成助手。请根据提供的对话内容，生成一个简洁的标题（5-15个字）。标题应准确概括对话的主要主题或意图。你必须将标题放在<title></title>标签中，并且除了这些标签和标题本身外，不要输出任何其他内容。"
) -> Optional[str]:
    """
    根据对话的第一轮消息生成一个简洁的对话标题。
    
    Args:
        first_user_message_text: 用户的第一条消息内容
        first_assistant_message_text: AI助手对第一条消息的回复内容
        llm_client: LLM客户端实例
        title_specific_system_prompt: 用于生成标题的特定system prompt
        
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
        
        # 直接调用客户端的特定方法
        title = await llm_client.generate_title_from_messages(
            first_user_message_content=first_user_message_text,
            first_assistant_message_content=first_assistant_message_text,
            title_generation_system_prompt=title_specific_system_prompt
        )
        
        return title
    
    except Exception as e:
        print(f"生成对话标题时出错: {str(e)}")
        traceback.print_exc()
        return None 