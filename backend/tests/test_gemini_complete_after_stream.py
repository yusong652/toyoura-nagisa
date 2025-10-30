"""
Test Gemini complete response after streaming

This test verifies if we can get complete response by awaiting stream
after the async for loop completes, which would simplify context assembly.

Key questions:
1. Can we await stream after async for loop?
2. Does it return a complete response object?
3. Can we extract full text for context from it?
4. Does it work in a finally block?

Model: gemini-2.5-flash-preview-09-2025
Date: 2025-10-29
"""

import asyncio
import os
from typing import List, Dict, Any
from google import genai
from google.genai import types


def get_api_key() -> str:
    """Get Google API key from environment or config"""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
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
            raise ValueError(f"Cannot get Google API key: {e}")
    return api_key


async def test_await_after_loop():
    """Test awaiting stream after async for loop completes"""

    print("=" * 80)
    print("TEST 1: Inspect All Part Fields")
    print("=" * 80)
    print()

    api_key = get_api_key()
    client = genai.Client(api_key=api_key)

    prompt = "What is 2 + 2?"

    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
            thinking_budget=2000
        )
    )

    # Create stream
    stream_generator = client.aio.models.generate_content_stream(
        model='gemini-2.5-flash-preview-09-2025',
        contents=prompt,
        config=config
    )

    # Iterate through stream and print ALL fields
    print("Phase 1: Inspecting all part fields")
    print("-" * 80)
    chunk_count = 0
    async for chunk in await stream_generator:
        chunk_count += 1
        if not chunk.candidates[0].content.parts:
            print(f"\nChunk #{chunk_count}: NO PARTS (likely final chunk)")
            print(f"  finish_reason: {chunk.candidates[0].finish_reason}")
            continue

        for part_idx, part in enumerate(chunk.candidates[0].content.parts):
            part_type = "THINKING" if part.thought else "TEXT"
            print(f"\nChunk #{chunk_count}, Part #{part_idx} ({part_type}):")
            print(f"  Type: {type(part)}")

            # Print all attributes
            print(f"  Available attributes: {dir(part)}")
            print()

            # Print specific fields
            print(f"  text: {part.text[:100] if part.text else None}...")
            print(f"  thought: {part.thought}")
            print(f"  thought_signature: {part.thought_signature}")
            print(f"  function_call: {part.function_call}")
            print(f"  function_response: {part.function_response}")
            print(f"  executable_code: {part.executable_code}")
            print(f"  code_execution_result: {part.code_execution_result}")
            print(f"  inline_data: {part.inline_data}")
            print(f"  file_data: {part.file_data}")
            print(f"  video_metadata: {part.video_metadata}")

            # Check for any other attributes
            print(f"\n  All non-private attributes:")
            for attr in dir(part):
                if not attr.startswith('_'):
                    try:
                        value = getattr(part, attr)
                        if not callable(value):
                            print(f"    {attr}: {type(value).__name__} = {str(value)[:80]}")
                    except:
                        pass

    print()
    print(f"Streaming complete. Total chunks: {chunk_count}")
    print()

    # Second: try to await the same stream generator
    print("Phase 2: Attempting to await stream after loop")
    print("-" * 80)
    try:
        # This is the KEY TEST
        complete_response = await stream_generator

        print("✓ Successfully awaited stream!")
        print()
        print(f"Response type: {type(complete_response)}")
        print(f"Has .text: {hasattr(complete_response, 'text')}")
        print(f"Has .candidates: {hasattr(complete_response, 'candidates')}")
        print()

        # Try to access response data
        if hasattr(complete_response, 'text'):
            print(f"complete_response.text: {complete_response.text}")
            print()

        if hasattr(complete_response, 'candidates'):
            print(f"Candidates: {len(complete_response.candidates)}")
            if complete_response.candidates:
                candidate = complete_response.candidates[0]
                print(f"Candidate.content: {candidate.content}")
                print()

                if candidate.content and candidate.content.parts:
                    print(f"Parts count: {len(candidate.content.parts)}")
                    for i, part in enumerate(candidate.content.parts):
                        part_type = "THINKING" if part.thought else "TEXT"
                        print(f"  Part {i} ({part_type}): {len(part.text)} chars")
                        if not part.thought:
                            print(f"    Content: {part.text}")
                    print()

        return complete_response

    except Exception as e:
        print(f"✗ Failed to await stream: {type(e).__name__}: {e}")
        return None


async def test_await_in_finally():
    """Test awaiting stream in a finally block (recommended pattern)"""

    print("=" * 80)
    print("TEST 2: Await Stream in Finally Block")
    print("=" * 80)
    print()

    api_key = get_api_key()
    client = genai.Client(api_key=api_key)

    prompt = "Calculate 5 * 6"

    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
            thinking_budget=2000
        )
    )

    # Create stream
    stream_generator = client.aio.models.generate_content_stream(
        model='gemini-2.5-flash-preview-09-2025',
        contents=prompt,
        config=config
    )

    complete_response = None
    chunk_count = 0

    try:
        print("Phase 1: Streaming chunks")
        print("-" * 80)
        async for chunk in await stream_generator:
            chunk_count += 1
            if not chunk.candidates[0].content.parts:
                continue
            for part in chunk.candidates[0].content.parts:
                part_type = "THINKING" if part.thought else "TEXT"
                print(f"Chunk #{chunk_count} ({part_type}): {len(part.text)} chars")

        print()
        print(f"Streaming complete. Total chunks: {chunk_count}")

    finally:
        print()
        print("Phase 2: Finally block - attempting to get complete response")
        print("-" * 80)
        try:
            complete_response = await stream_generator
            print("✓ Successfully awaited stream in finally block!")
            print()

            if hasattr(complete_response, 'text') and complete_response.text:
                print(f"Complete text: {complete_response.text}")
                print()

            if hasattr(complete_response, 'candidates') and complete_response.candidates:
                candidate = complete_response.candidates[0]
                if candidate.content and candidate.content.parts:
                    print(f"Total parts: {len(candidate.content.parts)}")
                    full_text = ""
                    for part in candidate.content.parts:
                        if not part.thought:
                            full_text += part.text
                    print(f"Extracted full text: {full_text}")
                    print()

        except Exception as e:
            print(f"✗ Failed in finally block: {type(e).__name__}: {e}")

    return complete_response


