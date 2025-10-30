"""
Test Gemini streaming response and complete response extraction

This test verifies:
1. Streaming chunk structure (thinking vs text parts)
2. How to get complete response after streaming
3. Context assembly for multi-turn conversations

Model: gemini-2.5-flash-preview-09-2025
Based on: docs/gemini_streaming_structure.md
Date: 2025-10-29
"""

import asyncio
import os
from typing import List, Dict, Any
from google import genai
from google.genai import types


def get_api_key() -> str:
    """Get Google API key from environment or prompt user"""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        # Try reading from a local file (for development)
        try:
            from pathlib import Path
            import sys
            backend_path = Path(__file__).parent.parent
            sys.path.insert(0, str(backend_path))
            from config.llm import get_llm_settings
            llm_settings = get_llm_settings()
            gemini_config = llm_settings.get_gemini_config()
            api_key = gemini_config.google_api_key
        except Exception as e:
            raise ValueError(f"Cannot get Google API key: {e}. Please set GOOGLE_API_KEY environment variable.")
    return api_key


async def test_streaming_and_complete_response():
    """Test streaming chunks and complete response extraction"""

    # Initialize client
    api_key = get_api_key()
    client = genai.Client(api_key=api_key)

    # Test prompt (triggers thinking)
    prompt = "Solve this step by step: If a train travels 120 km in 2 hours, what is its average speed?"

    print("=" * 80)
    print("TEST: Streaming + Complete Response")
    print("=" * 80)
    print(f"Prompt: {prompt}")
    print()

    # Configure with thinking enabled
    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
            thinking_budget=2000
        )
    )

    # Start streaming (this returns an async generator)
    stream_generator = client.aio.models.generate_content_stream(
        model='gemini-2.5-flash-preview-09-2025',
        contents=prompt,
        config=config
    )

    # Track chunks
    chunk_count = 0
    thinking_parts = []
    text_parts = []

    print("--- Streaming Chunks ---")
    async for chunk in await stream_generator:
        chunk_count += 1

        # Check if chunk has parts (some chunks may only contain finish_reason)
        if not chunk.candidates[0].content.parts:
            print(f"Chunk #{chunk_count} (FINAL):")
            print(f"  finish_reason: {chunk.candidates[0].finish_reason}")
            print()
            continue

        for part in chunk.candidates[0].content.parts:
            if part.thought:
                # Thinking content
                thinking_parts.append(part.text)
                print(f"Chunk #{chunk_count} (THINKING):")
                print(f"  text length: {len(part.text)} chars")
                print(f"  preview: {part.text[:80]}...")
                print()
            else:
                # Regular text content
                text_parts.append(part.text)
                print(f"Chunk #{chunk_count} (TEXT):")
                print(f"  text length: {len(part.text)} chars")
                print(f"  content: {part.text}")
                print()

    print("=" * 80)
    print("STATISTICS")
    print("=" * 80)
    print(f"Total chunks: {chunk_count}")
    print(f"Thinking parts: {len(thinking_parts)}")
    print(f"Text parts: {len(text_parts)}")
    print()

    # Reconstruct full content
    full_thinking = "".join(thinking_parts)
    full_text = "".join(text_parts)

    print(f"Full thinking length: {len(full_thinking)} chars")
    print(f"Full text length: {len(full_text)} chars")
    print()
    print("Full text content:")
    print("-" * 80)
    print(full_text)
    print("-" * 80)
    print()

    return {
        "thinking": full_thinking,
        "text": full_text,
        "chunk_count": chunk_count,
        "thinking_parts_count": len(thinking_parts),
        "text_parts_count": len(text_parts)
    }


