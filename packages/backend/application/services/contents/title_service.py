"""
Title Service - Business logic for session title generation.

This service handles automatic title generation for chat sessions
based on conversation context.
"""
import asyncio
from typing import Dict, Any, Optional, List
from backend.infrastructure.storage.session_manager import (
    get_all_sessions,
    update_session_title,
    load_all_message_history,
    get_latest_n_messages,
)
from backend.domain.models.messages import BaseMessage
from backend.domain.models.message_factory import message_factory, extract_text_from_message
from backend.infrastructure.llm.providers.anthropic.config import get_anthropic_client_config
from backend.infrastructure.llm.providers.anthropic.response_processor import AnthropicResponseProcessor
from backend.infrastructure.llm.providers.google.response_processor import GoogleResponseProcessor
from backend.infrastructure.llm.providers.moonshot.response_processor import MoonshotResponseProcessor
from backend.infrastructure.llm.providers.openai.constants import (
    DEFAULT_TITLE_MODEL,
    TITLE_GENERATION_TEMPERATURE,
    TITLE_MAX_LENGTH,
)
from backend.infrastructure.llm.providers.openai.response_processor import OpenAIResponseProcessor
from backend.infrastructure.llm.providers.openrouter.response_processor import OpenRouterResponseProcessor
from backend.infrastructure.llm.providers.zhipu.response_processor import ZhipuResponseProcessor
from backend.infrastructure.llm.shared.constants import (
    DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT,
    DEFAULT_TITLE_GENERATION_TEMPERATURE,
    DEFAULT_TITLE_MAX_LENGTH,
)
from backend.infrastructure.llm.shared.utils.text_processing import parse_title_response


def _format_conversation_context(messages: List[BaseMessage]) -> str:
    conversation_parts = []
    for msg in messages:
        text = extract_text_from_message(msg)
        if not text or not text.strip():
            continue
        role_label = "User" if msg.role == "user" else "Assistant"
        conversation_parts.append(f"{role_label}: {text.strip()}")
    return "\n".join(conversation_parts)


def _build_title_prompt(conversation_context: str) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Please generate a concise title based on the following conversation:\n\n"
                f"{conversation_context}"
            ),
        },
    ]


async def _generate_title_google(llm_client: Any, latest_messages: List[BaseMessage]) -> Optional[str]:
    conversation_context = _format_conversation_context(latest_messages)
    if not conversation_context:
        return None

    from google.genai import types

    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part(
                    text=_build_title_prompt(conversation_context)[1]["content"]
                )
            ],
        )
    ]
    title_config = types.GenerateContentConfig(
        system_instruction=DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT,
        temperature=DEFAULT_TITLE_GENERATION_TEMPERATURE,
        max_output_tokens=2048,
    )

    response = await llm_client.client.aio.models.generate_content(
        model="gemini-2.0-flash",
        contents=contents,
        config=title_config,
    )

    title_response_text = GoogleResponseProcessor.extract_text_content(response)
    return parse_title_response(title_response_text, max_length=DEFAULT_TITLE_MAX_LENGTH)


async def _generate_title_anthropic(llm_client: Any, latest_messages: List[BaseMessage]) -> Optional[str]:
    conversation_context = _format_conversation_context(latest_messages)
    if not conversation_context:
        return None

    anthropic_config = get_anthropic_client_config()
    messages = [
        {
            "role": "user",
            "content": (
                "Please generate a concise title based on the following conversation:\n\n"
                f"{conversation_context}"
            ),
        }
    ]
    api_kwargs = anthropic_config.get_api_call_kwargs(
        system_prompt=DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT,
        messages=messages,
    )
    api_kwargs.update({"max_tokens": 100, "temperature": 1.0})
    api_kwargs.pop("thinking", None)

    response = await llm_client.client.messages.create(**api_kwargs)
    title_response_text = AnthropicResponseProcessor.extract_text_content(response)
    return parse_title_response(title_response_text, max_length=30)


async def _generate_title_openai(llm_client: Any, latest_messages: List[BaseMessage]) -> Optional[str]:
    conversation_context = _format_conversation_context(latest_messages)
    if not conversation_context:
        return None

    input_items = [
        {
            "role": "user",
            "content": (
                "Please generate a concise title based on the following conversation:\n\n"
                f"{conversation_context}"
            ),
        }
    ]
    api_kwargs = {
        "model": DEFAULT_TITLE_MODEL,
        "instructions": DEFAULT_TITLE_GENERATION_SYSTEM_PROMPT,
        "input": input_items,
        "temperature": TITLE_GENERATION_TEMPERATURE,
        "max_output_tokens": 100,
    }

    response = await llm_client.async_client.responses.create(**api_kwargs)
    title_response_text = OpenAIResponseProcessor.extract_text_content(response)
    return parse_title_response(title_response_text, max_length=TITLE_MAX_LENGTH)


