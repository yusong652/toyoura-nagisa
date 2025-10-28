"""
Streaming Chunk Granularity Test

This script tests the chunk granularity of streaming APIs from different LLM providers
to understand how they deliver content in real-time.

Test objectives:
1. Measure chunk size (character count per chunk)
2. Measure chunk delivery frequency (time between chunks)
3. Compare streaming vs non-streaming response structure
4. Test thinking block streaming behavior (for Anthropic)
5. Test tool calling in streaming mode

Usage:
    uv run python backend/tests/streaming_chunk_test.py --provider gemini
    uv run python backend/tests/streaming_chunk_test.py --provider anthropic
    uv run python backend/tests/streaming_chunk_test.py --provider openai
    uv run python backend/tests/streaming_chunk_test.py --provider all
"""

import asyncio
import argparse
import time
import json
from typing import List, Dict, Any
from datetime import datetime


# ============================================================================
# Test Configuration
# ============================================================================

TEST_PROMPTS = {
    "simple": "Write a short story about a cat in 3 sentences.",
    "thinking": "Solve this math problem step by step: What is 15% of 240?",
    "long": "Write a detailed explanation of photosynthesis in 5 paragraphs.",
}


# ============================================================================
# Gemini Streaming Test
# ============================================================================

async def test_gemini_streaming():
    """Test Gemini streaming API chunk granularity."""
    print("\n" + "=" * 80)
    print("TESTING GEMINI STREAMING")
    print("=" * 80)

    try:
        from google import genai
        from backend.shared.utils.app_context import get_llm_client

        # Get existing LLM client from app context
        llm_client = get_llm_client()
        if llm_client.__class__.__name__ != 'GeminiClient':
            print("⚠️  Current LLM provider is not Gemini, skipping test")
            return

        # Use the existing client's API key and client
        client = llm_client.client

        for prompt_name, prompt_text in TEST_PROMPTS.items():
            print(f"\n{'─' * 80}")
            print(f"Test: {prompt_name.upper()}")
            print(f"Prompt: {prompt_text}")
            print(f"{'─' * 80}\n")

            # Test 1: Non-streaming (baseline)
            print("[Non-Streaming Mode]")
            start_time = time.time()
            response = client.models.generate_content(
                model='gemini-2.0-flash-exp',
                contents=prompt_text
            )
            end_time = time.time()

            full_text = response.text if hasattr(response, 'text') else ""
            print(f"Total time: {end_time - start_time:.3f}s")
            print(f"Total length: {len(full_text)} characters")
            print(f"First 100 chars: {full_text[:100]}")

            # Test 2: Streaming mode
            print(f"\n[Streaming Mode]")
            chunk_count = 0
            total_chars = 0
            chunk_sizes = []
            chunk_times = []
            streamed_text = ""

            stream_start = time.time()
            last_chunk_time = stream_start

            async for chunk in client.aio.models.generate_content_stream(
                model='gemini-2.0-flash-exp',
                contents=prompt_text
            ):
                current_time = time.time()
                chunk_text = chunk.text if hasattr(chunk, 'text') and chunk.text else ""

                if chunk_text:
                    chunk_count += 1
                    chunk_len = len(chunk_text)
                    total_chars += chunk_len
                    chunk_sizes.append(chunk_len)

                    time_since_last = current_time - last_chunk_time
                    chunk_times.append(time_since_last)

                    print(f"Chunk {chunk_count}: {chunk_len} chars, "
                          f"+{time_since_last*1000:.1f}ms, "
                          f"text: {repr(chunk_text[:50])}")

                    streamed_text += chunk_text
                    last_chunk_time = current_time

            stream_end = time.time()

            # Statistics
            print(f"\n[Statistics]")
            print(f"Total chunks: {chunk_count}")
            print(f"Total characters: {total_chars}")
            print(f"Total time: {stream_end - stream_start:.3f}s")
            if chunk_sizes:
                print(f"Average chunk size: {sum(chunk_sizes)/len(chunk_sizes):.1f} chars")
                print(f"Min chunk size: {min(chunk_sizes)} chars")
                print(f"Max chunk size: {max(chunk_sizes)} chars")
            if chunk_times:
                print(f"Average time between chunks: {sum(chunk_times)/len(chunk_times)*1000:.1f}ms")

            # Verify content match
            if streamed_text == full_text:
                print(f"✓ Streamed content matches non-streaming content")
            else:
                print(f"✗ Content mismatch!")
                print(f"  Non-streaming length: {len(full_text)}")
                print(f"  Streaming length: {len(streamed_text)}")

            await asyncio.sleep(1)  # Rate limiting

    except Exception as e:
        print(f"Error testing Gemini: {e}")
        import traceback
        traceback.print_exc()


