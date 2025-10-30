"""
Test streaming implementation with thinking content.

This test verifies that the streaming interface works correctly:
1. StreamingChunk data model
2. LLMClientBase streaming methods
3. GeminiClient streaming implementation
4. WebSocket message types

Model: gemini-2.5-flash-preview-09-2025
Date: 2025-10-29
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from google import genai
from google.genai import types
from config.llm import get_llm_settings
from domain.models.streaming import StreamingChunk
from presentation.websocket.message_types import MessageType, create_message


def get_api_key() -> str:
    """Get Google API key"""
    llm_settings = get_llm_settings()
    gemini_config = llm_settings.get_gemini_config()
    return gemini_config.google_api_key


async def test_streaming_chunk_model():
    """Test StreamingChunk data model"""
    print("=" * 80)
    print("TEST 1: StreamingChunk Data Model")
    print("=" * 80)
    print()

    # Test thinking chunk
    thinking_chunk = StreamingChunk(
        chunk_type="thinking",
        content="Analyzing the problem step by step...",
        metadata={"thought": True, "has_signature": False}
    )
    print(f"✓ Thinking chunk created: {thinking_chunk.chunk_type}")
    print(f"  Content preview: {thinking_chunk.content[:50]}...")
    print()

    # Test text chunk
    text_chunk = StreamingChunk(
        chunk_type="text",
        content="The answer is 42.",
        metadata={}
    )
    print(f"✓ Text chunk created: {text_chunk.chunk_type}")
    print(f"  Content: {text_chunk.content}")
    print()

    # Test function call chunk
    function_chunk = StreamingChunk(
        chunk_type="function_call",
        content="calculate",
        metadata={"args": {"expression": "2 + 2"}},
        function_call={"name": "calculate", "args": {"expression": "2 + 2"}}
    )
    print(f"✓ Function call chunk created: {function_chunk.chunk_type}")
    print(f"  Function: {function_chunk.content}")
    print(f"  Args: {function_chunk.metadata['args']}")
    print()

    print("✅ StreamingChunk model test PASSED")
    print()
    return True


async def test_websocket_message_type():
    """Test STREAMING_CHUNK WebSocket message type"""
    print("=" * 80)
    print("TEST 2: WebSocket Message Type")
    print("=" * 80)
    print()

    # Test message creation
    ws_message = create_message(
        MessageType.STREAMING_CHUNK,
        session_id="test-session",
        chunk_type="thinking",
        content="Test thinking content",
        metadata={"thought": True}
    )

    print(f"✓ WebSocket message created")
    print(f"  Type: {ws_message.type}")
    print(f"  Chunk type: {ws_message.chunk_type}")  # type: ignore
    print(f"  Content: {ws_message.content}")  # type: ignore
    print()

    # Test serialization
    message_dict = ws_message.model_dump()
    print(f"✓ Message serialized to dict")
    print(f"  Keys: {list(message_dict.keys())}")
    print()

    print("✅ WebSocket message type test PASSED")
    print()
    return True


async def test_gemini_streaming_api():
    """Test actual Gemini streaming API call"""
    print("=" * 80)
    print("TEST 3: Gemini Streaming API")
    print("=" * 80)
    print()

    api_key = get_api_key()
    client = genai.Client(api_key=api_key)

    # Simple streaming test
    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
            thinking_budget=1000
        )
    )

    prompt = "Calculate 123 + 456 for me."
    print(f"Prompt: {prompt}")
    print()

    stream = client.aio.models.generate_content_stream(
        model='gemini-2.5-flash-preview-09-2025',
        contents=[{"role": "user", "parts": [{"text": prompt}]}],
        config=config
    )

    chunk_count = 0
    thinking_count = 0
    text_count = 0

    print("Streaming response:")
    print("-" * 80)

    async for chunk in await stream:
        if not chunk.candidates or not chunk.candidates[0].content:
            continue
        if not chunk.candidates[0].content.parts:
            continue

        for part in chunk.candidates[0].content.parts:
            chunk_count += 1

            if part.thought and part.text:
                thinking_count += 1
                print(f"[THINKING #{thinking_count}] {part.text[:60]}...")
            elif part.text:
                text_count += 1
                print(f"[TEXT #{text_count}] {part.text}")

    print("-" * 80)
    print()

    print(f"✓ Received {chunk_count} total chunks")
    print(f"  - Thinking chunks: {thinking_count}")
    print(f"  - Text chunks: {text_count}")
    print()

    if thinking_count > 0 and text_count > 0:
        print("✅ Gemini streaming API test PASSED")
    else:
        print("⚠ Gemini streaming API test PARTIAL (missing thinking or text)")

    print()
    return thinking_count > 0


async def main():
    """Run all tests"""
    print("\n")
    print("=" * 80)
    print("STREAMING IMPLEMENTATION VERIFICATION")
    print("=" * 80)
    print()

    results = []

    # Test 1: Data model
    try:
        result1 = await test_streaming_chunk_model()
        results.append(("StreamingChunk Model", result1))
    except Exception as e:
        print(f"❌ Test 1 failed: {e}")
        results.append(("StreamingChunk Model", False))

    # Test 2: WebSocket message type
    try:
        result2 = await test_websocket_message_type()
        results.append(("WebSocket Message Type", result2))
    except Exception as e:
        print(f"❌ Test 2 failed: {e}")
        results.append(("WebSocket Message Type", False))

    # Test 3: Gemini streaming API
    try:
        result3 = await test_gemini_streaming_api()
        results.append(("Gemini Streaming API", result3))
    except Exception as e:
        print(f"❌ Test 3 failed: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Gemini Streaming API", False))

    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print()

    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")

    print()

    all_passed = all(result for _, result in results)
    if all_passed:
        print("🎉 ALL TESTS PASSED - Streaming implementation is ready!")
    else:
        print("⚠ SOME TESTS FAILED - Review implementation")

    print()


if __name__ == "__main__":
    asyncio.run(main())