async def _generate_title_moonshot(llm_client: Any, latest_messages: List[BaseMessage]) -> Optional[str]:
    conversation_context = _format_conversation_context(latest_messages)
    if not conversation_context:
        return None

    chat_messages = _build_title_prompt(conversation_context)
    response = await llm_client.async_client.chat.completions.create(
        model="kimi-k2-0905-preview",
        messages=chat_messages,
        temperature=DEFAULT_TITLE_GENERATION_TEMPERATURE,
        max_tokens=100,
    )

    title_response_text = MoonshotResponseProcessor.extract_text_content(response)
    return parse_title_response(title_response_text, max_length=DEFAULT_TITLE_MAX_LENGTH)


async def _generate_title_openrouter(llm_client: Any, latest_messages: List[BaseMessage]) -> Optional[str]:
    conversation_context = _format_conversation_context(latest_messages)
    if not conversation_context:
        return None

    from backend.config import get_llm_settings

    openrouter_config = get_llm_settings().get_openrouter_config()
    chat_messages = _build_title_prompt(conversation_context)
    response = await llm_client.async_client.chat.completions.create(
        model=openrouter_config.model,
        messages=chat_messages,
        temperature=DEFAULT_TITLE_GENERATION_TEMPERATURE,
        max_tokens=1000,
    )

    title_response_text = OpenRouterResponseProcessor.extract_text_content(response)
    return parse_title_response(title_response_text, max_length=DEFAULT_TITLE_MAX_LENGTH)


async def _generate_title_zhipu(llm_client: Any, latest_messages: List[BaseMessage]) -> Optional[str]:
    conversation_context = _format_conversation_context(latest_messages)
    if not conversation_context:
        return None

    chat_messages = _build_title_prompt(conversation_context)
    response = await llm_client.client.chat.completions.create(
        model="glm-4.5-air",
        messages=chat_messages,
        temperature=DEFAULT_TITLE_GENERATION_TEMPERATURE,
        max_tokens=2048,
        stream=False,
    )

    title_response_text = ZhipuResponseProcessor.extract_text_content(response)
    return parse_title_response(title_response_text, max_length=DEFAULT_TITLE_MAX_LENGTH)


TITLE_GENERATORS = {
    "google": _generate_title_google,
    "anthropic": _generate_title_anthropic,
    "openai": _generate_title_openai,
    "moonshot": _generate_title_moonshot,
    "openrouter": _generate_title_openrouter,
    "zhipu": _generate_title_zhipu,
}


def _get_title_generator(llm_client: Any):
    provider_name = getattr(llm_client, "provider_name", None)
    if not provider_name:
        raise ValueError("LLM client is missing provider_name")

    generator = TITLE_GENERATORS.get(provider_name.lower())
    if not generator:
        raise ValueError(f"Unsupported LLM provider for title generation: {provider_name}")

    return generator


async def generate_title_from_messages(
    llm_client: Any,
    latest_messages: List[BaseMessage]
) -> Optional[str]:
    try:
        generator = _get_title_generator(llm_client)
        return await generator(llm_client, latest_messages)
    except Exception as exc:
        print(f"[ERROR] Title generation failed: {exc}")
        import traceback
        traceback.print_exc()
        raise


def trigger_title_generation(session_id: str, llm_client: Any) -> None:
    """
    Trigger background title generation for a session.

    This is a fire-and-forget convenience function that schedules
    title generation as a background task. Safe to call from any
    async context without awaiting.

    Args:
        session_id: Session ID to generate title for
        llm_client: LLM client instance for title generation
    """
    title_service = TitleService()
    asyncio.create_task(
        title_service.try_generate_title_if_needed_async(session_id, llm_client)
    )


