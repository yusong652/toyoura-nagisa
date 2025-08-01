"""
Content generation utilities for Anthropic Claude API.

Specialized generators for creating titles, image prompts, and other derived content
based on conversation context. Separates content generation concerns from the main client.
"""

import re
import json
from typing import Optional, Dict, List, Any
import anthropic
from backend.domain.models.messages import BaseMessage, UserMessage
from .message_formatter import MessageFormatter
from backend.config import get_text_to_image_config
from .config import get_anthropic_client_config
from backend.infrastructure.storage.session_manager import get_latest_n_messages
from .debug import AnthropicDebugger


class TitleGenerator:
    """
    Handles conversation title generation using Anthropic Claude API.
    
    Generates concise, descriptive titles based on the first exchange
    in a conversation to help users identify and organize their chats.
    """

    @staticmethod
    def generate_title_from_messages(
        client: anthropic.Anthropic,
        latest_messages: List[BaseMessage]
    ) -> Optional[str]:
        """
        Generate a concise conversation title based on recent messages.
        
        Args:
            client: Anthropic Claude client instance for API calls
            latest_messages: Recent conversation messages to generate title from
            
        Returns:
            Generated title string, or None if generation fails
        """
        try:
            if not latest_messages or len(latest_messages) < 2:
                return None
            
            system_prompt = (
                "你是一个专业的对话标题生成助手。请根据提供的对话内容，生成一个简洁的标题（5-15个字）。"
                "标题应准确概括对话的主要主题或意图。你必须将标题放在<title></title>标签中，"
                "并且除了这些标签和标题本身外，不要输出任何其他内容。"
            )
            
            # 构造消息序列
            messages = list(latest_messages) + [
                UserMessage(role="user", content=[{"type": "text", "text": "请为上面对话生成标题"}])
            ]
            
            # 使用MessageFormatter进行消息格式转换
            formatted_messages = MessageFormatter.format_messages_for_anthropic(messages)
            
            # Use the new Anthropic configuration system
            anthropic_config = get_anthropic_client_config()
            
            # Build API call parameters using the configuration system
            api_kwargs = anthropic_config.get_api_call_kwargs(
                system_prompt=system_prompt,
                messages=formatted_messages
            )
            
            # Override parameters specific to title generation
            api_kwargs.update({
                "max_tokens": 1024,
                "temperature": 1.0
            })
            
            response = client.messages.create(**api_kwargs)
            
            if response.content and len(response.content) > 0:
                title_response_text = response.content[0].text
                
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
            print(f"Anthropic生成标题时出错: {str(e)}")
            return None


class WebSearchGenerator:
    """
    Handles web search using Anthropic Claude API with web_search_20250305 tool.

    Performs web searches using the native web search capability via the Anthropic API.
    Returns structured results with proper error handling and debugging support.
    """

    @staticmethod
    async def perform_web_search(
        client: anthropic.Anthropic,
        query: str,
        debug: bool = False,
        max_uses: int = 5
    ) -> Dict[str, Any]:
        """
        Perform a web search using the native web search tool via Anthropic API.
        
        Uses the web_search_20250305 tool. The model will automatically
        decide whether to perform a search based on the query requirements.
        
        Args:
            client: Anthropic Claude client instance
            query: The search query to find information on the web
            debug: Enable debug output
            max_uses: Maximum number of search tool uses (default: 5)
            
        Returns:
            Dictionary containing search results or error information
        """
        try:
            # Create user message with search query
            user_message = UserMessage(role="user", content=query)
            
            # Format message using MessageFormatter
            formatted_messages = MessageFormatter.format_messages_for_anthropic([user_message])
            
            # Configure web search system prompt
            web_search_system_prompt = (
                "You are a professional web search assistant. Your task is to search for and synthesize "
                "information from the web to provide comprehensive, accurate, and up-to-date answers. "
                "When searching:\n"
                "1. Use the web search tool to find relevant and current information\n"
                "2. Analyze multiple sources for accuracy and reliability\n"
                "3. Synthesize information into a coherent, well-structured response\n"
                "4. Prioritize recent and authoritative sources\n"
                "5. Clearly indicate when information is uncertain or requires verification\n"
                "6. Provide context and explain complex topics clearly\n"
                "Focus on delivering factual, helpful information that directly addresses the user's query."
            )
            
            # Use the new Anthropic configuration system
            anthropic_config = get_anthropic_client_config()
            
            # Build API call parameters using the configuration system
            api_kwargs = anthropic_config.get_api_call_kwargs(
                system_prompt=web_search_system_prompt,
                messages=formatted_messages,
                tools=[{
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": max_uses
                }]
            )
            
            # Override some parameters specific to web search
            api_kwargs.update({
                "max_tokens": 4096,
                "temperature": 0.1
            })
            
            if debug:
                # 使用统一的调试工具打印详细的API payload
                AnthropicDebugger.log_api_payload(api_kwargs, component="WebSearch", detailed=True)
            
            # Call the API with web search tool (async version)
            response = await client.messages.create(**api_kwargs)
            
            if debug:
                # 使用统一的调试工具打印API响应信息
                AnthropicDebugger.log_api_response(response)
            
            # Extract response text and tool usage information
            response_text = ""
            tool_calls = []
            sources = []
            
            if response.content:
                for content_block in response.content:
                    if hasattr(content_block, 'text'):
                        response_text += content_block.text
                    elif hasattr(content_block, 'type') and content_block.type == 'tool_use':
                        # Track tool calls for debugging
                        tool_calls.append({
                            'tool_name': getattr(content_block, 'name', 'unknown'),
                            'tool_id': getattr(content_block, 'id', 'unknown'),
                            'input': getattr(content_block, 'input', {})
                        })
                        
            
            # Note: Unlike Gemini, Anthropic's web_search_20250305 tool doesn't expose
            # individual source URLs in the response structure. The search results
            # are synthesized into the response text directly.
            
            # Build structured result
            result = {
                "query": query,
                "response_text": response_text,
                "sources": sources,  # Empty for Anthropic as sources aren't exposed
                "total_sources": len(sources),
                "tool_calls": tool_calls,
                "note": "Anthropic web search synthesizes results directly into response text"
            }
            
            
            return result
            
        except Exception as e:
            error_msg = f"An error occurred during web search: {str(e)}"
            if debug:
                print(f"[WebSearch] Error: {error_msg}")
            return {"error": error_msg, "query": query}


