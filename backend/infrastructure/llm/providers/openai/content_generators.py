"""
Content generation utilities for OpenAI API.

Specialized generators for creating titles, image prompts, and other derived content
based on conversation context. Provides OpenAI-specific implementations while
maintaining compatibility with the unified content generation interface.
"""

from typing import Optional, Dict, Any, List
import re
import json
from backend.domain.models.messages import BaseMessage, UserMessage
from backend.config import get_text_to_image_settings
from backend.infrastructure.storage.session_manager import get_latest_n_messages
from .message_formatter import MessageFormatter
from .debug import OpenAIDebugger
from .constants import *


class TitleGenerator:
    """
    Handles conversation title generation using OpenAI API.
    
    Generates concise, descriptive titles based on the first exchange
    in a conversation to help users identify and organize their chats.
    """

    @staticmethod
    def generate_title_from_messages(
        client,  # OpenAI client instance
        latest_messages: List[BaseMessage]
    ) -> Optional[str]:
        """
        Generate a concise conversation title based on recent messages.
        
        Args:
            client: OpenAI client instance for API calls
            latest_messages: Recent conversation messages to generate title from
            
        Returns:
            Generated title string, or None if generation fails
        """
        try:
            if not latest_messages or len(latest_messages) < 2:
                return None
            
            # Default system prompt for title generation
            system_prompt = (
                "You are a professional conversation title generator. Generate a concise title (5-15 words) "
                "that accurately summarizes the main topic or intent of the conversation. "
                "Put the title in <title></title> tags and output nothing else."
            )
            
            # Build conversation messages
            messages = list(latest_messages) + [
                UserMessage(role="user", content=[{"type": "text", "text": "Please generate a title for the above conversation"}])
            ]
            
            # Format messages for OpenAI API
            formatted_messages = MessageFormatter.format_messages(messages)
            
            # Add system prompt
            api_messages = [{"role": "system", "content": system_prompt}] + formatted_messages
            
            # Use smaller model for title generation
            response = client.chat.completions.create(
                model=DEFAULT_TITLE_MODEL,
                messages=api_messages,
                temperature=TITLE_GENERATION_TEMPERATURE,
                max_tokens=100
            )
            
            if not response.choices:
                return None
            
            title_response_text = response.choices[0].message.content or ""
            
            # Extract title from tags
            title_match = re.search(r'<title>(.*?)</title>', title_response_text, re.DOTALL)
            if title_match:
                title = title_match.group(1).strip()
                if title and len(title) <= TITLE_MAX_LENGTH:
                    return title
            
            # Fallback: clean the response directly
            cleaned_title = title_response_text.strip().strip('"\'').strip()
            if cleaned_title and len(cleaned_title) <= TITLE_MAX_LENGTH:
                return cleaned_title
            
            return None
            
        except Exception as e:
            print(f"OpenAI title generation error: {str(e)}")
            return None