async def test_new_stream_for_complete():
    """Test creating a fresh stream to get complete response"""

    print("=" * 80)
    print("TEST 3: Fresh Stream for Complete Response")
    print("=" * 80)
    print()

    api_key = get_api_key()
    client = genai.Client(api_key=api_key)

    prompt = "What is the capital of France?"

    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
            thinking_budget=2000
        )
    )

    print("Strategy: Use stream for real-time, manual assembly for context")
    print("-" * 80)
    print()

    # Stream for real-time display
    stream_generator = client.aio.models.generate_content_stream(
        model='gemini-2.5-flash-preview-09-2025',
        contents=prompt,
        config=config
    )

    # Manual assembly (current working approach)
    text_parts = []
    chunk_count = 0

    async for chunk in await stream_generator:
        chunk_count += 1
        if not chunk.candidates[0].content.parts:
            continue
        for part in chunk.candidates[0].content.parts:
            part_type = "THINKING" if part.thought else "TEXT"
            print(f"Chunk #{chunk_count} ({part_type}): {len(part.text)} chars")
            if not part.thought:
                text_parts.append(part.text)

    full_text = "".join(text_parts)
    print()
    print(f"Manually assembled text: {full_text}")
    print()

    return {
        "method": "manual_assembly",
        "full_text": full_text,
        "chunk_count": chunk_count
    }


async def test_context_format():
    """Test extracting context in the correct format for multi-turn conversation"""

    print("=" * 80)
    print("TEST 4: Context Format for Multi-turn Conversation")
    print("=" * 80)
    print()

    api_key = get_api_key()
    client = genai.Client(api_key=api_key)

    prompt = "List 3 primary colors"

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

    # Collect for context (only text, not thinking)
    text_parts = []

    print("Collecting response for context")
    print("-" * 80)
    async for chunk in await stream_generator:
        if not chunk.candidates[0].content.parts:
            continue
        for part in chunk.candidates[0].content.parts:
            if not part.thought:  # Only text parts for context
                text_parts.append(part.text)

    full_text = "".join(text_parts)

    # Format for Gemini context
    context_entry = {
        "role": "model",
        "parts": [{"text": full_text}]
    }

    print()
    print("Context entry for conversation history:")
    print("-" * 80)
    print(f"Role: {context_entry['role']}")
    print(f"Text: {context_entry['parts'][0]['text']}")
    print()

    # Test using this in a follow-up request
    print("Testing context in follow-up request")
    print("-" * 80)

    conversation_history = [
        {"role": "user", "parts": [{"text": prompt}]},
        context_entry
    ]

    follow_up_prompt = "Now explain why these are primary colors"

    stream_generator2 = client.aio.models.generate_content_stream(
        model='gemini-2.5-flash-preview-09-2025',
        contents=conversation_history + [{"role": "user", "parts": [{"text": follow_up_prompt}]}],
        config=config
    )

    response_parts = []
    async for chunk in await stream_generator2:
        if not chunk.candidates[0].content.parts:
            continue
        for part in chunk.candidates[0].content.parts:
            if not part.thought:
                response_parts.append(part.text)

    follow_up_response = "".join(response_parts)
    print(f"Follow-up response: {follow_up_response}")
    print()

    return {
        "context_format": context_entry,
        "follow_up_successful": len(follow_up_response) > 0
    }


async def main():
    """Run all tests"""

    print("Starting Gemini Complete Response After Stream Tests")
    print("=" * 80)
    print()

    # Test 1: Await after loop
    result1 = await test_await_after_loop()
    print("\n" + "=" * 80 + "\n")

    # Test 2: Await in finally block
    result2 = await test_await_in_finally()
    print("\n" + "=" * 80 + "\n")

    # Test 3: Manual assembly (baseline)
    result3 = await test_new_stream_for_complete()
    print("\n" + "=" * 80 + "\n")

    # Test 4: Context format
    result4 = await test_context_format()
    print("\n" + "=" * 80 + "\n")

    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print(f"Test 1 (Await after loop): {'✓ PASS' if result1 else '✗ FAIL'}")
    print(f"Test 2 (Await in finally): {'✓ PASS' if result2 else '✗ FAIL'}")
    print(f"Test 3 (Manual assembly): {'✓ PASS' if result3 else '✗ FAIL'}")
    print(f"Test 4 (Context format): {'✓ PASS' if result4 and result4['follow_up_successful'] else '✗ FAIL'}")
    print()

    # Recommendation
    print("=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)
    print()

    if result1 and hasattr(result1, 'candidates'):
        print("✓ RECOMMENDED: Use 'await stream' after async for loop")
        print("  - Simplifies code")
        print("  - Provides complete response object")
        print("  - Compatible with context assembly")
    else:
        print("✓ RECOMMENDED: Continue with manual assembly")
        print("  - Proven to work reliably")
        print("  - Full control over content collection")
        print("  - No additional API call needed")

    return {
        "await_after_loop": result1,
        "await_in_finally": result2,
        "manual_assembly": result3,
        "context_format": result4
    }


if __name__ == "__main__":
    asyncio.run(main())
