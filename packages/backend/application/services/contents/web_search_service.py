"""
Web Search Service - Application layer web search orchestration.
"""

import json
from typing import Dict, Any, Optional, List
from backend.config import get_llm_settings
from backend.domain.models.messages import BaseMessage, UserMessage
from backend.infrastructure.llm.shared.constants import DEFAULT_WEB_SEARCH_SYSTEM_PROMPT
from backend.infrastructure.llm.providers.google.config import get_google_client_config
from backend.infrastructure.llm.providers.google.message_formatter import GoogleMessageFormatter
from backend.infrastructure.llm.providers.google.response_processor import GoogleResponseProcessor
from backend.infrastructure.llm.providers.anthropic.message_formatter import MessageFormatter


async def perform_web_search(
    llm_client,
    query: str,
    max_uses: Optional[int] = None,
) -> Dict[str, Any]:
    llm_settings = get_llm_settings()
    provider_name = _get_provider_name(llm_client)

    if max_uses is None:
        if provider_name == "google":
            max_uses = llm_settings.get_google_config().web_search_max_uses
        elif provider_name == "anthropic":
            max_uses = llm_settings.get_anthropic_config().web_search_max_uses
        elif provider_name == "openai":
            max_uses = 5
        elif provider_name in ("moonshot", "zhipu"):
            max_uses = 1
        else:
            max_uses = 5

    if provider_name == "google":
        return await _perform_google_search(llm_client, query, max_uses)
    if provider_name == "anthropic":
        return await _perform_anthropic_search(llm_client, query, max_uses)
    if provider_name == "openai":
        return await _perform_openai_search(llm_client, query)
    if provider_name == "moonshot":
        return await _perform_moonshot_search(llm_client, query)
    if provider_name == "zhipu":
        return await _perform_zhipu_search(llm_client, query)

    return {
        "error": f"Unsupported LLM type: {provider_name}",
        "query": query,
    }

def _format_search_result(
    query: str,
    response_text: str,
    sources: List[Dict[str, Any]],
    error: Optional[str] = None,
) -> Dict[str, Any]:
    if response_text:
        parts = [response_text]
        if sources:
            parts.append("\n\n---\n**Sources:**")
            for i, source in enumerate(sources, 1):
                title = source.get("title", "Unknown")
                url = source.get("url", "")
                if url:
                    parts.append(f"{i}. [{title}]({url})")
                else:
                    parts.append(f"{i}. {title}")
        response_text = "\n".join(parts)

    return {
        "query": query,
        "response_text": response_text,
        "sources": sources,
        "total_sources": len(sources),
        "error": error,
    }


def _format_search_error(query: str, error_message: str) -> Dict[str, Any]:
    return _format_search_result(query, "", [], error_message)


def _build_search_user_message(query: str) -> UserMessage:
    return UserMessage(role="user", content=query)


def _get_provider_name(llm_client) -> str:
    provider_name = getattr(llm_client, "provider_name", None)
    if not provider_name:
        raise ValueError("LLM client is missing provider_name")
    return provider_name.lower()


async def _perform_google_search(llm_client, query: str, max_uses: int) -> Dict[str, Any]:
    google_client_config = get_google_client_config()

    from google.genai import types

    # Build GenerateContentConfig with search tool
    search_config = types.GenerateContentConfig(
        system_instruction=DEFAULT_WEB_SEARCH_SYSTEM_PROMPT,
        tools=[types.Tool(google_search=types.GoogleSearch())],
        safety_settings=google_client_config.safety_settings.to_gemini_format(),
    )

    # Format messages to Gemini context contents
    messages: List[BaseMessage] = [_build_search_user_message(query)]
    context_contents = GoogleMessageFormatter.format_messages(messages)

    # Prepare API config with GenerateContentConfig
    api_config = {
        "config": search_config,
    }

    # Use the client's call_api_with_context method
    response = await llm_client.call_api_with_context(
        context_contents=context_contents,
        api_config=api_config,
    )

    if not response.candidates:
        return _format_search_error(query, "No search results found")

    sources = GoogleResponseProcessor.extract_web_search_sources(response)
    response_text = GoogleResponseProcessor.extract_text_content(response)

    result = _format_search_result(query, response_text, sources)
    return result


async def _perform_anthropic_search(llm_client, query: str, max_uses: int) -> Dict[str, Any]:
    from backend.infrastructure.llm.providers.anthropic.response_processor import AnthropicResponseProcessor

    user_message = _build_search_user_message(query)
    context_contents = MessageFormatter.format_messages([user_message])

    # Prepare API config with web_search tool and system prompt
    api_config = {
        "tools": [{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": max_uses,
        }],
        "system_prompt": DEFAULT_WEB_SEARCH_SYSTEM_PROMPT,
    }

    # Use the client's call_api_with_context method
    # Override max_tokens, temperature, and thinking budget for web_search
    response = await llm_client.call_api_with_context(
        context_contents=context_contents,
        api_config=api_config,
        max_tokens=4096,
        temperature=1.0,
        thinking={"type": "enabled", "budget_tokens": 2048},
    )

    # Use response processor to extract content
    response_processor = AnthropicResponseProcessor()
    response_text = response_processor.extract_text_content(response)
    sources = response_processor.extract_web_search_sources(response)

    result = _format_search_result(query, response_text, sources)
    return result


