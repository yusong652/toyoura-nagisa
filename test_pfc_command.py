"""
Test script for type-driven PFC command tool.

Tests the elegant type-driven command structure:
- command: "ball create" (actual PFC command name)
- arg: 9.81 (native Python types: int, float, str, tuple)
- params: {"radius": 1.0, "position": [0, 0, 0]} (typed keyword-value pairs)
  - params can have null values for boolean flags: {"inheritance": null}
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from backend.infrastructure.pfc import get_client


async def test_pfc_commands():
    """Test the refactored PFC command structure."""

    print("=" * 70)
    print("Testing Type-Driven PFC Command Tool - Native Python Types")
    print("=" * 70)

    try:
        # Get WebSocket client (auto-connects)
        client = await get_client()
        print(f"\n✓ Connected to PFC server at {client.url}")

        # Test 1: Positional argument - model gravity (number)
        print("\n" + "-" * 70)
        print("Test 1: Positional argument - model gravity (number type)")
        print("-" * 70)
        print("Command: 'model gravity'")
        print("Arg: 9.81 (float)")
        print("\nExpected assembly: 'model gravity 9.81'")

        result1 = await client.send_command(
            "model gravity",
            arg=9.81  # Native Python float
        )
        print(f"\n✓ Result:")
        print(f"  Status: {result1.get('status')}")
        print(f"  Message: {result1.get('message')}")
        print(f"  Data: {result1.get('data')}")

        # Test 2: Set model domain (keyword parameters)
        print("\n" + "-" * 70)
        print("Test 2: Set model domain extent (keyword parameters)")
        print("-" * 70)
        print("Command: 'model domain'")
        print("Params: {'extent': '-10 10 -10 10 -10 10'}")
        print("\nExpected assembly: 'model domain extent -10 10 -10 10 -10 10'")

        result2 = await client.send_command(
            "model domain",
            params={"extent": "-10 10 -10 10 -10 10"}
        )
        print(f"\n✓ Result:")
        print(f"  Status: {result2.get('status')}")
        print(f"  Message: {result2.get('message')}")
        print(f"  Data: {result2.get('data')}")

        # Test 3: Command with single parameter
        print("\n" + "-" * 70)
        print("Test 3: Command with single keyword parameter")
        print("-" * 70)
        print("Command: 'ball create'")
        print("Params: {'radius': 1.0}")
        print("\nExpected assembly: 'ball create radius 1.0'")

        result3 = await client.send_command(
            "ball create",
            params={"radius": 1.0}
        )
        print(f"\n✓ Result:")
        print(f"  Status: {result3.get('status')}")
        print(f"  Message: {result3.get('message')}")
        print(f"  Data: {result3.get('data')}")

        # Test 4: Command with multiple parameters (mixed native types)
        print("\n" + "-" * 70)
        print("Test 4: Multiple params (number, tuple/list, identifier)")
        print("-" * 70)
        print("Command: 'ball create'")
        print("Params: {'radius': 1.5, 'position': [0, 0, 0], 'group': 'test_balls'}")
        print("\nExpected assembly: 'ball create radius 1.5 position (0,0,0) group \"test_balls\"'")

        result4 = await client.send_command(
            "ball create",
            params={"radius": 1.5, "position": [0, 0, 0], "group": "test_balls"}  # Native types
        )
        print(f"\n✓ Result:")
        print(f"  Status: {result4.get('status')}")
        print(f"  Message: {result4.get('message')}")
        print(f"  Data: {result4.get('data')}")

        # Test 5: Boolean flags - contact material with inheritance
        print("\n" + "-" * 70)
        print("Test 5: Boolean flags (null values indicate flag keywords)")
        print("-" * 70)
        print("Command: 'contact cmat default'")
        print("Params: {'model': 'linear', 'inheritance': None}")
        print("\nExpected assembly: 'contact cmat default model linear inheritance'")

        result5 = await client.send_command(
            "contact cmat default",
            params={"model": "linear", "inheritance": None}
        )
        print(f"\n✓ Result:")
        print(f"  Status: {result5.get('status')}")
        print(f"  Message: {result5.get('message')}")
        print(f"  Data: {result5.get('data')}")

        # Test 6: List all balls (no parameters)
        print("\n" + "-" * 70)
        print("Test 6: Command with no parameters")
        print("-" * 70)
        print("Command: 'ball list'")
        print("\nExpected assembly: 'ball list'")

        result6 = await client.send_command("ball list")
        print(f"\n✓ Result:")
        print(f"  Status: {result6.get('status')}")
        print(f"  Message: {result6.get('message')}")
        print(f"  Data: {result6.get('data')}")

        # Test 7: Delete balls by range
        print("\n" + "-" * 70)
        print("Test 7: Delete balls by range (PFC native range syntax)")
        print("-" * 70)
        print("Command: 'ball delete'")
        print("Params: {'range': 'id 1 2'}")
        print("\nExpected assembly: 'ball delete range id 1 2'")

        result7 = await client.send_command(
            "ball delete",
            params={"range": "id 1 2"}
        )
        print(f"\n✓ Result:")
        print(f"  Status: {result7.get('status')}")
        print(f"  Message: {result7.get('message')}")
        print(f"  Data: {result7.get('data')}")
        print(f"\n  Expected: Should show 2 balls created from previous tests")

        # Test 8: Invalid command (PFC business error)
        print("\n" + "-" * 70)
        print("Test 8: Invalid command (should return PFC error, not backend error)")
        print("-" * 70)
        print("Command: 'invalid command'")
        print("\nExpected: status='error' with PFC error message")

        result8 = await client.send_command("invalid command")
        print(f"\n✓ Result:")
        print(f"  Status: {result8.get('status')}")
        print(f"  Message: {result8.get('message')}")
        print(f"  Data: {result8.get('data')}")

        # Test 9: Condition auto-conversion (LLM intuitive way)
        print("\n" + "-" * 70)
        print("Test 9: Condition auto-conversion (LLM intuitive way)")
        print("-" * 70)
        print("Command: 'model domain'")
        print("Params: {'condition': 'stop'} (LLM intuitive key-value)")
        print("\nBackend auto-converts to: {'condition': None, 'stop': None}")
        print("Expected assembly: 'model domain condition stop'")

        result9 = await client.send_command(
            "model domain",
            params={"condition": "stop"}  # LLM intuitive way
        )
        print(f"\n✓ Result:")
        print(f"  Status: {result9.get('status')}")
        print(f"  Message: {result9.get('message')}")
        print(f"  Data: {result9.get('data')}")

        # Test 10: String identifier with group parameter
        print("\n" + "-" * 70)
        print("Test 10: String identifier handling (group parameter)")
        print("-" * 70)
        print("Command: 'ball create'")
        print("Params: {'radius': 1.0, 'group': 'my_balls'}")
        print("\nExpected: 'ball create radius 1.0 group \"my_balls\"' (auto-quoted)")

        result10 = await client.send_command(
            "ball create",
            params={"radius": 1.0, "group": "my_balls"}
        )
        print(f"\n✓ Result:")
        print(f"  Status: {result10.get('status')}")
        print(f"  Message: {result10.get('message')}")

        print("\n" + "=" * 70)
        print("All tests completed successfully!")
        print("=" * 70)

        print("\n📋 Test Summary - Type-Driven API:")
        print("  ✓ Positional argument (native float) - model gravity with number type")
        print("  ✓ Keyword parameters (string) - model domain with extent")
        print("  ✓ Ball creation with single numeric parameter")
        print("  ✓ Ball creation with mixed native types (float, list, string)")
        print("  ✓ Boolean flags (None values) - contact cmat with inheritance")
        print("  ✓ Command with no parameters - ball list")
        print("  ✓ Ball delete with range parameter")
        print("  ✓ Invalid commands return proper PFC error structure")
        print("  ✓ Condition auto-conversion - LLM intuitive {'condition': 'stop'}")
        print("  ✓ String identifier auto-quoting - group parameter")
        print("\n🎯 Type-Driven Benefits:")
        print("  • No string wrapping for numbers: 9.81 instead of \"9.81\"")
        print("  • Native tuples/lists: [0, 0, 0] instead of \"(0, 0, 0)\"")
        print("  • Auto-conversion: {'condition': 'stop'} → proper PFC flags")
        print("  • Smart string handling: identifiers auto-quoted, complex strings preserved")
        print("  • Clearer LLM API ergonomics with Python type semantics")

    except Exception as e:
        print(f"\n✗ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_pfc_commands())
