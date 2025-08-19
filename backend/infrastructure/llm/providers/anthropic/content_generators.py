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
from backend.infrastructure.llm.base.content_generators import (
    BaseTitleGenerator,
    BaseWebSearchGenerator,
    BaseImagePromptGenerator
)
from backend.infrastructure.llm.shared.constants import (
    DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT,
    DEFAULT_WEB_SEARCH_SYSTEM_PROMPT
)
from .message_formatter import MessageFormatter
from backend.config import get_llm_settings
from .config import get_anthropic_client_config
from .debug import AnthropicDebugger


class TitleGenerator(BaseTitleGenerator):
    """
    Handles conversation title generation using Anthropic Claude API.
    
    Generates concise, descriptive titles based on the first exchange
    in a conversation to help users identify and organize their chats.
    Inherits from BaseTitleGenerator for consistency with other providers.
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
            
            # Use shared system prompt for consistency
            system_prompt = DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT
            
            # 构造消息序列
            messages = list(latest_messages) + [
                UserMessage(role="user", content=[{"type": "text", "text": "请为上面对话生成标题"}])
            ]
            
            # 使用MessageFormatter进行消息格式转换
            formatted_messages = MessageFormatter.format_messages(messages)
            
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


class AnthropicWebSearchGenerator(BaseWebSearchGenerator):
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
            formatted_messages = MessageFormatter.format_messages([user_message])
            
            # Use shared web search system prompt for consistency
            web_search_system_prompt = DEFAULT_WEB_SEARCH_SYSTEM_PROMPT
            
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


from backend.infrastructure.llm.base.content_generators import BaseImagePromptGenerator

class ImagePromptGenerator(BaseImagePromptGenerator):
    """
    Handles text-to-image prompt generation using Anthropic Claude API.
    
    Creates detailed and effective prompts for image generation based on
    recent conversation context, with support for positive and negative prompts.
    """

    @staticmethod
    async def generate_text_to_image_prompt(
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
            # Get Anthropic configuration for model info
            llm_settings = get_llm_settings()
            llm_anthropic_config = llm_settings.get_anthropic_config()  # This has the 'model' attribute
            
            # Prepare generation context using inherited method with provider info
            context = ImagePromptGenerator.prepare_generation_context(
                session_id=session_id,
                llm_provider="anthropic",
                llm_model=llm_anthropic_config.model
            )
            
            # Build messages using inherited method
            messages = ImagePromptGenerator.build_messages_for_generation(context)
            
            # Use MessageFormatter for message format conversion
            formatted_messages = MessageFormatter.format_messages(messages)
            
            if debug:
                print("\n[text_to_image] Messages for prompt generation:")
                import pprint
                pprint.pprint(messages)
                print("[text_to_image] Formatted messages:")
                pprint.pprint(formatted_messages)
            
            if debug:
                print(f"\n[Anthropic][text_to_image] System prompt: {context['system_prompt']}")
            
            # Use the model from context (which now correctly uses Anthropic's model)
            model_for_text_to_image = context.get('model', llm_anthropic_config.model)
            
            response = client.messages.create(
                model=model_for_text_to_image,
                max_tokens=4096,
                temperature=context.get('temperature', 1.0),
                system=context['system_prompt'],
                messages=formatted_messages
            )

            if response.content and len(response.content) > 0:
                prompt_text = response.content[0].text
                
                # Process response using inherited method
                return ImagePromptGenerator.process_generation_response(
                    prompt_text, context, session_id, debug
                )
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
            
            analysis_messages = MessageFormatter.format_messages([
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