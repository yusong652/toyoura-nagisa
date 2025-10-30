"""
Test comparison of different context assembly strategies for Gemini

This test compares:
1. Text-only context (current approach)
2. Complete parts context (with thinking, function_call, thought_signature)
3. Partial parts context (function_call only, no thinking)

Goal: Determine the minimal necessary context structure for multi-turn
conversations with tool calling.

Model: gemini-2.5-flash-preview-09-2025
Date: 2025-10-29
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Any
import json

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from google import genai
from google.genai import types
from config.llm import get_llm_settings


def get_api_key() -> str:
    """Get Google API key from config"""
    llm_settings = get_llm_settings()
    gemini_config = llm_settings.get_gemini_config()
    return gemini_config.google_api_key


def create_weather_tool() -> types.Tool:
    """Create a weather query tool"""
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_weather",
                description="Get current weather for a city",
                parameters={
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "City name"
                        }
                    },
                    "required": ["city"]
                }
            )
        ]
    )


async def test_strategy_text_only():
    """Strategy 1: Text-only context (current approach)"""

    print("=" * 80)
    print("STRATEGY 1: Text-Only Context")
    print("=" * 80)
    print()

    api_key = get_api_key()
    client = genai.Client(api_key=api_key)
    weather_tool = create_weather_tool()

    config = types.GenerateContentConfig(
        tools=[weather_tool],
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
            thinking_budget=2000
        )
    )

    # Turn 1: User asks for weather
    conversation = [{"role": "user", "parts": [{"text": "What's the weather in Paris?"}]}]

    stream1 = client.aio.models.generate_content_stream(
        model='gemini-2.5-flash-preview-09-2025',
        contents=conversation,
        config=config
    )

    # Collect ONLY text (no thinking, no function_call structure)
    text_parts = []
    has_function_call = False
    function_name = None
    function_args = None

    async for chunk in await stream1:
        if not chunk.candidates or not chunk.candidates[0].content:
            continue
        if not chunk.candidates[0].content.parts:
            continue

        for part in chunk.candidates[0].content.parts:
            if part.function_call:
                has_function_call = True
                function_name = part.function_call.name
                function_args = dict(part.function_call.args)
            elif part.text and not part.thought:
                text_parts.append(part.text)

    full_text = "".join(text_parts)

    print(f"Collected text: {full_text}")
    print(f"Has function call: {has_function_call}")
    print()

    if not has_function_call:
        print("✗ Model didn't request function call with text-only context")
        return {"success": False, "reason": "No function call"}

    # Add text-only model response
    conversation.append({"role": "model", "parts": [{"text": full_text}]})

    # Add function result
    conversation.append({
        "role": "user",
        "parts": [{
            "function_response": {
                "name": function_name,
                "response": {"city": "Paris", "temperature": 18, "condition": "Sunny"}
            }
        }]
    })

    # Turn 2: Model processes result
    print("Turn 2: Processing function result with text-only history...")

    try:
        stream2 = client.aio.models.generate_content_stream(
            model='gemini-2.5-flash-preview-09-2025',
            contents=conversation,
            config=config
        )

        response_text = []
        async for chunk in await stream2:
            if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                for part in chunk.candidates[0].content.parts:
                    if part.text and not part.thought:
                        response_text.append(part.text)

        final_response = "".join(response_text)
        print(f"✓ Turn 2 response: {final_response[:100]}...")
        print()

        return {"success": True, "response": final_response}

    except Exception as e:
        print(f"✗ Turn 2 failed: {e}")
        return {"success": False, "error": str(e)}


async def test_strategy_complete_parts():
    """Strategy 2: Complete parts (thinking + function_call + thought_signature)"""

    print("=" * 80)
    print("STRATEGY 2: Complete Parts Context")
    print("=" * 80)
    print()

    api_key = get_api_key()
    client = genai.Client(api_key=api_key)
    weather_tool = create_weather_tool()

    config = types.GenerateContentConfig(
        tools=[weather_tool],
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
            thinking_budget=2000
        )
    )

    # Turn 1
    conversation = [{"role": "user", "parts": [{"text": "What's the weather in Paris?"}]}]

    stream1 = client.aio.models.generate_content_stream(
        model='gemini-2.5-flash-preview-09-2025',
        contents=conversation,
        config=config
    )

    # Collect ALL parts (thinking, text, function_call with thought_signature)
    model_parts = []
    function_name = None

    async for chunk in await stream1:
        if not chunk.candidates or not chunk.candidates[0].content:
            continue
        if not chunk.candidates[0].content.parts:
            continue

        for part in chunk.candidates[0].content.parts:
            if part.thought and part.text:
                # Include thinking part
                model_parts.append({"text": part.text, "thought": True})
            elif part.function_call:
                # Include function call with thought_signature
                fc_part = {
                    "function_call": {
                        "name": part.function_call.name,
                        "args": dict(part.function_call.args)
                    }
                }
                if part.thought_signature:
                    fc_part["thought_signature"] = part.thought_signature
                model_parts.append(fc_part)
                function_name = part.function_call.name
            elif part.text:
                # Include text part
                model_parts.append({"text": part.text})

    print(f"Collected {len(model_parts)} parts")
    for i, part in enumerate(model_parts):
        print(f"  Part {i}: {list(part.keys())}")
    print()

    if not function_name:
        print("✗ Model didn't request function call")
        return {"success": False, "reason": "No function call"}

    # Add complete model response
    conversation.append({"role": "model", "parts": model_parts})

    # Add function result
    conversation.append({
        "role": "user",
        "parts": [{
            "function_response": {
                "name": function_name,
                "response": {"city": "Paris", "temperature": 18, "condition": "Sunny"}
            }
        }]
    })

    # Turn 2
    print("Turn 2: Processing function result with complete history...")

    try:
        stream2 = client.aio.models.generate_content_stream(
            model='gemini-2.5-flash-preview-09-2025',
            contents=conversation,
            config=config
        )

        response_text = []
        async for chunk in await stream2:
            if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                for part in chunk.candidates[0].content.parts:
                    if part.text and not part.thought:
                        response_text.append(part.text)

        final_response = "".join(response_text)
        print(f"✓ Turn 2 response: {final_response[:100]}...")
        print()

        return {"success": True, "response": final_response}

    except Exception as e:
        print(f"✗ Turn 2 failed: {e}")
        return {"success": False, "error": str(e)}


async def test_strategy_function_call_only():
    """Strategy 3: Function call only (no thinking, with thought_signature)"""

    print("=" * 80)
    print("STRATEGY 3: Function Call Only (No Thinking)")
    print("=" * 80)
    print()

    api_key = get_api_key()
    client = genai.Client(api_key=api_key)
    weather_tool = create_weather_tool()

    config = types.GenerateContentConfig(
        tools=[weather_tool],
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
            thinking_budget=2000
        )
    )

    # Turn 1
    conversation = [{"role": "user", "parts": [{"text": "What's the weather in Paris?"}]}]

    stream1 = client.aio.models.generate_content_stream(
        model='gemini-2.5-flash-preview-09-2025',
        contents=conversation,
        config=config
    )

    # Collect function_call and text parts (NO thinking)
    model_parts = []
    function_name = None

    async for chunk in await stream1:
        if not chunk.candidates or not chunk.candidates[0].content:
            continue
        if not chunk.candidates[0].content.parts:
            continue

        for part in chunk.candidates[0].content.parts:
            if part.thought:
                # SKIP thinking parts
                continue
            elif part.function_call:
                # Include function call with thought_signature
                fc_part = {
                    "function_call": {
                        "name": part.function_call.name,
                        "args": dict(part.function_call.args)
                    }
                }
                if part.thought_signature:
                    fc_part["thought_signature"] = part.thought_signature
                model_parts.append(fc_part)
                function_name = part.function_call.name
            elif part.text:
                # Include text part
                model_parts.append({"text": part.text})

    print(f"Collected {len(model_parts)} parts (no thinking)")
    for i, part in enumerate(model_parts):
        print(f"  Part {i}: {list(part.keys())}")
    print()

    if not function_name:
        print("✗ Model didn't request function call")
        return {"success": False, "reason": "No function call"}

    # Add model response (without thinking)
    conversation.append({"role": "model", "parts": model_parts})

    # Add function result
    conversation.append({
        "role": "user",
        "parts": [{
            "function_response": {
                "name": function_name,
                "response": {"city": "Paris", "temperature": 18, "condition": "Sunny"}
            }
        }]
    })

    # Turn 2
    print("Turn 2: Processing function result without thinking in history...")

    try:
        stream2 = client.aio.models.generate_content_stream(
            model='gemini-2.5-flash-preview-09-2025',
            contents=conversation,
            config=config
        )

        response_text = []
        async for chunk in await stream2:
            if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                for part in chunk.candidates[0].content.parts:
                    if part.text and not part.thought:
                        response_text.append(part.text)

        final_response = "".join(response_text)
        print(f"✓ Turn 2 response: {final_response[:100]}...")
        print()

        return {"success": True, "response": final_response}

    except Exception as e:
        print(f"✗ Turn 2 failed: {e}")
        return {"success": False, "error": str(e)}


async def main():
    """Run all strategy tests"""

    print("Starting Context Strategy Comparison Tests")
    print("=" * 80)
    print()

    # Test all strategies
    result1 = await test_strategy_text_only()
    result2 = await test_strategy_complete_parts()
    result3 = await test_strategy_function_call_only()

    # Summary
    print("\n" + "=" * 80)
    print("COMPARISON SUMMARY")
    print("=" * 80)
    print()

    print("Strategy 1 (Text-Only):")
    print(f"  Success: {'✓ YES' if result1['success'] else '✗ NO'}")
    if not result1['success']:
        print(f"  Reason: {result1.get('reason', result1.get('error'))}")
    print()

    print("Strategy 2 (Complete Parts):")
    print(f"  Success: {'✓ YES' if result2['success'] else '✗ NO'}")
    if not result2['success']:
        print(f"  Reason: {result2.get('reason', result2.get('error'))}")
    print()

    print("Strategy 3 (Function Call Only, No Thinking):")
    print(f"  Success: {'✓ YES' if result3['success'] else '✗ NO'}")
    if not result3['success']:
        print(f"  Reason: {result3.get('reason', result3.get('error'))}")
    print()

    print("=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)
    print()

    success_count = sum([result1['success'], result2['success'], result3['success']])

    if success_count == 3:
        print("✓ All strategies work!")
        print()
        print("Recommendation: Use Strategy 3 (Function Call Only)")
        print("  Reason: Minimal context, includes necessary fields")
        print("  - Include function_call parts with thought_signature")
        print("  - Include text parts")
        print("  - SKIP thinking parts (not needed for context)")
    elif result2['success']:
        print("⚠ Only complete parts work")
        print()
        print("Recommendation: Use Strategy 2 (Complete Parts)")
        print("  - MUST include thinking parts")
        print("  - MUST include thought_signature")
        print("  - This is the safest approach")
    elif result3['success']:
        print("✓ Function call strategy works")
        print()
        print("Recommendation: Use Strategy 3")
        print("  - Include function_call with thought_signature")
        print("  - Include text parts")
        print("  - Thinking parts not needed")
    else:
        print("✗ Need further investigation")
        print("  None of the simple strategies worked reliably")

    return {
        "text_only": result1,
        "complete_parts": result2,
        "function_call_only": result3
    }


if __name__ == "__main__":
    asyncio.run(main())