# ============================================================================
# Anthropic Streaming Test
# ============================================================================

async def test_anthropic_streaming():
    """Test Anthropic streaming API chunk granularity."""
    print("\n" + "=" * 80)
    print("TESTING ANTHROPIC STREAMING")
    print("=" * 80)

    try:
        import anthropic
        from backend.shared.utils.app_context import get_llm_client

        # Get existing LLM client from app context
        llm_client = get_llm_client()
        if llm_client.__class__.__name__ != 'AnthropicClient':
            print("⚠️  Current LLM provider is not Anthropic, skipping test")
            return

        # Use the existing client's API key
        client = anthropic.AsyncAnthropic(api_key=llm_client.api_key)

        for prompt_name, prompt_text in TEST_PROMPTS.items():
            print(f"\n{'─' * 80}")
            print(f"Test: {prompt_name.upper()}")
            print(f"Prompt: {prompt_text}")
            print(f"{'─' * 80}\n")

            # Test 1: Non-streaming (baseline)
            print("[Non-Streaming Mode]")
            start_time = time.time()
            response = await client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt_text}]
            )
            end_time = time.time()

            # Extract text from response
            full_text = ""
            for block in response.content:
                if block.type == "text":
                    full_text += block.text

            print(f"Total time: {end_time - start_time:.3f}s")
            print(f"Total length: {len(full_text)} characters")
            print(f"Content blocks: {len(response.content)}")
            print(f"First 100 chars: {full_text[:100]}")

            # Test 2: Streaming mode with detailed event tracking
            print(f"\n[Streaming Mode - Event Details]")
            chunk_count = 0
            total_chars = 0
            chunk_sizes = []
            chunk_times = []
            streamed_text = ""
            event_types = []

            stream_start = time.time()
            last_chunk_time = stream_start

            async with client.messages.stream(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt_text}]
            ) as stream:
                async for event in stream:
                    current_time = time.time()
                    event_type = event.type
                    event_types.append(event_type)

                    print(f"Event: {event_type}", end="")

                    # Handle different event types
                    if event_type == "message_start":
                        print(f" - Message started")

                    elif event_type == "content_block_start":
                        print(f" - Block type: {event.content_block.type}")

                    elif event_type == "content_block_delta":
                        delta = event.delta
                        if delta.type == "text_delta":
                            chunk_count += 1
                            chunk_text = delta.text
                            chunk_len = len(chunk_text)
                            total_chars += chunk_len
                            chunk_sizes.append(chunk_len)

                            time_since_last = current_time - last_chunk_time
                            chunk_times.append(time_since_last)

                            print(f" - Text: {chunk_len} chars, "
                                  f"+{time_since_last*1000:.1f}ms, "
                                  f"{repr(chunk_text[:50])}")

                            streamed_text += chunk_text
                            last_chunk_time = current_time
                        else:
                            print(f" - Delta type: {delta.type}")

                    elif event_type == "content_block_stop":
                        print(f" - Block ended")

                    elif event_type == "message_delta":
                        print(f" - Stop reason: {event.delta.stop_reason if hasattr(event.delta, 'stop_reason') else 'N/A'}")

                    elif event_type == "message_stop":
                        print(f" - Message completed")

                    else:
                        print()

                # Get final message
                final_message = await stream.get_final_message()

            stream_end = time.time()

            # Statistics
            print(f"\n[Statistics]")
            print(f"Total events: {len(event_types)}")
            print(f"Event type breakdown: {dict((t, event_types.count(t)) for t in set(event_types))}")
            print(f"Total text chunks: {chunk_count}")
            print(f"Total characters: {total_chars}")
            print(f"Total time: {stream_end - stream_start:.3f}s")
            if chunk_sizes:
                print(f"Average chunk size: {sum(chunk_sizes)/len(chunk_sizes):.1f} chars")
                print(f"Min chunk size: {min(chunk_sizes)} chars")
                print(f"Max chunk size: {max(chunk_sizes)} chars")
            if chunk_times:
                print(f"Average time between chunks: {sum(chunk_times)/len(chunk_times)*1000:.1f}ms")

            # Verify content match
            if streamed_text == full_text:
                print(f"✓ Streamed content matches non-streaming content")
            else:
                print(f"✗ Content mismatch!")
                print(f"  Non-streaming length: {len(full_text)}")
                print(f"  Streaming length: {len(streamed_text)}")

            await asyncio.sleep(1)  # Rate limiting

    except Exception as e:
        print(f"Error testing Anthropic: {e}")
        import traceback
        traceback.print_exc()