async def _perform_openai_search(llm_client, query: str) -> Dict[str, Any]:
    from backend.infrastructure.llm.providers.openai.response_processor import OpenAIResponseProcessor

    # Prepare context contents (input items in Responses API format)
    context_contents = [
        {
            "role": "user",
            "content": query,
        }
    ]

    # Prepare API config with tools and instructions
    api_config = {
        "tools": [{"type": "web_search"}],
        "instructions": DEFAULT_WEB_SEARCH_SYSTEM_PROMPT,
    }

    # Use the client's call_api_with_context method
    response = await llm_client.call_api_with_context(
        context_contents=context_contents,
        api_config=api_config,
    )

    if not response.output:
        return _format_search_error(query, "No search results found")

    # Use response processor to extract content
    response_processor = OpenAIResponseProcessor()
    response_text = response_processor.extract_text_content(response)
    sources = response_processor.extract_web_search_sources(response)

    result = _format_search_result(query, response_text, sources)
    return result


async def _perform_moonshot_search(llm_client, query: str) -> Dict[str, Any]:
    from backend.infrastructure.llm.providers.moonshot.response_processor import MoonshotResponseProcessor

    llm_settings = get_llm_settings()
    moonshot_config = llm_settings.get_moonshot_config()

    # Prepare context contents (messages without system prompt)
    context_contents: List[Dict[str, Any]] = [
        {"role": "user", "content": query},
    ]

    # Prepare API config with tools and system prompt
    api_config = {
        "tools": [
            {"type": "builtin_function", "function": {"name": "$web_search"}},
        ],
        "system_prompt": DEFAULT_WEB_SEARCH_SYSTEM_PROMPT,
    }

    finish_reason = None
    choice = None

    while finish_reason is None or finish_reason == "tool_calls":
        # Use the client's call_api_with_context method
        response = await llm_client.call_api_with_context(
            context_contents=context_contents,
            api_config=api_config,
            temperature=moonshot_config.temperature,
        )

        if not response.choices:
            return _format_search_error(query, "No search results found")

        choice = response.choices[0]
        finish_reason = choice.finish_reason

        if finish_reason == "tool_calls" and choice.message.tool_calls:
            # Add assistant message with tool calls to context
            context_contents.append(choice.message.model_dump())

            for tool_call in choice.message.tool_calls:
                function = getattr(tool_call, "function", None)
                if not function:
                    continue

                tool_call_name = getattr(function, "name", "")
                tool_call_arguments_str = getattr(function, "arguments", "{}")
                tool_call_arguments = json.loads(tool_call_arguments_str)

                if tool_call_name == "$web_search":
                    tool_result = tool_call_arguments
                else:
                    tool_result = {"error": f"Unknown tool: {tool_call_name}"}

                tool_call_id = getattr(tool_call, "id", "")
                tool_result_content = json.dumps(tool_result, ensure_ascii=False)

                # Add tool result message to context
                context_contents.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": tool_call_name,
                    "content": tool_result_content,
                })

    if not choice:
        return _format_search_error(query, "No valid response")

    # Use response processor to extract content
    response_processor = MoonshotResponseProcessor()
    response_text = response_processor.extract_text_content(response)
    sources = response_processor.extract_web_search_sources(response)

    result = _format_search_result(query, response_text, sources)
    return result


async def _perform_zhipu_search(llm_client, query: str) -> Dict[str, Any]:
    from backend.infrastructure.llm.providers.zhipu.response_processor import ZhipuResponseProcessor

    llm_settings = get_llm_settings()
    zhipu_config = llm_settings.get_zhipu_config()

    # Prepare context contents (messages without system prompt)
    context_contents = [
        {"role": "user", "content": query},
    ]

    # Prepare API config with tools and system prompt
    api_config = {
        "tools": [
            {
                "type": "web_search",
                "web_search": {
                    "search_query": query,
                    "search_result": True,
                },
            }
        ],
        "system_prompt": DEFAULT_WEB_SEARCH_SYSTEM_PROMPT,
    }

    # Use the client's call_api_with_context method
    response = await llm_client.call_api_with_context(
        context_contents=context_contents,
        api_config=api_config,
        temperature=zhipu_config.temperature,
        max_tokens=8000,
        enable_thinking=False,  # Disable thinking mode for web search
    )

    if not response.choices:
        return _format_search_error(query, "No search results found")

    # Use response processor to extract content
    response_processor = ZhipuResponseProcessor()
    response_text = response_processor.extract_text_content(response)
    sources = response_processor.extract_web_search_sources(response)

    result = _format_search_result(query, response_text, sources)
    return result


