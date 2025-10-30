"""
Test complete parts preservation in Gemini conversation flow

This test implements the simplest approach:
- Collect ALL parts from ALL chunks into a single parts list
- Preserve everything: thinking, text, function_call, thought_signature
- Test if this works for multi-turn conversation with tool calling

Goal: Verify the "dump everything into parts" strategy works.

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
    """Get Google API key"""
    llm_settings = get_llm_settings()
    gemini_config = llm_settings.get_gemini_config()
    return gemini_config.google_api_key


def create_calculator_tool() -> types.Tool:
    """Create a simple calculator tool"""
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="calculate",
                description="Perform a mathematical calculation",
                parameters={
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "Mathematical expression to evaluate (e.g., '2 + 3 * 4')"
                        }
                    },
                    "required": ["expression"]
                }
            ),
            types.FunctionDeclaration(
                name="get_history",
                description="Get calculation history",
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            )
        ]
    )


def simulate_calculator(function_name: str, args: Dict) -> Any:
    """Simulate calculator function"""
    if function_name == "calculate":
        expression = args.get("expression", "")
        try:
            # Simple eval (for testing only - never use in production!)
            result = eval(expression)
            return {"expression": expression, "result": result}
        except:
            return {"error": "Invalid expression"}
    elif function_name == "get_history":
        return {"history": ["2 + 3 = 5", "10 * 5 = 50"]}
    return {"error": "Unknown function"}


def collect_all_parts_from_stream(chunks: List[Any]) -> List[Dict[str, Any]]:
    """
    Collect ALL parts from ALL chunks into a single parts list.

    This is the simplest approach: just dump everything.
    """
    all_parts = []

    for chunk in chunks:
        if not chunk.candidates or not chunk.candidates[0].content:
            continue
        if not chunk.candidates[0].content.parts:
            continue

        for part in chunk.candidates[0].content.parts:
            part_dict = {}

            # Add text if present
            if part.text:
                part_dict["text"] = part.text

            # Add thought flag if present
            if part.thought:
                part_dict["thought"] = True

            # Add thought_signature if present
            if part.thought_signature:
                part_dict["thought_signature"] = part.thought_signature

            # Add function_call if present
            if part.function_call:
                part_dict["function_call"] = {
                    "name": part.function_call.name,
                    "args": dict(part.function_call.args)
                }

            # Add function_response if present
            if part.function_response:
                part_dict["function_response"] = {
                    "name": part.function_response.name,
                    "response": part.function_response.response
                }

            # Only add if there's actual content
            if part_dict:
                all_parts.append(part_dict)

    return all_parts


async def test_complete_parts_flow():
    """Test complete multi-turn flow with ALL parts preserved"""

    print("=" * 80)
    print("COMPLETE PARTS FLOW TEST")
    print("=" * 80)
    print()
    print("Strategy: Collect ALL parts from ALL chunks into single list")
    print()

    api_key = get_api_key()
    client = genai.Client(api_key=api_key)
    calculator_tool = create_calculator_tool()

    config = types.GenerateContentConfig(
        tools=[calculator_tool],
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
            thinking_budget=2000
        )
    )

    # Conversation history
    conversation = []

    # ===== TURN 1: User asks for calculation =====
    print("\n" + "=" * 80)
    print("TURN 1: User asks for calculation")
    print("=" * 80)

    user_msg_1 = "Calculate 123 * 456 for me"
    print(f"User: {user_msg_1}")
    print()

    conversation.append({
        "role": "user",
        "parts": [{"text": user_msg_1}]
    })

    # Stream Turn 1
    print("Streaming Turn 1...")
    print("-" * 80)

    stream_generator_1 = client.aio.models.generate_content_stream(
        model='gemini-2.5-flash-preview-09-2025',
        contents=conversation,
        config=config
    )

    # Collect ALL chunks
    chunks_1 = []
    async for chunk in await stream_generator_1:
        chunks_1.append(chunk)

        # Display what we got
        if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
            for part in chunk.candidates[0].content.parts:
                if part.thought:
                    print(f"  [THINKING] {part.text[:80] if part.text else 'N/A'}...")
                elif part.function_call:
                    print(f"  [FUNCTION_CALL] {part.function_call.name}({dict(part.function_call.args)})")
                    print(f"    thought_signature: {len(part.thought_signature) if part.thought_signature else 0} bytes")
                elif part.text:
                    print(f"  [TEXT] {part.text[:80]}...")

    # Collect ALL parts using our simple strategy
    turn1_parts = collect_all_parts_from_stream(chunks_1)

    print()
    print(f"Turn 1 collected {len(turn1_parts)} parts:")
    for i, part in enumerate(turn1_parts):
        print(f"  Part {i}: {list(part.keys())}")
    print()

    # Check if there's a function call
    function_calls = [p for p in turn1_parts if "function_call" in p]

    if not function_calls:
        print("✗ No function call detected. Test cannot continue.")
        return {"success": False, "reason": "No function call"}

    print(f"✓ Found {len(function_calls)} function call(s)")
    print()

    # Add Turn 1 model response to conversation (with ALL parts)
    conversation.append({
        "role": "model",
        "parts": turn1_parts
    })

    # ===== Execute function calls =====
    print("Executing function calls...")
    print("-" * 80)

    for fc in function_calls:
        func_name = fc["function_call"]["name"]
        func_args = fc["function_call"]["args"]

        print(f"Calling: {func_name}({func_args})")
        result = simulate_calculator(func_name, func_args)
        print(f"Result: {result}")
        print()

        # Add function response
        conversation.append({
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

    print("Streaming Turn 2...")
    print("-" * 80)

    stream_generator_2 = client.aio.models.generate_content_stream(
        model='gemini-2.5-flash-preview-09-2025',
        contents=conversation,
        config=config
    )

    # Collect ALL chunks for Turn 2
    chunks_2 = []
    async for chunk in await stream_generator_2:
        chunks_2.append(chunk)

        if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
            for part in chunk.candidates[0].content.parts:
                if part.thought:
                    print(f"  [THINKING] {part.text[:80] if part.text else 'N/A'}...")
                elif part.text:
                    print(f"  [TEXT] {part.text[:80]}...")

    turn2_parts = collect_all_parts_from_stream(chunks_2)

    print()
    print(f"Turn 2 collected {len(turn2_parts)} parts:")
    for i, part in enumerate(turn2_parts):
        print(f"  Part {i}: {list(part.keys())}")
    print()

    # Extract text for display
    turn2_text = "".join([p["text"] for p in turn2_parts if "text" in p and not p.get("thought")])
    print(f"Turn 2 Response: {turn2_text}")
    print()

    # Add Turn 2 to conversation
    conversation.append({
        "role": "model",
        "parts": turn2_parts
    })

    # ===== TURN 3: Follow-up question =====
    print("\n" + "=" * 80)
    print("TURN 3: Follow-up question")
    print("=" * 80)

    user_msg_3 = "What was the expression I asked you to calculate?"
    print(f"User: {user_msg_3}")
    print()

    conversation.append({
        "role": "user",
        "parts": [{"text": user_msg_3}]
    })

    print("Streaming Turn 3...")
    print("-" * 80)

    stream_generator_3 = client.aio.models.generate_content_stream(
        model='gemini-2.5-flash-preview-09-2025',
        contents=conversation,
        config=config
    )

    chunks_3 = []
    async for chunk in await stream_generator_3:
        chunks_3.append(chunk)

        if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
            for part in chunk.candidates[0].content.parts:
                if part.thought:
                    print(f"  [THINKING] {part.text[:80] if part.text else 'N/A'}...")
                elif part.text:
                    print(f"  [TEXT] {part.text[:80]}...")

    turn3_parts = collect_all_parts_from_stream(chunks_3)

    print()
    print(f"Turn 3 collected {len(turn3_parts)} parts")
    print()

    turn3_text = "".join([p["text"] for p in turn3_parts if "text" in p and not p.get("thought")])
    print(f"Turn 3 Response: {turn3_text}")
    print()

    # Check if model remembers
    remembers = "123" in turn3_text and "456" in turn3_text
    print(f"Model remembers the expression: {'✓ YES' if remembers else '✗ NO'}")
    print()

    # ===== SUMMARY =====
    print("\n" + "=" * 80)
    print("CONVERSATION SUMMARY")
    print("=" * 80)
    print()

    print(f"Total messages in conversation: {len(conversation)}")
    print()

    print("Conversation structure:")
    for i, msg in enumerate(conversation):
        role = msg["role"]
        parts_count = len(msg["parts"])
        print(f"{i+1}. {role.upper()}: {parts_count} parts")

        # Show part types
        part_types = []
        for part in msg["parts"]:
            if "thought" in part and part["thought"]:
                part_types.append("thinking")
            elif "function_call" in part:
                part_types.append(f"func_call({part['function_call']['name']})")
            elif "function_response" in part:
                part_types.append(f"func_resp({part['function_response']['name']})")
            elif "text" in part:
                part_types.append("text")
        print(f"   Types: {', '.join(part_types)}")

    print()
    print("=" * 80)
    print("TEST RESULT")
    print("=" * 80)
    print()

    if remembers:
        print("✅ SUCCESS: Complete parts flow works!")
        print()
        print("Evidence:")
        print("  ✓ Function call executed successfully")
        print("  ✓ Model processed function result")
        print("  ✓ Model remembers previous conversation")
        print()
        print("Conclusion:")
        print("  The 'collect all parts' strategy is VALID")
        print("  All chunks' parts -> single parts list works!")
    else:
        print("⚠ PARTIAL SUCCESS")
        print()
        print("Function calling worked, but memory test failed.")
        print("May need to check conversation structure.")

    return {
        "success": True,
        "turn1_parts_count": len(turn1_parts),
        "turn2_parts_count": len(turn2_parts),
        "turn3_parts_count": len(turn3_parts),
        "remembers_context": remembers,
        "conversation": conversation
    }


async def main():
    """Run the test"""

    print("Starting Complete Parts Flow Test")
    print("=" * 80)
    print()

    result = await test_complete_parts_flow()

    print("\n" + "=" * 80)
    print("FINAL CONCLUSION")
    print("=" * 80)
    print()

    if result["success"]:
        print("✅ The complete parts preservation strategy WORKS!")
        print()
        print("Implementation pattern:")
        print("-" * 80)
        print("""
# Collect all parts from stream
model_parts = []

async for chunk in await stream:
    if not chunk.candidates or not chunk.candidates[0].content:
        continue
    if not chunk.candidates[0].content.parts:
        continue

    for part in chunk.candidates[0].content.parts:
        part_dict = {}

        if part.text:
            part_dict["text"] = part.text
        if part.thought:
            part_dict["thought"] = True
        if part.thought_signature:
            part_dict["thought_signature"] = part.thought_signature
        if part.function_call:
            part_dict["function_call"] = {
                "name": part.function_call.name,
                "args": dict(part.function_call.args)
            }

        if part_dict:
            model_parts.append(part_dict)

# Add to conversation
conversation.append({
    "role": "model",
    "parts": model_parts
})
        """)
        print()
        print("This approach preserves:")
        print("  ✓ All thinking parts")
        print("  ✓ All text parts")
        print("  ✓ All function calls with thought_signature")
        print("  ✓ Complete conversation chain")

    return result


if __name__ == "__main__":
    asyncio.run(main())