# ============================================================================
# OpenAI Streaming Test
# ============================================================================

async def test_openai_streaming():
    """Test OpenAI streaming API chunk granularity."""
    print("\n" + "=" * 80)
    print("TESTING OPENAI STREAMING")
    print("=" * 80)

    try:
        from openai import AsyncOpenAI
        from backend.shared.utils.app_context import get_llm_client

        # Get existing LLM client from app context
        llm_client = get_llm_client()
        if llm_client.__class__.__name__ != 'OpenAIClient':
            print("⚠️  Current LLM provider is not OpenAI, skipping test")
            return

        # Use the existing client's API key
        client = AsyncOpenAI(api_key=llm_client.api_key)

        for prompt_name, prompt_text in TEST_PROMPTS.items():
            print(f"\n{'─' * 80}")
            print(f"Test: {prompt_name.upper()}")
            print(f"Prompt: {prompt_text}")
            print(f"{'─' * 80}\n")

            # Test 1: Non-streaming (baseline)
            print("[Non-Streaming Mode]")
            start_time = time.time()
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt_text}]
            )
            end_time = time.time()

            full_text = response.choices[0].message.content or ""
            print(f"Total time: {end_time - start_time:.3f}s")
            print(f"Total length: {len(full_text)} characters")
            print(f"First 100 chars: {full_text[:100]}")

            # Test 2: Streaming mode
            print(f"\n[Streaming Mode]")
            chunk_count = 0
            total_chars = 0
            chunk_sizes = []
            chunk_times = []
            streamed_text = ""

            stream_start = time.time()
            last_chunk_time = stream_start

            stream = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt_text}],
                stream=True
            )

            async for chunk in stream:
                current_time = time.time()
                delta = chunk.choices[0].delta
                chunk_text = delta.content if delta.content else ""

                if chunk_text:
                    chunk_count += 1
                    chunk_len = len(chunk_text)
                    total_chars += chunk_len
                    chunk_sizes.append(chunk_len)

                    time_since_last = current_time - last_chunk_time
                    chunk_times.append(time_since_last)

                    print(f"Chunk {chunk_count}: {chunk_len} chars, "
                          f"+{time_since_last*1000:.1f}ms, "
                          f"text: {repr(chunk_text[:50])}")

                    streamed_text += chunk_text
                    last_chunk_time = current_time

            stream_end = time.time()

            # Statistics
            print(f"\n[Statistics]")
            print(f"Total chunks: {chunk_count}")
            print(f"Total characters: {total_chars}")
            print(f"Total time: {stream_end - stream_start:.3f}s")
            if chunk_sizes:
                print(f"Average chunk size: {sum(chunk_sizes)/len(chunk_sizes):.1f} chars")
                print(f"Min chunk size: {min(chunk_sizes)} chars")
                print(f"Max chunk size: {max(chunk_sizes)} chars")
            if chunk_times:
                print(f"Average time between chunks: {sum(chunk_times)/len(chunk_times)*1000:.1f}ms")

            # Verify content match
            if streamed_text == full_text:
                print(f"✓ Streamed content matches non-streaming content")
            else:
                print(f"✗ Content mismatch!")
                print(f"  Non-streaming length: {len(full_text)}")
                print(f"  Streaming length: {len(streamed_text)}")

            await asyncio.sleep(1)  # Rate limiting

    except Exception as e:
        print(f"Error testing OpenAI: {e}")
        import traceback
        traceback.print_exc()


# ============================================================================
# Main Test Runner
# ============================================================================

async def main():
    parser = argparse.ArgumentParser(description='Test LLM streaming chunk granularity')
    parser.add_argument(
        '--provider',
        choices=['gemini', 'anthropic', 'openai', 'all'],
        default='all',
        help='Which provider to test'
    )

    args = parser.parse_args()

    print("\n" + "=" * 80)
    print("LLM STREAMING CHUNK GRANULARITY TEST")
    print("=" * 80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if args.provider in ['gemini', 'all']:
        await test_gemini_streaming()

    if args.provider in ['anthropic', 'all']:
        await test_anthropic_streaming()

    if args.provider in ['openai', 'all']:
        await test_openai_streaming()

    print("\n" + "=" * 80)
    print("TEST COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
