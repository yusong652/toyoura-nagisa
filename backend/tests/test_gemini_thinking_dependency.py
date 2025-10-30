"""
Test if Gemini uses thinking content from previous turns

This test designs a scenario where the follow-up question REQUIRES
information from the previous turn's thinking process, not just the
final text answer.

Goal: Verify if we MUST preserve thinking parts in context.

Test Design:
1. Ask a complex question that requires reasoning
2. Model thinks and gives an answer
3. Ask a follow-up that refers to the reasoning process itself
4. Compare two strategies:
   - With thinking in context
   - Without thinking in context

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


def get_api_key() -> str:
    """Get Google API key"""
    llm_settings = get_llm_settings()
    gemini_config = llm_settings.get_gemini_config()
    return gemini_config.google_api_key


async def test_with_thinking_context():
    """Test WITH thinking parts preserved in context"""

    print("=" * 80)
    print("TEST 1: WITH Thinking in Context")
    print("=" * 80)
    print()

    api_key = get_api_key()
    client = genai.Client(api_key=api_key)

    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
            thinking_budget=3000
        )
    )

    # Turn 1: Complex reasoning question
    prompt1 = """I have 3 boxes. Box A contains 5 red balls and 3 blue balls.
Box B contains 4 red balls and 6 blue balls. Box C contains 2 red balls and 8 blue balls.
If I randomly pick one box and then randomly pick one ball from that box,
what is the probability of getting a red ball? Please think through this step by step."""

    print("Turn 1:")
    print("-" * 80)
    print(f"User: {prompt1[:100]}...")
    print()

    conversation = [{"role": "user", "parts": [{"text": prompt1}]}]

    stream1 = client.aio.models.generate_content_stream(
        model='gemini-2.5-flash-preview-09-2025',
        contents=conversation,
        config=config
    )

    # Collect ALL parts including thinking
    turn1_thinking_parts = []
    turn1_text_parts = []
    all_turn1_parts = []

    async for chunk in await stream1:
        if not chunk.candidates or not chunk.candidates[0].content:
            continue
        if not chunk.candidates[0].content.parts:
            continue

        for part in chunk.candidates[0].content.parts:
            if part.thought and part.text:
                # Thinking part - PRESERVE
                turn1_thinking_parts.append(part.text)
                all_turn1_parts.append({"text": part.text, "thought": True})
                print(f"[THINKING] {part.text[:80]}...")
            elif part.text:
                # Text part
                turn1_text_parts.append(part.text)
                all_turn1_parts.append({"text": part.text})
                print(f"[TEXT] {part.text[:80]}...")

    turn1_full_text = "".join(turn1_text_parts)
    turn1_full_thinking = "".join(turn1_thinking_parts)

    print()
    print("Turn 1 Summary:")
    print(f"  Thinking length: {len(turn1_full_thinking)} chars")
    print(f"  Text length: {len(turn1_full_text)} chars")
    print(f"  Final answer: {turn1_full_text[:150]}...")
    print()

    # Add Turn 1 to history WITH thinking
    conversation.append({"role": "model", "parts": all_turn1_parts})

    # Turn 2: Follow-up that requires reasoning from Turn 1
    prompt2 = """In your previous reasoning, you mentioned calculating probabilities for each box.
