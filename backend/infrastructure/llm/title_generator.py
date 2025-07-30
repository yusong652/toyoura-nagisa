from typing import Optional
from backend.infrastructure.llm.base.client import LLMClientBase
from backend.domain.models.messages import BaseMessage
import traceback

def multimodal_to_prompt(content):
    prompt = ""
    if isinstance(content, str):
        prompt += content
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                if "text" in item:
                    prompt += item["text"]
                elif "inline_data" in item:
                    prompt += "[图片]"
            elif isinstance(item, str):
                prompt += item
    return prompt

async def generate_conversation_title(
    user_message: BaseMessage,
    assistant_message: BaseMessage,
    llm_client: LLMClientBase,
    title_specific_system_prompt: Optional[str] = "你是一个专业的对话标题生成助手。请根据提供的对话内容，生成一个简洁的标题（5-15个字）。标题应准确概括对话的主要主题或意图。你必须将标题放在<title></title>标签中，并且除了这些标签和标题本身外，不要输出任何其他内容。"
) -> Optional[str]:
    """
    根据对话的第一轮消息（支持多模态）生成一个简洁的对话标题。
    Args:
        user_message: 用户的第一条消息（Message对象，支持多模态）
        assistant_message: AI助手的第一条回复（Message对象，支持多模态）
        llm_client: LLM客户端实例
        title_specific_system_prompt: 用于生成标题的特定system prompt
    Returns:
        生成的对话标题，如果生成失败则返回None
    """
    try:
        if not user_message or not assistant_message:
            return None
            
        # 直接传递 Message 对象给 LLM 客户端
        title = await llm_client.generate_title_from_messages(
            first_user_message=user_message,
            first_assistant_message=assistant_message,
            title_generation_system_prompt=title_specific_system_prompt
        )
        return title
    except Exception as e:
        print(f"生成对话标题时出错: {str(e)}")
        traceback.print_exc()
        return None 