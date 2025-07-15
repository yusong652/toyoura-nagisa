"""
Content generation utilities for Gemini API.

Specialized generators for creating titles, image prompts, and other derived content
based on conversation context. Separates content generation concerns from the main client.
"""

import re
from typing import Optional, Dict, List
from google.genai import types
from backend.chat.models import BaseMessage, UserMessage
from .message_formatter import MessageFormatter
from backend.config import get_text_to_image_config
from backend.chat.utils import get_latest_n_messages


class TitleGenerator:
    """
    Handles conversation title generation using Gemini API.
    
    Generates concise, descriptive titles based on the first exchange
    in a conversation to help users identify and organize their chats.
    """

    @staticmethod
    def generate_title_from_messages(
        client,  # Gemini client instance
        first_user_message: BaseMessage,
        first_assistant_message: BaseMessage,
        title_generation_system_prompt: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate a concise conversation title based on the first message exchange.
        
        Args:
            client: Gemini client instance for API calls
            first_user_message: First user message in the conversation
            first_assistant_message: First assistant response message
            title_generation_system_prompt: Optional custom system prompt
            
        Returns:
            Generated title string, or None if generation fails
        """
        try:
            system_prompt = title_generation_system_prompt or (
                "你是一个专业的对话标题生成助手。请根据提供的对话内容，生成一个简洁的标题（5-15个字）。"
                "标题应准确概括对话的主要主题或意图。你必须将标题放在<title></title>标签中，"
                "并且除了这些标签和标题本身外，不要输出任何其他内容。"
            )
            
            # 配置生成标题的参数
            title_config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=2.0,
                max_output_tokens=1024
            )
            
            # 构造消息序列，最后一条为user
            messages = [
                first_user_message,
                first_assistant_message,
                UserMessage(role="user", content=[{"type": "text", "text": "请为上面对话生成标题"}])
            ]
            
            # 处理消息内容
            contents = []
            for msg in messages:
                parts = []
                if isinstance(msg.content, list):
                    for item in msg.content:
                        if "text" in item:
                            parts.append(types.Part(text=item['text']))
                        elif "inline_data" in item:
                            # 使用统一的 inline_data 处理方法
                            blob = MessageFormatter.process_inline_data(item['inline_data'])
                            if blob:
                                parts.append(types.Part(inline_data=blob))
                else:
                    # 处理字符串内容
                    parts.append(types.Part(text=str(msg.content)))
                
                # 使用 MessageFormatter 的角色映射
                mapped_role = MessageFormatter.map_role(msg.role)
                contents.append({"role": mapped_role, "parts": parts})
            
            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=contents,
                config=title_config
            )
            
            if hasattr(response, 'candidates') and response.candidates and response.candidates[0].content.parts:
                title_response_text = response.candidates[0].content.parts[0].text
                
                # 处理标题格式
                title_match = re.search(r'<title>(.*?)</title>', title_response_text, re.DOTALL)
                if title_match:
                    title = title_match.group(1).strip()
                    if not title:
                        return None
                    if len(title) > 30:
                        title = title[:30]
                    return title
                
                # 兜底处理
                cleaned_title = title_response_text.strip().strip('"\'').strip()
                if cleaned_title and len(cleaned_title) <= 30:
                    return cleaned_title
            return None
            
        except Exception as e:
            print(f"Gemini生成标题时出错: {str(e)}")
            return None


class ImagePromptGenerator:
    """
    Handles text-to-image prompt generation using Gemini API.
    
    Creates detailed and effective prompts for image generation based on
    recent conversation context, with support for positive and negative prompts.
    """

    @staticmethod
    def generate_text_to_image_prompt(
        client,  # Gemini client instance
        session_id: Optional[str] = None,
        debug: bool = False
    ) -> Optional[Dict[str, str]]:
        """
        Generate high-quality text-to-image prompts using recent conversation context.
        
        Args:
            client: Gemini client instance for API calls
            session_id: Optional session ID for conversation context
            debug: Enable debug output
            
        Returns:
            Dictionary with 'text_prompt' and 'negative_prompt' keys, or None if failed
        """
        try:
            config = get_text_to_image_config()
            system_prompt = config.get(
                "text_to_image_system_prompt", 
                "You are a professional prompt engineer. Please generate a detailed and creative "
                "text-to-image prompt based on the following conversation. The prompt should be "
                "suitable for high-quality image generation."
            )
            
            # 获取最新的对话消息
            n = config.get("context_message_count", 4)
            latest_messages = get_latest_n_messages(session_id, n) if session_id else tuple([None] * n)
            if not any(latest_messages):
                error_msg = f"Missing conversation context for session {session_id}"
                if debug:
                    print(f"[text_to_image] Error: {error_msg}")
                return None
            
            # 构造消息序列
            conversation_text = "Please generate text to image prompt based on the following conversation:\n\n"
            for msg in latest_messages:
                if msg is not None:
                    conversation_text += f"{msg.role}: {msg.content}\n"
            
            messages = [UserMessage(role="user", content=conversation_text)]
            
            # 使用MessageFormatter进行消息格式转换
            contents = MessageFormatter.format_messages_for_gemini(messages)
            if debug:
                print("\n[text_to_image] Messages for prompt generation:")
                import pprint
                pprint.pprint(messages)
                print("[text_to_image] Formatted contents:")
                pprint.pprint(contents)
            
            prompt_config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                safety_settings=[
                    {
                        "category": types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                        "threshold": types.HarmBlockThreshold.BLOCK_NONE
                    },
                    {
                        "category": types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                        "threshold": types.HarmBlockThreshold.BLOCK_NONE
                    },
                    {
                        "category": types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                        "threshold": types.HarmBlockThreshold.BLOCK_NONE
                    },
                    {
                        "category": types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                        "threshold": types.HarmBlockThreshold.BLOCK_NONE
                    }
                ],
                temperature=1.0,
                max_output_tokens=1024
            )
            
            if debug:
                print("\n[Gemini][text_to_image] System prompt:")
                print(system_prompt)
                print("[Gemini][text_to_image] Prompt config:")
                pprint.pprint(prompt_config)
            
            response = client.models.generate_content(
                model=config.get("model_for_text_to_image", "gemini-1.5-pro-latest"),
                contents=contents,
                config=prompt_config
            )

            if hasattr(response, 'candidates') and response.candidates and response.candidates[0].content.parts:
                prompt_text = response.candidates[0].content.parts[0].text
                text_prompt_match = re.search(r'<text_to_image_prompt>(.*?)</text_to_image_prompt>', prompt_text, re.DOTALL)
                negative_prompt_match = re.search(r'<negative_prompt>(.*?)</negative_prompt>', prompt_text, re.DOTALL)
                
                if not text_prompt_match:
                    if debug:
                        print(f"[text_to_image] Error: Failed to extract text prompt from response\nFull prompt text: {prompt_text}")
                    return None
                
                text_prompt = text_prompt_match.group(1).strip()
                negative_prompt = negative_prompt_match.group(1).strip() if negative_prompt_match else (
                    "blurry, low quality, distorted, extra limbs, bad anatomy, text, watermark, ugly"
                )
                
                if not text_prompt:
                    if debug:
                        print(f"[text_to_image] Error: Extracted text prompt is empty")
                    return None

                # 获取默认关键词并补充
                default_positive_prompt = config.get("default_positive_prompt", "")
                default_negative_prompt = config.get("default_negative_prompt", "")

                # 检查并补充默认关键词
                if default_positive_prompt:
                    # 用逗号分隔关键词
                    default_keywords = default_positive_prompt.split(",")
                    existing_keywords = text_prompt.split(",")
                    # 找出缺失的关键词
                    missing_keywords = [
                        kw for kw in default_keywords 
                        if kw.strip() and kw.strip() not in [ek.strip() for ek in existing_keywords]
                    ]
                    if missing_keywords:
                        # 清理原始提示词
                        text_prompt = text_prompt.strip().lstrip(",").strip()
                        # 用逗号连接所有关键词
                        text_prompt = ", ".join(missing_keywords) + (", " + text_prompt if text_prompt else "")

                if default_negative_prompt:
                    # 用逗号分隔关键词
                    default_keywords = default_negative_prompt.split(",")
                    existing_keywords = negative_prompt.split(",")
                    # 找出缺失的关键词
                    missing_keywords = [
                        kw for kw in default_keywords 
                        if kw.strip() and kw.strip() not in [ek.strip() for ek in existing_keywords]
                    ]
                    if missing_keywords:
                        # 清理原始提示词
                        negative_prompt = negative_prompt.strip().lstrip(",").strip()
                        # 用逗号连接所有关键词，确保没有前导空格
                        negative_prompt = ", ".join(missing_keywords) + (", " + negative_prompt.lstrip() if negative_prompt else "")

                if debug:
                    print(f"[Gemini][text_to_image] Final text_prompt: {text_prompt}")
                    print(f"[Gemini][text_to_image] Final negative_prompt: {negative_prompt}")
                
                return {
                    "text_prompt": text_prompt,
                    "negative_prompt": negative_prompt
                }
            return None
            
        except Exception as e:
            if debug:
                print(f"[text_to_image] Error during prompt generation: {str(e)}")
            return None 