class TitleService:
    """
    Service layer for session title generation operations.

    Provides intelligent title generation based on conversation history,
    identifying key topics and generating concise, descriptive titles.
    """

    def should_generate_title(self, session_id: str, history_msgs: List) -> bool:
        """
        Determine if title generation is needed.

        Title generation is triggered only if:
        1. Current session has a default title (starts with 'New Chat' or contains 'New Conversation')
        2. History contains at least one pure text assistant message (non-tool message)

        Args:
            session_id: Session UUID to check
            history_msgs: List of message objects in the session

        Returns:
            bool: True if title should be generated, False otherwise
        """
        sessions = get_all_sessions()
        current_session = next((s for s in sessions if s['id'] == session_id), None)
        has_default_title = (
            current_session is not None and
            (
                current_session.get('name', '').startswith('New Chat')
                or 'New Conversation' in current_session.get('name', '')
            )
        )
        has_text_assistant = any(self._is_assistant_with_text_content(msg) for msg in history_msgs)
        return has_default_title and has_text_assistant

    def _is_assistant_with_text_content(self, msg) -> bool:
        """
        Check if message is an assistant message with text content.

        This method filters for assistant messages (ignoring user messages)
        and checks if they contain at least one text block with actual content.
        Messages with tool_use blocks are accepted if they also have text.

        This allows title generation to happen immediately after the first
        meaningful response, even if it also includes tool calls.

        Args:
            msg: Message object to check (can be user or assistant)

        Returns:
            bool: True if message is assistant with text content, False otherwise
        """
        # Only check assistant messages, skip user messages
        if getattr(msg, "role", None) != "assistant":
            return False

        # Check if content has at least one text block with actual text
        content = getattr(msg, "content", None)

        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    # Accept if has text block with non-empty content
                    if block.get('type') == 'text' and block.get('text', '').strip():
                        return True
        elif isinstance(content, str) and content.strip():
            # Handle string content (legacy format)
            return True

        return False

    def _is_pure_text_user(self, msg) -> bool:
        """
        Determine if user message is pure text (non-tool result message).

        A pure text user message does not contain tool_result blocks in its content.
        Tool result blocks are system-generated responses from tool execution.

        Args:
            msg: Message object to check

        Returns:
            bool: True if message is pure text user message, False otherwise
        """
        if getattr(msg, "role", None) != "user":
            return False

        # Check content for tool_result blocks
        content = getattr(msg, "content", None)
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get('type') == 'tool_result':
                    return False

        return True

    async def _generate_title_from_history(self, session_id: str, llm_client) -> Optional[str]:
        """
        Core logic: Find latest user and pure text assistant messages and generate title.

        Searches backward from end of history to find most recent pair of non-tool messages,
        then uses LLM to generate an appropriate session title.

        Filters out both:
        - Assistant messages with tool_use blocks (tool calls)
        - User messages with tool_result blocks (tool execution results)

        Args:
            session_id: Session UUID to generate title for
            llm_client: LLM client with generate_title_from_messages method

        Returns:
            Optional[str]: Generated title, or None if no suitable message pair found
        """
        latest_messages = list(get_latest_n_messages(session_id, 2))
        if len(latest_messages) < 2:
            return None

        title = await generate_title_from_messages(llm_client, latest_messages)
        return title

    async def try_generate_title_if_needed_async(
        self,
        session_id: str,
        llm_client
    ) -> None:
        """
        Asynchronously attempt to generate title when needed.

        This method checks if title generation is needed and triggers it if appropriate.
        Should be called after message completion in the presentation layer.

        Args:
            session_id: Session ID to generate title for
            llm_client: LLM client instance for title generation
        """
        try:
            # Load history and check if title generation is needed
            loaded_history = load_all_message_history(session_id)
            history_msgs = [message_factory(msg) if isinstance(msg, dict) else msg for msg in loaded_history]

            if self.should_generate_title(session_id, history_msgs):
                # Generate title
                result = await self.generate_title_for_session(session_id, llm_client)

                if result and result.get("success") and result.get("title"):
                    # Send title update via WebSocket
                    from backend.infrastructure.websocket.notification_service import WebSocketNotificationService
                    await WebSocketNotificationService.send_title_update(session_id, result["title"])
                    print(f"[INFO] Title auto-generated for session {session_id}: {result['title']}")

        except Exception as e:
            # Title generation failure should not affect main flow
            print(f"[WARNING] Background title generation failed for session {session_id}: {e}")

    async def generate_title_for_session(
        self,
        session_id: str,
        llm_client: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a descriptive title for a chat session.

        This operation:
        1. Validates the session exists
        2. Analyzes conversation history
        3. Uses LLM to generate appropriate title
        4. Updates session metadata

        Args:
            session_id: Session UUID to generate title for
            llm_client: LLM client for title generation

        Returns:
            Optional[Dict[str, Any]]: Title generation result or None if session not found:
                - session_id: str - Session that received new title
                - title: str - Generated title text
                - success: bool - Always True if successful
                - error: str - Error message if generation failed
        """
        # Validate session exists
        sessions = get_all_sessions()
        session = next((s for s in sessions if s['id'] == session_id), None)

        if not session:
            return None

        try:
            # Generate title using core logic
            new_title = await self._generate_title_from_history(session_id, llm_client)

            if new_title is None:
                return {
                    "error": "No valid user message or pure text assistant message found for title generation",
                    "success": False
                }

            if not new_title:
                return {
                    "error": "Title generation failed",
                    "success": False
                }

            # Update session title
            update_success = update_session_title(session_id, new_title)

            if not update_success:
                return {
                    "error": "Failed to update session title",
                    "success": False
                }

            return {
                "session_id": session_id,
                "title": new_title,
                "success": True
            }
        except Exception as e:
            import traceback
            print(f"[ERROR] Title generation error: {e}")
            print(f"[ERROR] Traceback:")
            traceback.print_exc()
            return {
                "error": str(e),
                "success": False
            }
