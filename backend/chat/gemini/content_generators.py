"""
Content generation utilities for Gemini API.

Specialized generators for creating titles, image prompts, and other derived content
based on conversation context. Separates content generation concerns from the main client.
"""

import re
import os
import json
from datetime import datetime
from typing import Optional, Dict, List, Any
from google.genai import types
from backend.chat.models import BaseMessage, UserMessage, AssistantMessage
from .message_formatter import MessageFormatter
from backend.config import get_text_to_image_config, get_llm_specific_config
from backend.chat.utils import get_latest_n_messages


def _get_text_to_image_history_file(session_id: str) -> str:
    """Get the path to the text-to-image history file for a session."""
    from backend.chat.utils import HISTORY_BASE_DIR
    session_dir = os.path.join(HISTORY_BASE_DIR, session_id)
    return os.path.join(session_dir, "text_to_image_history.json")


def load_text_to_image_history(session_id: str) -> List[Dict[str, Any]]:
    """
    Load text-to-image prompt generation history for a session.
    
    Args:
        session_id: Session ID to load history for
        
    Returns:
        List of previous prompt generation records, each containing:
        - user_message: The original request
        - assistant_message: The generated prompt response
        - timestamp: When the generation occurred
    """
    history_file = _get_text_to_image_history_file(session_id)
    
    if not os.path.exists(history_file):
        return []
    
    try:
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
            return history
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[WARNING] Failed to load text-to-image history for session {session_id}: {e}")
        return []