class ImagePromptGenerator:
    """
    Handles text-to-image prompt generation using OpenAI API.
    
    Creates detailed and effective prompts for image generation based on
    recent conversation context, with support for positive and negative prompts.
    """

    @staticmethod
    def generate_text_to_image_prompt(
        client,  # OpenAI client instance
        session_id: Optional[str] = None,
        debug: bool = False
    ) -> Optional[Dict[str, str]]:
        """
        Generate high-quality text-to-image prompts using recent conversation context.
        
        Args:
            client: OpenAI client instance for API calls
            session_id: Optional session ID for conversation context
            debug: Enable debug output
            
        Returns:
            Dictionary with 'text_prompt' and 'negative_prompt' keys, or None if failed
        """
        try:
            # Get configuration
            text_to_image_settings = get_text_to_image_settings()
            
            system_prompt = text_to_image_settings.text_to_image_system_prompt or (
                "You are a professional prompt engineer. Generate a detailed and creative text-to-image prompt "
                "based on the following conversation. The prompt should be suitable for high-quality image generation. "
                "Format your response with <text_to_image_prompt>...</text_to_image_prompt> and "
                "<negative_prompt>...</negative_prompt> tags."
            )
            
            context_message_count = text_to_image_settings.context_message_count
            
            # Get recent conversation context
            latest_messages = get_latest_n_messages(session_id, context_message_count) if session_id else tuple([None] * context_message_count)
            if not any(latest_messages):
                if debug:
                    print(f"[text_to_image] No context messages for session {session_id}")
                return None
            
            # Build conversation text
            conversation_text = "Please generate a text-to-image prompt based on the following conversation:\n\n"
            for msg in latest_messages:
                if msg is not None:
                    # Extract text content from multimodal messages
                    if isinstance(msg.content, list):
                        text_parts = []
                        for block in msg.content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text_parts.append(block.get("text", ""))
                            elif isinstance(block, dict) and "text" in block:
                                text_parts.append(block["text"])
                        content_text = "".join(text_parts)
                    else:
                        content_text = str(msg.content)
                    
                    conversation_text += f"{msg.role}: {content_text}\n"
            
            # Create user message
            user_message = UserMessage(role="user", content=conversation_text)
            formatted_messages = MessageFormatter.format_messages([user_message])
            
            # Add system prompt
            api_messages = [{"role": "system", "content": system_prompt}] + formatted_messages
            
            if debug:
                OpenAIDebugger.print_debug_request_payload({
                    'model': DEFAULT_IMAGE_PROMPT_MODEL,
                    'messages': api_messages
                })
            
            # Call OpenAI API
            response = client.chat.completions.create(
                model=DEFAULT_IMAGE_PROMPT_MODEL,
                messages=api_messages,
                temperature=IMAGE_PROMPT_TEMPERATURE,
                max_tokens=1024
            )
            
            if not response.choices:
                return None
            
            prompt_text = response.choices[0].message.content or ""
            
            if debug:
                print(f"[text_to_image] Raw response: {prompt_text[:200]}...")
            
            # Parse response
            text_match = re.search(r"<text_to_image_prompt>(.*?)</text_to_image_prompt>", prompt_text, re.DOTALL)
            neg_match = re.search(r"<negative_prompt>(.*?)</negative_prompt>", prompt_text, re.DOTALL)
            
            if not text_match:
                if debug:
                    print("[text_to_image] Failed to parse prompt tags")
                return None
            
            text_prompt = text_match.group(1).strip()
            negative_prompt = (
                neg_match.group(1).strip() if neg_match 
                else "blurry, low quality, distorted, extra limbs, bad anatomy, text, watermark, ugly"
            )
            
            # Enhance with defaults
            default_positive = text_to_image_settings.text_to_image_default_positive_prompt
            default_negative = text_to_image_settings.text_to_image_default_negative_prompt
            
            if default_positive:
                # Add missing positive keywords
                existing_keywords = set(kw.strip().lower() for kw in text_prompt.split(","))
                default_keywords = set(kw.strip().lower() for kw in default_positive.split(","))
                missing_keywords = default_keywords - existing_keywords
                
                if missing_keywords:
                    missing_text = ", ".join(missing_keywords)
                    text_prompt = f"{missing_text}, {text_prompt}"
            
            if default_negative:
                # Add missing negative keywords
                existing_neg_keywords = set(kw.strip().lower() for kw in negative_prompt.split(","))
                default_neg_keywords = set(kw.strip().lower() for kw in default_negative.split(","))
                missing_neg_keywords = default_neg_keywords - existing_neg_keywords
                
                if missing_neg_keywords:
                    missing_neg_text = ", ".join(missing_neg_keywords)
                    negative_prompt = f"{missing_neg_text}, {negative_prompt}"
            
            if debug:
                print(f"[text_to_image] Final text_prompt: {text_prompt}")
                print(f"[text_to_image] Final negative_prompt: {negative_prompt}")
            
            return {
                "text_prompt": text_prompt,
                "negative_prompt": negative_prompt
            }
            
        except Exception as e:
            if debug:
                print(f"[text_to_image] Error during prompt generation: {str(e)}")
            return None


class WebSearchGenerator:
    """
    Handles web search using OpenAI API.
    
    Note: OpenAI doesn't have built-in web search capabilities like Gemini.
    This implementation provides a placeholder that should integrate with
    MCP tools for actual web search functionality.
    """

    @staticmethod
    def perform_web_search(
        client,  # OpenAI client instance
        query: str,
        debug: bool = False
    ) -> Dict[str, Any]:
        """
        Perform a web search using MCP tools (OpenAI doesn't have built-in search).
        
        Args:
            client: OpenAI client instance (not used for search)
            query: The search query
            debug: Enable debug output
            
        Returns:
            Dictionary indicating that OpenAI requires external tools for search
        """
        if debug:
            print(f"[WebSearch] OpenAI client requested search for: {query}")
            print("[WebSearch] Note: OpenAI requires external MCP tools for web search")
        
        return {
            "error": "OpenAI client requires MCP web search tools",
            "query": query,
            "suggestion": "Use MCP tools like 'web_search' or 'google_search' for web search functionality",
            "sources": [],
            "total_sources": 0
        }