class ImagePromptGenerator:
    """
    Handles text-to-image prompt generation using Anthropic Claude API.
    
    Creates detailed and effective prompts for image generation based on
    recent conversation context, with support for positive and negative prompts.
    """

    @staticmethod
    def generate_text_to_image_prompt(
        client: anthropic.Anthropic,
        session_id: Optional[str] = None,
        debug: bool = False
    ) -> Optional[Dict[str, str]]:
        """
        Generate high-quality text-to-image prompts using recent conversation context.
        
        Args:
            client: Anthropic Claude client instance for API calls
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
                "suitable for high-quality image generation. Format your response with "
                "<text_to_image_prompt>your prompt here</text_to_image_prompt> and optionally "
                "<negative_prompt>negative prompt here</negative_prompt>."
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
                    # Handle different content formats
                    if isinstance(msg.content, list):
                        # Extract text from list content
                        text_parts = []
                        for item in msg.content:
                            if isinstance(item, dict) and "text" in item:
                                text_parts.append(item["text"])
                        content = " ".join(text_parts)
                    else:
                        content = str(msg.content)
                    conversation_text += f"{msg.role}: {content}\n"
            
            messages = [UserMessage(role="user", content=conversation_text)]
            
            # 使用MessageFormatter进行消息格式转换
            formatted_messages = MessageFormatter.format_messages_for_anthropic(messages)
            
            if debug:
                print("\n[text_to_image] Messages for prompt generation:")
                import pprint
                pprint.pprint(messages)
                print("[text_to_image] Formatted messages:")
                pprint.pprint(formatted_messages)
            
            if debug:
                print(f"\n[Anthropic][text_to_image] System prompt: {system_prompt}")
            
            response = client.messages.create(
                model=config.get("model_for_text_to_image", "claude-3-5-sonnet-20241022"),
                max_tokens=4096,
                temperature=1.0,
                system=system_prompt,
                messages=formatted_messages
            )

            if response.content and len(response.content) > 0:
                prompt_text = response.content[0].text
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
                    print(f"[Anthropic][text_to_image] Final text_prompt: {text_prompt}")
                    print(f"[Anthropic][text_to_image] Final negative_prompt: {negative_prompt}")
                
                return {
                    "text_prompt": text_prompt,
                    "negative_prompt": negative_prompt
                }
            return None
            
        except Exception as e:
            if debug:
                print(f"[text_to_image] Error during prompt generation: {str(e)}")
            return None


class AnalysisGenerator:
    """
    Handles various analysis tasks using Anthropic Claude API.
    
    Provides structured analysis capabilities that leverage Claude's
    analytical strengths for tasks like code review, document analysis, etc.
    """

    @staticmethod
    def analyze_conversation_sentiment(
        client: anthropic.Anthropic,
        messages: List[BaseMessage],
        debug: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze the sentiment and tone of a conversation.
        
        Args:
            client: Anthropic Claude client instance
            messages: List of messages to analyze
            debug: Enable debug output
            
        Returns:
            Dictionary with sentiment analysis results
        """
        try:
            if not messages:
                return None
                
            # 构造分析提示
            conversation_text = "Please analyze the sentiment and tone of this conversation:\n\n"
            for msg in messages[-5:]:  # Analyze last 5 messages
                if isinstance(msg.content, list):
                    text_parts = []
                    for item in msg.content:
                        if isinstance(item, dict) and "text" in item:
                            text_parts.append(item["text"])
                    content = " ".join(text_parts)
                else:
                    content = str(msg.content)
                conversation_text += f"{msg.role}: {content}\n"
            
            conversation_text += "\nProvide analysis in JSON format with keys: overall_sentiment, confidence, key_themes, tone."
            
            analysis_messages = MessageFormatter.format_messages_for_anthropic([
                UserMessage(role="user", content=conversation_text)
            ])
            
            # Use the new Anthropic configuration system
            anthropic_config = get_anthropic_client_config()
            
            # Build API call parameters using the configuration system
            api_kwargs = anthropic_config.get_api_call_kwargs(
                system_prompt="",  # No system prompt for analysis
                messages=analysis_messages
            )
            
            # Override parameters specific to sentiment analysis
            api_kwargs.update({
                "max_tokens": 1024,
                "temperature": 0.1  # Lower temperature for consistent analysis
            })
            
            # Remove system prompt as we don't need it for this analysis
            api_kwargs.pop("system", None)
            
            response = client.messages.create(**api_kwargs)
            
            if response.content and len(response.content) > 0:
                analysis_text = response.content[0].text
                
                # Try to extract JSON from response
                try:
                    # Look for JSON in the response
                    json_match = re.search(r'\{.*\}', analysis_text, re.DOTALL)
                    if json_match:
                        analysis_data = json.loads(json_match.group(0))
                        return analysis_data
                    else:
                        # Fallback: parse structured text response
                        return {"raw_analysis": analysis_text}
                except json.JSONDecodeError:
                    return {"raw_analysis": analysis_text}
                    
            return None
            
        except Exception as e:
            if debug:
                print(f"[sentiment_analysis] Error: {str(e)}")
            return None