def save_text_to_image_generation(
    session_id: str, 
    user_request: str, 
    assistant_response: str,
    max_history_length: int = 10
) -> None:
    """
    Save a text-to-image prompt generation record to history.
    
    Args:
        session_id: Session ID to save to
        user_request: The original user request text
        assistant_response: Complete assistant response content
        max_history_length: Maximum number of records to keep (default: 10)
    """
    history_file = _get_text_to_image_history_file(session_id)
    
    # Ensure session directory exists
    session_dir = os.path.dirname(history_file)
    os.makedirs(session_dir, exist_ok=True)
    
    # Load existing history
    history = load_text_to_image_history(session_id)
    
    # Create new record
    new_record = {
        "user_message": {
            "role": "user",
            "content": user_request
        },
        "assistant_message": {
            "role": "assistant", 
            "content": assistant_response  # 保存完整的assistant response，不做格式化
        },
        "timestamp": datetime.now().isoformat()
    }
    
    # Add new record and maintain history length
    history.append(new_record)
    if len(history) > max_history_length:
        history = history[-max_history_length:]  # Keep only the latest records
    
    # Save updated history
    try:
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ERROR] Failed to save text-to-image history for session {session_id}: {e}")


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
            
            # Get model from configuration
            gemini_config = get_llm_specific_config("gemini")
            model = gemini_config.get("model", "gemini-2.5-flash")
            
            response = client.models.generate_content(
                model=model,
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


class WebSearchGenerator:
    """
    Handles web search using Gemini API with google_search tool.
    
    Performs web searches using Google Search via the Gemini API using the
    modern google_search tool. Returns structured results with proper error
    handling and debugging support.
    """

    @staticmethod
    def perform_web_search(
        client,  # Gemini client instance
        query: str,
        debug: bool = False,
        max_uses: int = 5
    ) -> Dict[str, Any]:
        """
        Perform a web search using Google Search via the Gemini API.
        
        Uses the modern google_search tool. The model will automatically
        decide whether to perform a search based on the query requirements.
        
        Args:
            client: Gemini client instance for API calls
            query: The search query to find information on the web
            debug: Enable debug output
            
        Returns:
            Dictionary containing search results or error information
        """
        try:
            if debug:
                print(f"[WebSearch] Performing search for query: {query}")
            
            # Configure the Gemini model with the web search tool
            # Use google_search tool as per 2025 API requirements
            web_search_system_prompt = (
                "You are a professional web search assistant. Your task is to search for and synthesize "
                "information from the web to provide comprehensive, accurate, and up-to-date answers. "
                "When searching:\n"
                "1. Use the search tool to find relevant and current information\n"
                "2. Analyze multiple sources for accuracy and reliability\n"
                "3. Synthesize information into a coherent, well-structured response\n"
                "4. Prioritize recent and authoritative sources\n"
                "5. Clearly indicate when information is uncertain or requires verification\n"
                "6. Provide context and explain complex topics clearly\n"
                "Focus on delivering factual, helpful information that directly addresses the user's query."
            )
            
            # Note: Gemini's google_search tool doesn't support max_uses parameter
            # The max_uses parameter is accepted for API compatibility but ignored
            search_config = types.GenerateContentConfig(
                system_instruction=web_search_system_prompt,
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.1,
                max_output_tokens=4096
            )
            
            if debug and max_uses != 5:
                print(f"[WebSearch] Note: max_uses={max_uses} parameter ignored for Gemini (API limitation)")
            
            # Create user message with search query
            user_message = UserMessage(role="user", content=query)
            
            # Format message using MessageFormatter
            contents = MessageFormatter.format_messages_for_gemini([user_message])
            
            if debug:
                print(f"[WebSearch] Formatted contents for API call:")
                import pprint
                pprint.pprint(contents)
            
            # Get model from configuration
            gemini_config = get_llm_specific_config("gemini")
            model = gemini_config.get("model", "gemini-2.5-flash")
            
            # Call the model with the query
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=search_config
            )
            
            if debug:
                print(f"[WebSearch] Raw API response received")
                # Debug: Print response structure
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    print(f"[WebSearch] Candidate attributes: {dir(candidate)}")
                    if hasattr(candidate, 'grounding_metadata'):
                        print(f"[WebSearch] Grounding metadata found")
                        gm = candidate.grounding_metadata
                        print(f"[WebSearch] Grounding metadata attributes: {dir(gm)}")
                    else:
                        print(f"[WebSearch] No grounding_metadata found")
            
            # Check for tool calls
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                
                # Extract grounding metadata for sources
                grounding_metadata = getattr(candidate, 'grounding_metadata', None)
                sources = []
                if grounding_metadata:
                    grounding_chunks = getattr(grounding_metadata, 'grounding_chunks', [])
                    
                    # Process grounding chunks according to official API structure
                    for i, chunk in enumerate(grounding_chunks):
                        if hasattr(chunk, 'web'):
                            web_info = chunk.web
                            # Extract more comprehensive information
                            source_data = {
                                'url': getattr(web_info, 'uri', ''),
                                'title': getattr(web_info, 'title', ''),
                                'snippet': getattr(web_info, 'text', ''),
                                'index': i
                            }
                            
                            # Try to get additional metadata if available
                            if hasattr(web_info, 'snippet'):
                                source_data['snippet'] = web_info.snippet
                            
                            sources.append(source_data)
                            
                            if debug:
                                print(f"[WebSearch] Source {i+1}: {source_data['title']}")
                                print(f"[WebSearch]   URL: {source_data['url']}")
                                print(f"[WebSearch]   Snippet: {source_data['snippet'][:100]}...")
                                
                        elif hasattr(chunk, 'uri'):  # Fallback for older format
                            source_data = {
                                'url': chunk.uri,
                                'title': getattr(chunk, 'title', ''),
                                'snippet': getattr(chunk, 'text', ''),
                                'index': i
                            }
                            sources.append(source_data)
                            
                            if debug:
                                print(f"[WebSearch] Source {i+1} (fallback): {source_data['title']}")
                                
                # Also try to extract citation/grounding support information
                if grounding_metadata and hasattr(grounding_metadata, 'grounding_supports'):
                    grounding_supports = grounding_metadata.grounding_supports
                    if debug:
                        print(f"[WebSearch] Found {len(grounding_supports)} grounding supports")
                        for j, support in enumerate(grounding_supports):
                            if hasattr(support, 'grounding_chunk_indices'):
                                chunk_indices = support.grounding_chunk_indices
                                print(f"[WebSearch] Support {j+1} references chunks: {chunk_indices}")
                
                # Extract response text
                response_text = ""
                if hasattr(candidate, 'content') and candidate.content.parts:
                    response_text = candidate.content.parts[0].text
                
                # Build structured result
                result = {
                    "query": query,
                    "response_text": response_text,
                    "sources": sources,
                    "total_sources": len(sources)
                }
                
                if debug:
                    print(f"[WebSearch] Extracted {len(sources)} sources")
                    print(f"[WebSearch] Response text length: {len(response_text)}")
                
                return result
            else:
                if debug:
                    print("[WebSearch] No candidates found in response")
                return {"error": "No search results found", "query": query}
                
        except Exception as e:
            error_msg = f"An error occurred during web search: {str(e)}"
            if debug:
                print(f"[WebSearch] Error: {error_msg}")
            return {"error": error_msg, "query": query}


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
            
            # 加载历史few-shot示例
            few_shot_history = load_text_to_image_history(session_id) if session_id else []
            
            # 构造消息序列，包含few-shot学习
            messages = []
            
            # 添加few-shot示例（作为历史对话）
            for record in few_shot_history[-3:]:  # 使用最近的3个示例
                if debug:
                    print(f"[text_to_image] Adding few-shot example from {record.get('timestamp', 'unknown')}")
                
                # 直接添加用户消息和助手回复，保持原有的格式
                user_msg = UserMessage(role="user", content=record['user_message']['content'])
                messages.append(user_msg)
                
                assistant_msg = AssistantMessage(role="assistant", content=record['assistant_message']['content'])
                messages.append(assistant_msg)
            
            # 构造当前请求 - 注意：latest_messages是当前对话上下文，用于理解用户想要生成什么图像
            conversation_text = "Please generate text to image prompt based on the following conversation:\n\n"
            for msg in latest_messages:
                if msg is not None:
                    conversation_text += f"{msg.role}: {msg.content}\n"
            
            current_request = UserMessage(role="user", content=conversation_text)
            messages.append(current_request)
            
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
                temperature=1.6,
                max_output_tokens=4096
            )
            
            if debug:
                print("\n[Gemini][text_to_image] System prompt:")
                print(system_prompt)
                print("[Gemini][text_to_image] Prompt config:")
                pprint.pprint(prompt_config)
            
            response = client.models.generate_content(
                model=config.get("model_for_text_to_image", "gemini-1.5-pro"),
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
                
                # 保存成功的生成记录到历史中，用于future few-shot学习
                final_prompts = {
                    "text_prompt": text_prompt,
                    "negative_prompt": negative_prompt
                }
                
                if session_id:
                    try:
                        save_text_to_image_generation(session_id, conversation_text, prompt_text)
                        if debug:
                            print(f"[text_to_image] Saved generation to history for session {session_id}")
                    except Exception as e:
                        if debug:
                            print(f"[text_to_image] Warning: Failed to save generation to history: {e}")
                        # 不阻止返回结果，只是记录错误
                
                return final_prompts
            return None
            
        except Exception as e:
            if debug:
                print(f"[text_to_image] Error during prompt generation: {str(e)}")
            return None 