Can you explain why you chose that specific approach?
What other methods did you consider and why did you reject them?"""

    print("Turn 2:")
    print("-" * 80)
    print(f"User: {prompt2[:100]}...")
    print()

    conversation.append({"role": "user", "parts": [{"text": prompt2}]})

    stream2 = client.aio.models.generate_content_stream(
        model='gemini-2.5-flash-preview-09-2025',
        contents=conversation,
        config=config
    )

    turn2_text_parts = []
    turn2_has_reference = False

    async for chunk in await stream2:
        if not chunk.candidates or not chunk.candidates[0].content:
            continue
        if not chunk.candidates[0].content.parts:
            continue

        for part in chunk.candidates[0].content.parts:
            if part.text and not part.thought:
                turn2_text_parts.append(part.text)
                # Check if model references its previous reasoning
                if any(keyword in part.text.lower() for keyword in
                       ["previous", "earlier", "mentioned", "calculated", "reasoning", "approach"]):
                    turn2_has_reference = True

    turn2_full_text = "".join(turn2_text_parts)

    print("Turn 2 Response:")
    print("-" * 80)
    print(turn2_full_text[:300] + "...")
    print()

    print("Analysis:")
    print(f"  Response length: {len(turn2_full_text)} chars")
    print(f"  References previous reasoning: {'✓ YES' if turn2_has_reference else '✗ NO'}")
    print()

    return {
        "turn1_thinking_length": len(turn1_full_thinking),
        "turn1_text_length": len(turn1_full_text),
        "turn2_text_length": len(turn2_full_text),
        "turn2_references_reasoning": turn2_has_reference,
        "turn2_response": turn2_full_text
    }


async def test_without_thinking_context():
    """Test WITHOUT thinking parts in context (only text)"""

    print("=" * 80)
    print("TEST 2: WITHOUT Thinking in Context")
    print("=" * 80)
    print()

    api_key = get_api_key()
    client = genai.Client(api_key=api_key)

    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
            thinking_budget=3000
        )
    )

    # Turn 1: Same complex question
    prompt1 = """I have 3 boxes. Box A contains 5 red balls and 3 blue balls.
Box B contains 4 red balls and 6 blue balls. Box C contains 2 red balls and 8 blue balls.
If I randomly pick one box and then randomly pick one ball from that box,
what is the probability of getting a red ball? Please think through this step by step."""

    print("Turn 1:")
    print("-" * 80)
    print(f"User: {prompt1[:100]}...")
    print()

    conversation = [{"role": "user", "parts": [{"text": prompt1}]}]

    stream1 = client.aio.models.generate_content_stream(
        model='gemini-2.5-flash-preview-09-2025',
        contents=conversation,
        config=config
    )

    # Collect ONLY text (skip thinking)
    turn1_thinking_parts = []
    turn1_text_parts = []

    async for chunk in await stream1:
        if not chunk.candidates or not chunk.candidates[0].content:
            continue
        if not chunk.candidates[0].content.parts:
            continue

        for part in chunk.candidates[0].content.parts:
            if part.thought and part.text:
                # Thinking part - SKIP (but track for comparison)
                turn1_thinking_parts.append(part.text)
                print(f"[THINKING - SKIPPED] {part.text[:80]}...")
            elif part.text:
                # Text part
                turn1_text_parts.append(part.text)
                print(f"[TEXT] {part.text[:80]}...")

    turn1_full_text = "".join(turn1_text_parts)
    turn1_full_thinking = "".join(turn1_thinking_parts)

    print()
    print("Turn 1 Summary:")
    print(f"  Thinking length: {len(turn1_full_thinking)} chars (SKIPPED)")
    print(f"  Text length: {len(turn1_full_text)} chars")
    print(f"  Final answer: {turn1_full_text[:150]}...")
    print()

    # Add Turn 1 to history WITHOUT thinking (text only)
    conversation.append({"role": "model", "parts": [{"text": turn1_full_text}]})

    # Turn 2: Same follow-up question
    prompt2 = """In your previous reasoning, you mentioned calculating probabilities for each box.
