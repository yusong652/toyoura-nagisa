"""
Simple Streaming Chunk Granularity Test (Standalone)

This is a simplified standalone version that doesn't require the full app context.
It directly reads API keys from environment variables.

Usage:
    # Set environment variables first
    export GOOGLE_API_KEY="your-key"
    export ANTHROPIC_API_KEY="your-key"
    export OPENAI_API_KEY="your-key"

    # Run tests
    uv run python backend/tests/streaming_chunk_test_simple.py --provider gemini
    uv run python backend/tests/streaming_chunk_test_simple.py --provider anthropic
    uv run python backend/tests/streaming_chunk_test_simple.py --provider openai
"""

import asyncio
import argparse
import time
import os
from datetime import datetime


# Test prompts
TEST_PROMPTS = {
    "simple": "Write a short story about a cat in 3 sentences.",
    "thinking": "Solve this math problem step by step: What is 15% of 240?",
}


async def test_gemini_streaming():
    """Test Gemini streaming API chunk granularity."""
    print("\n" + "=" * 80)
    print("TESTING GEMINI STREAMING")
    print("=" * 80)

    try:
        from google import genai
        # Try to get API key from backend config
        try:
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
            from config.llm import get_llm_settings
            settings = get_llm_settings()
            gemini_config = settings.get_gemini_config()
            api_key = gemini_config.google_api_key
            print(f"✓ Using API key from backend config")
        except Exception:
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                print("❌ Could not get API key from config or environment, skipping test")
                return
            print(f"✓ Using API key from environment variable")

        client = genai.Client(api_key=api_key)

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

            stream = await client.aio.models.generate_content_stream(
                model='gemini-2.0-flash-exp',
                contents=prompt_text
            )
            async for chunk in stream:
                current_time = time.time()
                chunk_text = chunk.text if hasattr(chunk, 'text') and chunk.text else ""

                if chunk_text:
                    chunk_count += 1
                    chunk_len = len(chunk_text)
                    total_chars += chunk_len
                    chunk_sizes.append(chunk_len)

                    time_since_last = current_time - last_chunk_time
                    chunk_times.append(time_since_last)

                    print(f"Chunk {chunk_count:3d}: {chunk_len:3d} chars, "
                          f"+{time_since_last*1000:6.1f}ms, "
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

            await asyncio.sleep(1)

    except Exception as e:
        print(f"Error testing Gemini: {e}")
        import traceback
        traceback.print_exc()


async def test_anthropic_streaming():
    """Test Anthropic streaming API chunk granularity."""
    print("\n" + "=" * 80)
    print("TESTING ANTHROPIC STREAMING")
    print("=" * 80)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY environment variable not set, skipping test")
        return

    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=api_key)

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

            full_text = ""
            for block in response.content:
                if block.type == "text":
                    full_text += block.text

            print(f"Total time: {end_time - start_time:.3f}s")
            print(f"Total length: {len(full_text)} characters")
            print(f"First 100 chars: {full_text[:100]}")

            # Test 2: Streaming mode
            print(f"\n[Streaming Mode - Detailed Events]")
            chunk_count = 0
            total_chars = 0
            chunk_sizes = []
            chunk_times = []
            streamed_text = ""
            event_count = 0

            stream_start = time.time()
            last_chunk_time = stream_start

            async with client.messages.stream(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt_text}]
            ) as stream:
                async for event in stream:
                    current_time = time.time()
                    event_count += 1
                    event_type = event.type

                    if event_type == "content_block_delta":
                        delta = event.delta
                        if delta.type == "text_delta":
                            chunk_count += 1
                            chunk_text = delta.text
                            chunk_len = len(chunk_text)
                            total_chars += chunk_len
                            chunk_sizes.append(chunk_len)

                            time_since_last = current_time - last_chunk_time
                            chunk_times.append(time_since_last)

                            print(f"Chunk {chunk_count:3d}: {chunk_len:3d} chars, "
                                  f"+{time_since_last*1000:6.1f}ms, "
                                  f"text: {repr(chunk_text[:50])}")

                            streamed_text += chunk_text
                            last_chunk_time = current_time
                    else:
                        print(f"Event [{event_count:3d}]: {event_type}")

            stream_end = time.time()

            # Statistics
            print(f"\n[Statistics]")
            print(f"Total events: {event_count}")
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

            await asyncio.sleep(1)

    except Exception as e:
        print(f"Error testing Anthropic: {e}")
        import traceback
        traceback.print_exc()


async def test_openai_streaming():
    """Test OpenAI streaming API chunk granularity."""
    print("\n" + "=" * 80)
    print("TESTING OPENAI STREAMING")
    print("=" * 80)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY environment variable not set, skipping test")
        return

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key)

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

                    print(f"Chunk {chunk_count:3d}: {chunk_len:3d} chars, "
                          f"+{time_since_last*1000:6.1f}ms, "
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

            await asyncio.sleep(1)

    except Exception as e:
        print(f"Error testing OpenAI: {e}")
        import traceback
        traceback.print_exc()


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
    print("LLM STREAMING CHUNK GRANULARITY TEST (STANDALONE)")
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
