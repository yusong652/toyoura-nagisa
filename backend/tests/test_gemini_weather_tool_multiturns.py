"""
Test Gemini multi-turn conversation with weather tool

This test simulates a complete multi-turn dialogue with function calling
to verify:
1. How parts are structured in responses with function calls
2. Complete response assembly for context
3. All fields in each part (text, thought, thought_signature, function_call, etc.)

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
    """Create a weather query tool for testing"""
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_weather",
                description="Get current weather information for a city",
                parameters={
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "The city name (e.g., 'Tokyo', 'New York')"
                        },
                        "unit": {
                            "type": "string",
                            "enum": ["celsius", "fahrenheit"],
                            "description": "Temperature unit"
                        }
                    },
                    "required": ["city"]
                }
            ),
            types.FunctionDeclaration(
                name="get_forecast",
                description="Get weather forecast for next N days",
                parameters={
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "The city name"
                        },
                        "days": {
                            "type": "integer",
                            "description": "Number of days for forecast (1-7)",
                            "minimum": 1,
                            "maximum": 7
                        }
                    },
                    "required": ["city", "days"]
                }
            )
        ]
    )


def simulate_weather_api(function_name: str, args: Dict) -> Dict:
    """Simulate weather API responses"""
    if function_name == "get_weather":
        city = args.get("city", "Unknown")
        unit = args.get("unit", "celsius")
        temp = 22 if unit == "celsius" else 72
        return {
            "city": city,
            "temperature": temp,
            "unit": unit,
            "condition": "Partly Cloudy",
            "humidity": 65,
            "wind_speed": 15
        }
    elif function_name == "get_forecast":
        city = args.get("city", "Unknown")
        days = args.get("days", 3)
        forecast = []
        for i in range(days):
            forecast.append({
                "day": i + 1,
                "temperature_high": 25 + i,
                "temperature_low": 18 + i,
                "condition": "Sunny" if i % 2 == 0 else "Cloudy"
            })
        return {
            "city": city,
            "forecast": forecast
        }
    return {"error": "Unknown function"}


def print_part_details(part, part_idx: int, chunk_idx: int):
    """Print detailed information about a part"""
    print(f"\n{'='*80}")
    print(f"Chunk #{chunk_idx}, Part #{part_idx}")
    print(f"{'='*80}")

    # Basic fields
    print(f"  thought: {part.thought}")
    print(f"  thought_signature: {part.thought_signature}")

    # Text content
    if part.text:
        print(f"  text: {part.text[:100]}..." if len(part.text) > 100 else f"  text: {part.text}")
    else:
        print(f"  text: None")

    # Function call
    if part.function_call:
        print(f"  ✓ FUNCTION_CALL:")
        print(f"    name: {part.function_call.name}")
        print(f"    args: {dict(part.function_call.args)}")
    else:
        print(f"  function_call: None")

    # Function response
    if part.function_response:
        print(f"  ✓ FUNCTION_RESPONSE:")
        print(f"    name: {part.function_response.name}")
        print(f"    response: {part.function_response.response}")
    else:
        print(f"  function_response: None")

    # What fields are actually set
    print(f"  model_fields_set: {part.model_fields_set}")
    print()


async def test_weather_multiturns():
    """Test complete multi-turn conversation with weather tool"""

    print("=" * 80)
    print("MULTI-TURN WEATHER CONVERSATION TEST")
    print("=" * 80)
    print()

    api_key = get_api_key()
    client = genai.Client(api_key=api_key)

    # Create weather tool
    weather_tool = create_weather_tool()

    # Configuration with thinking and tools
    config = types.GenerateContentConfig(
        tools=[weather_tool],
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
            thinking_budget=2000
        ),
        temperature=1.0
    )

    # Conversation history
    conversation_history = []

    # ===== TURN 1: Ask for weather =====
    print("\n" + "=" * 80)
    print("TURN 1: User asks for weather")
    print("=" * 80)

    user_message_1 = "What's the weather like in Tokyo? Please use celsius."
    print(f"User: {user_message_1}")
    print()

    # Add to history
    conversation_history.append({
        "role": "user",
        "parts": [{"text": user_message_1}]
    })

    # Stream response
    stream_generator = client.aio.models.generate_content_stream(
        model='gemini-2.5-flash-preview-09-2025',
        contents=conversation_history,
        config=config
    )

    # Collect all parts for this turn
    turn1_parts = []
    chunk_count = 0

    print("Streaming Turn 1 response...")
    print("-" * 80)

    async for chunk in await stream_generator:
        chunk_count += 1

        if not chunk.candidates or not chunk.candidates[0].content:
            continue

        if not chunk.candidates[0].content.parts:
            print(f"\nChunk #{chunk_count}: NO PARTS (final chunk)")
            print(f"  finish_reason: {chunk.candidates[0].finish_reason}")
            continue

        for part_idx, part in enumerate(chunk.candidates[0].content.parts):
            print_part_details(part, part_idx, chunk_count)

            # Collect complete part information
            part_data = {
                "text": part.text,
                "thought": part.thought,
                "thought_signature": part.thought_signature,
                "function_call": None,
                "function_response": None,
                "model_fields_set": part.model_fields_set
            }

            if part.function_call:
                part_data["function_call"] = {
                    "name": part.function_call.name,
                    "args": dict(part.function_call.args)
                }

            if part.function_response:
                part_data["function_response"] = {
                    "name": part.function_response.name,
                    "response": part.function_response.response
                }

            turn1_parts.append(part_data)

    print("\n" + "-" * 80)
    print(f"Turn 1 complete. Total chunks: {chunk_count}, Total parts: {len(turn1_parts)}")
    print()

    # Analyze Turn 1 parts
    print("Turn 1 Parts Analysis:")
    print("-" * 80)
    thinking_parts = [p for p in turn1_parts if p["thought"]]
    text_parts = [p for p in turn1_parts if p["text"] and not p["thought"]]
    function_call_parts = [p for p in turn1_parts if p["function_call"]]

    print(f"  Thinking parts: {len(thinking_parts)}")
    print(f"  Text parts: {len(text_parts)}")
    print(f"  Function call parts: {len(function_call_parts)}")
    print()

    # Check if model wants to call function
    if function_call_parts:
        print("✓ Model requested function call:")
        for fc_part in function_call_parts:
            print(f"  Function: {fc_part['function_call']['name']}")
            print(f"  Args: {fc_part['function_call']['args']}")
        print()

        # Add model's function call request to history
        # Build model response parts
        model_parts = []
        for part_data in turn1_parts:
            if part_data["thought"]:
                # Include thinking parts
                model_parts.append({"text": part_data["text"], "thought": True})
            elif part_data["function_call"]:
                # Include function call
                model_parts.append({
                    "function_call": {
                        "name": part_data["function_call"]["name"],
                        "args": part_data["function_call"]["args"]
                    }
                })
            elif part_data["text"]:
                # Include text
                model_parts.append({"text": part_data["text"]})

        conversation_history.append({
            "role": "model",
            "parts": model_parts
        })

        # Simulate function execution
        print("Simulating function execution...")
        print("-" * 80)
        for fc_part in function_call_parts:
            func_name = fc_part["function_call"]["name"]
            func_args = fc_part["function_call"]["args"]
            result = simulate_weather_api(func_name, func_args)
            print(f"Function: {func_name}")
            print(f"Result: {json.dumps(result, indent=2)}")
            print()

            # Add function result to history
            conversation_history.append({
                "role": "user",
                "parts": [{
                    "function_response": {
                        "name": func_name,
                        "response": result
                    }
                }]
            })

        # ===== TURN 2: Model processes function result =====
        print("\n" + "=" * 80)
        print("TURN 2: Model processes function result")
        print("=" * 80)
        print()

        stream_generator2 = client.aio.models.generate_content_stream(
            model='gemini-2.5-flash-preview-09-2025',
            contents=conversation_history,
            config=config
        )

        turn2_parts = []
        chunk_count = 0

        print("Streaming Turn 2 response...")
        print("-" * 80)

        async for chunk in await stream_generator2:
            chunk_count += 1

            if not chunk.candidates or not chunk.candidates[0].content:
                continue

            if not chunk.candidates[0].content.parts:
                print(f"\nChunk #{chunk_count}: NO PARTS")
                continue

            for part_idx, part in enumerate(chunk.candidates[0].content.parts):
                print_part_details(part, part_idx, chunk_count)

                # Collect part
                part_data = {
                    "text": part.text,
                    "thought": part.thought,
                    "model_fields_set": part.model_fields_set
                }
                turn2_parts.append(part_data)

        print("\n" + "-" * 80)
        print(f"Turn 2 complete. Total chunks: {chunk_count}, Total parts: {len(turn2_parts)}")
        print()

        # Assemble Turn 2 response for context
        turn2_text_parts = [p["text"] for p in turn2_parts if p["text"] and not p["thought"]]
        turn2_full_text = "".join(turn2_text_parts)

        print("Turn 2 Response (text only):")
        print("-" * 80)
        print(turn2_full_text)
        print()

        # Add to history
        conversation_history.append({
            "role": "model",
            "parts": [{"text": turn2_full_text}]
        })

    # ===== TURN 3: Follow-up question =====
    print("\n" + "=" * 80)
    print("TURN 3: User asks follow-up question")
    print("=" * 80)

    user_message_3 = "How about the forecast for the next 3 days?"
    print(f"User: {user_message_3}")
    print()

    conversation_history.append({
        "role": "user",
        "parts": [{"text": user_message_3}]
    })

    stream_generator3 = client.aio.models.generate_content_stream(
        model='gemini-2.5-flash-preview-09-2025',
        contents=conversation_history,
        config=config
    )

    turn3_parts = []
    chunk_count = 0

    print("Streaming Turn 3 response...")
    print("-" * 80)

    async for chunk in await stream_generator3:
        chunk_count += 1

        if not chunk.candidates or not chunk.candidates[0].content:
            continue

        if not chunk.candidates[0].content.parts:
            continue

        for part_idx, part in enumerate(chunk.candidates[0].content.parts):
            print_part_details(part, part_idx, chunk_count)

            part_data = {
                "text": part.text,
                "thought": part.thought,
                "function_call": None,
                "model_fields_set": part.model_fields_set
            }

            if part.function_call:
                part_data["function_call"] = {
                    "name": part.function_call.name,
                    "args": dict(part.function_call.args)
                }

            turn3_parts.append(part_data)

    print("\n" + "-" * 80)
    print(f"Turn 3 complete. Total chunks: {chunk_count}, Total parts: {len(turn3_parts)}")
    print()

    # Check for function calls in Turn 3
    function_call_parts_3 = [p for p in turn3_parts if p["function_call"]]
    if function_call_parts_3:
        print("✓ Model requested another function call:")
        for fc_part in function_call_parts_3:
            print(f"  Function: {fc_part['function_call']['name']}")
            print(f"  Args: {fc_part['function_call']['args']}")
        print()

        # Process function call (similar to Turn 1-2)
        # ... (omitted for brevity, same pattern)

    # ===== FINAL SUMMARY =====
    print("\n" + "=" * 80)
    print("CONVERSATION SUMMARY")
    print("=" * 80)
    print()

    print(f"Total conversation turns: {len([msg for msg in conversation_history if msg['role'] == 'user'])}")
    print(f"Total messages in history: {len(conversation_history)}")
    print()

    print("Complete conversation history:")
    print("-" * 80)
    for i, msg in enumerate(conversation_history):
        role = msg["role"]
        parts = msg["parts"]
        print(f"{i+1}. {role.upper()}: {len(parts)} parts")

        for j, part in enumerate(parts):
            if "text" in part:
                text_preview = part["text"][:80] + "..." if len(part["text"]) > 80 else part["text"]
                print(f"   Part {j}: text = {text_preview}")
            elif "function_call" in part:
                print(f"   Part {j}: function_call = {part['function_call']['name']}({part['function_call']['args']})")
            elif "function_response" in part:
                print(f"   Part {j}: function_response = {part['function_response']['name']}")
            elif "thought" in part:
                print(f"   Part {j}: thought = True")
    print()

    return {
        "turn1_parts": turn1_parts,
        "turn2_parts": turn2_parts,
        "turn3_parts": turn3_parts,
        "conversation_history": conversation_history
    }


async def main():
    """Run the test"""

    print("Starting Gemini Weather Tool Multi-Turn Test")
    print("=" * 80)
    print()

    result = await test_weather_multiturns()

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    print()

    print("Key Findings:")
    print("-" * 80)
    print(f"1. Turn 1 collected {len(result['turn1_parts'])} parts")
    print(f"2. Turn 2 collected {len(result['turn2_parts'])} parts")
    print(f"3. Turn 3 collected {len(result['turn3_parts'])} parts")
    print(f"4. Final conversation history: {len(result['conversation_history'])} messages")
    print()

    # Check what fields were actually used
    all_parts = result['turn1_parts'] + result['turn2_parts'] + result['turn3_parts']

    has_thought_signature = any(p.get("thought_signature") for p in all_parts)
    has_function_calls = any(p.get("function_call") for p in all_parts)
    has_thinking = any(p.get("thought") for p in all_parts)

    print("Field Usage Summary:")
    print("-" * 80)
    print(f"  thought_signature present: {'✓ YES' if has_thought_signature else '✗ NO'}")
    print(f"  function_call present: {'✓ YES' if has_function_calls else '✗ NO'}")
    print(f"  thinking parts present: {'✓ YES' if has_thinking else '✗ NO'}")
    print()

    print("=" * 80)
    print("CONTEXT ASSEMBLY RECOMMENDATION")
    print("=" * 80)
    print()

    if has_function_calls:
        print("✓ Function calls detected!")
        print()
        print("For context assembly with function calls, preserve:")
        print("  1. Text parts (non-thinking)")
        print("  2. Function call parts")
        print("  3. Function response parts")
        print()
        print("Example format:")
        print('  {"role": "model", "parts": [')
        print('    {"text": "..."},')
        print('    {"function_call": {"name": "...", "args": {...}}}')
        print('  ]}')
    else:
        print("Current text-only approach is sufficient.")

    return result


if __name__ == "__main__":
    asyncio.run(main())