Can you explain why you chose that specific approach?
What other methods did you consider and why did you reject them?"""

    print("Turn 2:")
    print("-" * 80)
    print(f"User: {prompt2[:100]}...")
    print()

    conversation.append({"role": "user", "parts": [{"text": prompt2}]})

    stream2 = client.aio.models.generate_content_stream(
        model='gemini-2.5-flash-preview-09-2025',
        contents=conversation,
        config=config
    )

    turn2_text_parts = []
    turn2_has_reference = False
    turn2_seems_confused = False

    async for chunk in await stream2:
        if not chunk.candidates or not chunk.candidates[0].content:
            continue
        if not chunk.candidates[0].content.parts:
            continue

        for part in chunk.candidates[0].content.parts:
            if part.text and not part.thought:
                turn2_text_parts.append(part.text)
                # Check references and confusion
                lower_text = part.text.lower()
                if any(keyword in lower_text for keyword in
                       ["previous", "earlier", "mentioned", "calculated", "reasoning"]):
                    turn2_has_reference = True
                if any(keyword in lower_text for keyword in
                       ["don't recall", "didn't mention", "not sure", "unclear", "cannot find"]):
                    turn2_seems_confused = True

    turn2_full_text = "".join(turn2_text_parts)

    print("Turn 2 Response:")
    print("-" * 80)
    print(turn2_full_text[:300] + "...")
    print()

    print("Analysis:")
    print(f"  Response length: {len(turn2_full_text)} chars")
    print(f"  References previous reasoning: {'✓ YES' if turn2_has_reference else '✗ NO'}")
    print(f"  Seems confused/unable to recall: {'✗ YES' if turn2_seems_confused else '✓ NO'}")
    print()

    return {
        "turn1_thinking_length": len(turn1_full_thinking),
        "turn1_text_length": len(turn1_full_text),
        "turn2_text_length": len(turn2_full_text),
        "turn2_references_reasoning": turn2_has_reference,
        "turn2_seems_confused": turn2_seems_confused,
        "turn2_response": turn2_full_text
    }


async def main():
    """Run both tests and compare"""

    print("Starting Thinking Dependency Tests")
    print("=" * 80)
    print()
    print("Goal: Verify if thinking parts are needed in context")
    print("Method: Ask follow-up that requires previous thinking process")
    print()

    # Run both tests
    result_with = await test_with_thinking_context()
    print("\n" + "=" * 80 + "\n")
    result_without = await test_without_thinking_context()

    # Compare results
    print("\n" + "=" * 80)
    print("COMPARISON & CONCLUSION")
    print("=" * 80)
    print()

    print("Turn 1 (both tests similar):")
    print(f"  Thinking: {result_with['turn1_thinking_length']} chars")
    print(f"  Text: {result_with['turn1_text_length']} chars")
    print()

    print("Turn 2 (critical difference):")
    print("-" * 80)
    print()

    print("WITH thinking in context:")
    print(f"  Response length: {result_with['turn2_text_length']} chars")
    print(f"  References reasoning: {'✓ YES' if result_with['turn2_references_reasoning'] else '✗ NO'}")
    print(f"  Preview: {result_with['turn2_response'][:200]}...")
    print()

    print("WITHOUT thinking in context:")
    print(f"  Response length: {result_without['turn2_text_length']} chars")
    print(f"  References reasoning: {'✓ YES' if result_without['turn2_references_reasoning'] else '✗ NO'}")
    print(f"  Seems confused: {'✗ YES' if result_without['turn2_seems_confused'] else '✓ NO'}")
    print(f"  Preview: {result_without['turn2_response'][:200]}...")
    print()

    print("=" * 80)
    print("FINAL VERDICT")
    print("=" * 80)
    print()

    # Determine if thinking is necessary
    quality_with = result_with['turn2_references_reasoning'] and result_with['turn2_text_length'] > 100
    quality_without = result_without['turn2_references_reasoning'] and not result_without['turn2_seems_confused']

    if quality_with and not quality_without:
        print("✓ THINKING PARTS ARE NECESSARY")
        print()
        print("Evidence:")
        print("  - With thinking: Model can reference previous reasoning")
        print("  - Without thinking: Model cannot properly answer")
        print()
        print("RECOMMENDATION:")
        print("  MUST preserve thinking parts in conversation context")
        print("  Structure: {\"text\": \"...\", \"thought\": True}")
    elif quality_with and quality_without:
        print("⚠ BOTH WORK BUT WITH THINKING IS BETTER")
        print()
        print("Evidence:")
        print("  - Both produce valid responses")
        print("  - With thinking may provide more detailed/accurate answers")
        print()
        print("RECOMMENDATION:")
        print("  SHOULD preserve thinking parts for better quality")
        print("  But not strictly necessary for functionality")
    else:
        print("✗ UNCLEAR - NEED MORE INVESTIGATION")
        print()
        print("The test results are inconclusive.")
        print("May need different test scenarios.")

    return {
        "with_thinking": result_with,
        "without_thinking": result_without
    }


if __name__ == "__main__":
    asyncio.run(main())
