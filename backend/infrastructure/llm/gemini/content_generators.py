"""
Content generation utilities for Gemini API.

Specialized generators for creating titles, image prompts, and other derived content
based on conversation context. Separates content generation concerns from the main client.
"""

from typing import Optional, Dict, Any
from google.genai import types
from backend.domain.models.messages import BaseMessage, UserMessage, AssistantMessage
from .message_formatter import MessageFormatter
from .debug import GeminiDebugger
from .response_processor import ResponseProcessor
from backend.config import get_text_to_image_settings, get_llm_settings
from backend.infrastructure.storage.session_manager import get_latest_n_messages
from .config import get_gemini_client_config
from .shared.utils import (
    load_text_to_image_history,
    save_text_to_image_generation,
    extract_text_content,
    parse_text_to_image_response,
    enhance_prompts_with_defaults,
    parse_title_response
)
from .shared.constants.text_to_image import (
    DEFAULT_NEGATIVE_PROMPT,
    DEFAULT_FEW_SHOT_MAX_LENGTH,
    DEFAULT_CONTEXT_MESSAGE_COUNT,
    DEFAULT_TEXT_TO_IMAGE_SYSTEM_PROMPT,
    CONVERSATION_TEXT_PROMPT_PREFIX
)
from .shared.constants.web_search import (
    DEFAULT_WEB_SEARCH_SYSTEM_PROMPT,
    DEFAULT_WEB_SEARCH_TEMPERATURE
)
from .shared.constants.title_generation import (
    DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT,
    DEFAULT_TITLE_GENERATION_TEMPERATURE,
    DEFAULT_TITLE_MAX_LENGTH,
    TITLE_GENERATION_REQUEST_TEXT
)


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
            # 读取Gemini配置
            gemini_config = get_gemini_client_config()
            
            system_prompt = title_generation_system_prompt or DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT
            
            # 配置生成标题的参数
            title_config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=DEFAULT_TITLE_GENERATION_TEMPERATURE,
                max_output_tokens=gemini_config.model_settings.max_output_tokens
            )
            
            # 构造消息序列，最后一条为user
            messages = [
                first_user_message,
                first_assistant_message,
                UserMessage(role="user", content=[{"type": "text", "text": TITLE_GENERATION_REQUEST_TEXT}])
            ]
            
            # 使用MessageFormatter进行统一的消息格式转换
            contents = MessageFormatter.format_messages_for_gemini(messages)
            
            # Get model from configuration
            llm_settings = get_llm_settings()
            gemini_config = llm_settings.get_gemini_config()
            model = gemini_config.model
            
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=title_config
            )
            
            # Extract response text using ResponseProcessor
            title_response_text = ResponseProcessor.extract_text_content(response)
            
            # Parse title using utility function
            return parse_title_response(title_response_text, max_length=DEFAULT_TITLE_MAX_LENGTH)
            
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
            
            # 读取Gemini配置
            gemini_config = get_gemini_client_config()
            
            # Configure the Gemini model with the web search tool
            # Use google_search tool as per 2025 API requirements
            web_search_system_prompt = DEFAULT_WEB_SEARCH_SYSTEM_PROMPT
            
            # Note: Gemini's google_search tool doesn't support max_uses parameter
            # The max_uses parameter is accepted for API compatibility but ignored
            search_config = types.GenerateContentConfig(
                system_instruction=web_search_system_prompt,
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=DEFAULT_WEB_SEARCH_TEMPERATURE,
                max_output_tokens=gemini_config.model_settings.max_output_tokens
            )
            
            # Create user message with search query
            user_message = UserMessage(role="user", content=query)
            
            # Format message using MessageFormatter
            contents = MessageFormatter.format_messages_for_gemini([user_message])
            
            if debug:
                GeminiDebugger.print_debug_request(contents, search_config)
                print(f"[WebSearch] Note: max_uses={max_uses} parameter ignored for Gemini (API limitation)")
            
            # Get model from configuration
            llm_settings = get_llm_settings()
            gemini_config = llm_settings.get_gemini_config()
            model = gemini_config.model
            
            # Call the model with the query
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=search_config
            )
            
            if debug:
                GeminiDebugger.print_debug_response(response)
            
            # Check for tool calls
            if hasattr(response, 'candidates') and response.candidates:
                # Extract sources using ResponseProcessor
                sources = ResponseProcessor.extract_web_search_sources(response, debug=debug)
                
                # Extract response text using ResponseProcessor
                response_text = ResponseProcessor.extract_text_content(response)
                
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
            # 读取所有配置
            text_to_image_settings = get_text_to_image_settings()
            gemini_config = get_gemini_client_config()
            
            # 提取配置参数
            system_prompt = text_to_image_settings.text_to_image_system_prompt or DEFAULT_TEXT_TO_IMAGE_SYSTEM_PROMPT
            context_message_count = text_to_image_settings.context_message_count
            few_shot_max_length = getattr(text_to_image_settings, 'few_shot_max_length', DEFAULT_FEW_SHOT_MAX_LENGTH)
            temperature = getattr(text_to_image_settings, 'text_to_image_temperature', 1.0)
            model_for_text_to_image = getattr(text_to_image_settings, 'model_for_text_to_image', "gemini-1.5-pro")
            default_positive_prompt = text_to_image_settings.default_positive_prompt
            default_negative_prompt = text_to_image_settings.default_negative_prompt
            safety_settings = gemini_config.safety_settings.to_gemini_format()
            max_output_tokens = gemini_config.model_settings.max_output_tokens

            # 创建API调用配置
            config_kwargs = {
                "system_instruction": system_prompt,
                "safety_settings": safety_settings,
                "temperature": temperature,
                "max_output_tokens": max_output_tokens
            }
            
            # 添加thinking配置（如果适用）
            if (model_for_text_to_image.startswith("gemini-2.5") and 
                gemini_config.model_settings.enable_thinking_for_gemini_2_5):
                config_kwargs["thinking_config"] = types.ThinkingConfig(
                    include_thoughts=gemini_config.model_settings.include_thoughts_in_response
                )
            
            prompt_config = types.GenerateContentConfig(**config_kwargs)
            
            # 获取最新的对话消息
            latest_messages = get_latest_n_messages(session_id, context_message_count) if session_id else tuple([None] * context_message_count)
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
            for record in few_shot_history[-few_shot_max_length:]:  # 使用配置的示例数量
                # 直接添加用户消息和助手回复，保持原有的格式
                user_msg = UserMessage(role="user", content=record['user_message']['content'])
                messages.append(user_msg)
                
                assistant_msg = AssistantMessage(role="assistant", content=record['assistant_message']['content'])
                messages.append(assistant_msg)
            
            # 构造当前请求 - 注意：latest_messages是当前对话上下文，用于理解用户想要生成什么图像
            conversation_text = CONVERSATION_TEXT_PROMPT_PREFIX
            for msg in latest_messages:
                if msg is not None:
                    # 正确提取文本内容，处理 Union[str, List[dict]] 类型
                    text_content = extract_text_content(msg.content)
                    conversation_text += f"{msg.role}: {text_content}\n"
            
            current_request = UserMessage(role="user", content=conversation_text)
            messages.append(current_request)
            
            # 使用MessageFormatter进行消息格式转换
            contents = MessageFormatter.format_messages_for_gemini(messages)
            if debug:
                import pprint
                print("[text_to_image] Formatted contents:")
                pprint.pprint(contents)
            

            
            response = client.models.generate_content(
                model=model_for_text_to_image,
                contents=contents,
                config=prompt_config
            )

            # Extract response text using ResponseProcessor
            prompt_text = ResponseProcessor.extract_text_content(response)
            
            if prompt_text:
                # 使用工具函数解析响应
                parsed_result = parse_text_to_image_response(
                    prompt_text,
                    default_negative_prompt=DEFAULT_NEGATIVE_PROMPT,
                    debug=debug
                )
                
                if parsed_result is None:
                    return None
                
                text_prompt, negative_prompt = parsed_result
                
                # 使用工具函数增强提示词
                text_prompt, negative_prompt = enhance_prompts_with_defaults(
                    text_prompt=text_prompt,
                    negative_prompt=negative_prompt,
                    default_positive_prompt=default_positive_prompt,
                    default_negative_prompt=default_negative_prompt,
                    debug=debug
                )
                
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