async def test_complete_response_await():
    """Test if 'await stream' returns complete response"""

    # Initialize client
    api_key = get_api_key()
    client = genai.Client(api_key=api_key)

    prompt = "Write a haiku about coding."

    print("=" * 80)
    print("TEST: Complete Response via 'await stream'")
    print("=" * 80)
    print(f"Prompt: {prompt}")
    print()

    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
            thinking_budget=2000
        )
    )

    stream_generator = client.aio.models.generate_content_stream(
        model='gemini-2.5-flash-preview-09-2025',
        contents=prompt,
        config=config
    )

    # First: iterate through stream
    print("--- Iterating through stream ---")
    chunk_count = 0
    async for chunk in await stream_generator:
        chunk_count += 1
        if not chunk.candidates[0].content.parts:
            continue
        for part in chunk.candidates[0].content.parts:
            part_type = "THINKING" if part.thought else "TEXT"
            print(f"Chunk #{chunk_count} ({part_type}): {len(part.text)} chars")

    print()
    print("--- After streaming complete ---")
    print(f"Total chunks received: {chunk_count}")
    print()

    # Try to await stream (this may not work as expected)
    # Need to create a new stream for this test
    print("--- Creating new stream to test 'await stream' ---")
    stream_generator2 = client.aio.models.generate_content_stream(
        model='gemini-2.5-flash-preview-09-2025',
        contents=prompt,
        config=config
    )

    # Check if we can get complete response without iterating
    try:
        # This is the key test: can we get complete response?
        complete_response = await stream_generator2

        print("✓ 'await stream' succeeded!")
        print()
        print(f"Response type: {type(complete_response)}")
        print(f"Has .text attribute: {hasattr(complete_response, 'text')}")
        print(f"Has .candidates attribute: {hasattr(complete_response, 'candidates')}")

        if hasattr(complete_response, 'text'):
            print(f"complete_response.text: {complete_response.text}")

        if hasattr(complete_response, 'candidates'):
            print(f"Number of candidates: {len(complete_response.candidates)}")
            if complete_response.candidates:
                candidate = complete_response.candidates[0]
                print(f"Candidate parts: {len(candidate.content.parts)}")

                # Extract all content
                for i, part in enumerate(candidate.content.parts):
                    part_type = "THINKING" if part.thought else "TEXT"
                    print(f"  Part {i} ({part_type}): {len(part.text)} chars")

        return complete_response

    except Exception as e:
        print(f"✗ 'await stream' failed: {e}")
        return None


async def test_multi_turn_conversation():
    """Test multi-turn conversation context building"""

    # Initialize client
    api_key = get_api_key()
    client = genai.Client(api_key=api_key)

    print("=" * 80)
    print("TEST: Multi-turn Conversation Context")
    print("=" * 80)
    print()

    # Conversation history
    conversation_history: List[Dict[str, Any]] = []

    # Turn 1
    user_msg_1 = "What is 5 + 3?"
    print(f"User: {user_msg_1}")

    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
            thinking_budget=2000
        )
    )

    stream_generator1 = client.aio.models.generate_content_stream(
        model='gemini-2.5-flash-preview-09-2025',
        contents=user_msg_1,
        config=config
    )

    # Collect response
    thinking_parts = []
    text_parts = []
    async for chunk in await stream_generator1:
        if not chunk.candidates[0].content.parts:
            continue
        for part in chunk.candidates[0].content.parts:
            if part.thought:
                thinking_parts.append(part.text)
            else:
                text_parts.append(part.text)

    assistant_msg_1 = "".join(text_parts)
    print(f"Assistant: {assistant_msg_1}")
    print()

    # Add to conversation history
    conversation_history.append({"role": "user", "parts": [{"text": user_msg_1}]})
    conversation_history.append({"role": "model", "parts": [{"text": assistant_msg_1}]})

    # Turn 2 (reference previous context)
    user_msg_2 = "Now multiply that result by 2"
    print(f"User: {user_msg_2}")

    # Include conversation history
    contents = conversation_history + [{"role": "user", "parts": [{"text": user_msg_2}]}]

    stream_generator2 = client.aio.models.generate_content_stream(
        model='gemini-2.5-flash-preview-09-2025',
        contents=contents,
        config=config
    )

    # Collect response
    thinking_parts = []
    text_parts = []
    async for chunk in await stream_generator2:
        if not chunk.candidates[0].content.parts:
            continue
        for part in chunk.candidates[0].content.parts:
            if part.thought:
                thinking_parts.append(part.text)
            else:
                text_parts.append(part.text)

    assistant_msg_2 = "".join(text_parts)
    print(f"Assistant: {assistant_msg_2}")
    print()

    # Add to conversation history
    conversation_history.append({"role": "user", "parts": [{"text": user_msg_2}]})
    conversation_history.append({"role": "model", "parts": [{"text": assistant_msg_2}]})

    print("=" * 80)
    print("CONVERSATION HISTORY")
    print("=" * 80)
    print(f"Total messages: {len(conversation_history)}")
    for i, msg in enumerate(conversation_history):
        role = msg["role"]
        text = msg["parts"][0]["text"]
        print(f"{i+1}. {role}: {text[:80]}...")
    print()

    return conversation_history


async def main():
    """Run all tests"""

    print("Starting Gemini Complete Response Tests")
    print("=" * 80)
    print()

    # Test 1: Streaming and manual reconstruction
    print("TEST 1: Manual streaming reconstruction")
    result1 = await test_streaming_and_complete_response()
    print()

    # Test 2: Try 'await stream' pattern
    print("TEST 2: 'await stream' pattern")
    result2 = await test_complete_response_await()
    print()

    # Test 3: Multi-turn conversation
    print("TEST 3: Multi-turn conversation")
    result3 = await test_multi_turn_conversation()
    print()

    print("=" * 80)
    print("ALL TESTS COMPLETED")
    print("=" * 80)

    return {
        "manual_reconstruction": result1,
        "await_stream": result2,
        "conversation_history": result3
    }


if __name__ == "__main__":
    asyncio.run(main())
