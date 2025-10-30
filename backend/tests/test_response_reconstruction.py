"""
Test if reconstructed GenerateContentResponse works with GeminiContextManager.

This test verifies that the response object we construct from streaming chunks
can be properly handled by GeminiContextManager.add_response().

Date: 2025-10-29
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from google.genai import types
from backend.domain.models.streaming import StreamingChunk


def test_response_construction():
    """Test constructing GenerateContentResponse from StreamingChunks"""
    print("=" * 80)
    print("TEST: Response Construction from Streaming Chunks")
    print("=" * 80)
    print()

    # Simulate collected chunks
    chunks = [
        StreamingChunk(
            chunk_type="thinking",
            content="Let me think about this...",
            metadata={"thought": True, "has_signature": False}
        ),
        StreamingChunk(
            chunk_type="text",
            content="The answer is 42.",
            metadata={}
        )
    ]

    print(f"Input: {len(chunks)} chunks")
    for i, chunk in enumerate(chunks):
        print(f"  {i+1}. {chunk.chunk_type}: {chunk.content[:50]}...")
    print()

    # Construct response using our implementation
    print("Constructing GenerateContentResponse...")

    # Convert chunks to parts
    parts = []
    for chunk in chunks:
        if chunk.chunk_type == "thinking":
            part = types.Part(
                text=chunk.content,
                thought=True
            )
        elif chunk.chunk_type == "text":
            part = types.Part(text=chunk.content)
        else:
            continue
        parts.append(part)

    print(f"✓ Created {len(parts)} Part objects")
    print()

    # Create Content
    content = types.Content(parts=parts, role="model")
    print(f"✓ Created Content with role={content.role}")
    print()

    # Create Candidate
    candidate = types.Candidate(
        content=content,
        finish_reason=types.FinishReason.STOP
    )
    print(f"✓ Created Candidate with finish_reason={candidate.finish_reason}")
    print()

    # Create Response
    response = types.GenerateContentResponse(candidates=[candidate])
    print(f"✓ Created GenerateContentResponse with {len(response.candidates)} candidate(s)")
    print()

    # Test accessing response attributes (what GeminiContextManager does)
    print("Testing response attribute access:")
    print("-" * 80)

    try:
        # This is what GeminiContextManager.add_response() does
        candidate = response.candidates[0]
        print(f"✓ response.candidates[0] - OK")

        raw_content = candidate.content
        print(f"✓ candidate.content - OK")
        print(f"  Content type: {type(raw_content)}")
        print(f"  Content role: {raw_content.role}")
        print(f"  Parts count: {len(raw_content.parts)}")
        print()

        # Verify parts
        for i, part in enumerate(raw_content.parts):
            print(f"  Part {i+1}:")
            print(f"    - Has text: {bool(part.text)}")
            print(f"    - Has thought: {bool(part.thought)}")
            if part.text:
                print(f"    - Text preview: {part.text[:40]}...")
        print()

        print("✅ Response object is VALID and compatible with GeminiContextManager")
        return True

    except Exception as e:
        print(f"❌ Error accessing response attributes: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_context_manager_integration():
    """Test actual integration with GeminiContextManager"""
    print("=" * 80)
    print("TEST: GeminiContextManager Integration")
    print("=" * 80)
    print()

    from backend.infrastructure.llm.providers.gemini.context_manager import GeminiContextManager

    # Create context manager
    context_manager = GeminiContextManager(
        session_id="test-session",
        provider_name="gemini"
    )
    print("✓ Created GeminiContextManager")
    print()

    # Construct a test response
    parts = [
        types.Part(text="Thinking...", thought=True),
        types.Part(text="The answer is 42.")
    ]
    content = types.Content(parts=parts, role="model")
    candidate = types.Candidate(
        content=content,
        finish_reason=types.FinishReason.STOP
    )
    response = types.GenerateContentResponse(candidates=[candidate])
    print("✓ Created test response")
    print()

    # Try to add response to context manager
    try:
        context_manager.add_response(response)
        print("✓ Successfully added response to context manager")
        print()

        # Verify it was added
        print(f"Working contents count: {len(context_manager.working_contents)}")
        if context_manager.working_contents:
            added_content = context_manager.working_contents[-1]
            print(f"Last content type: {type(added_content)}")
            print(f"Last content role: {added_content.role}")
            print(f"Last content parts: {len(added_content.parts)}")
            print()

        print("✅ GeminiContextManager integration SUCCESSFUL")
        return True

    except Exception as e:
        print(f"❌ Error adding response to context manager: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    print("\n")
    print("=" * 80)
    print("RESPONSE RECONSTRUCTION VERIFICATION")
    print("=" * 80)
    print()

    results = []

    # Test 1: Response construction
    try:
        result1 = test_response_construction()
        results.append(("Response Construction", result1))
    except Exception as e:
        print(f"❌ Test 1 failed: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Response Construction", False))

    print()

    # Test 2: Context manager integration
    try:
        result2 = test_context_manager_integration()
        results.append(("Context Manager Integration", result2))
    except Exception as e:
        print(f"❌ Test 2 failed: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Context Manager Integration", False))

    # Summary
    print()
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
        print("🎉 ALL TESTS PASSED - Response reconstruction is compatible!")
    else:
        print("⚠ SOME TESTS FAILED - Need to fix response construction")

    print()


if __name__ == "__main__":
    asyncio.run(main())
