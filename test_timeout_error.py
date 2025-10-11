#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test Script for Timeout Error Message Quality

Tests how timeout errors are reported and whether they guide LLM to correct actions.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from infrastructure.pfc.websocket_client import PFCWebSocketClient


async def test_timeout_scenarios():
    """Test different timeout scenarios and analyze error messages."""

    client = PFCWebSocketClient(url="ws://127.0.0.1:9001")

    try:
        print("=" * 70)
        print("Timeout Error Message Quality Test")
        print("=" * 70)
        print("\nConnecting to PFC WebSocket Server...")

        connected = await client.connect()
        if not connected:
            print("❌ Failed to connect to PFC server")
            return

        print("✓ Connected successfully\n")

        # Initialize model
        print("Initializing model...")
        await client.send_command("model new", timeout_ms=10000)

        # Setup proper simulation that will actually compute
        print("Setting up simulation with proper contact model...")

        # Domain and basic settings
        await client.send_command("model domain extent", arg="-10 10 -10 10 -10 10", timeout_ms=10000)
        await client.send_command("model large-strain", arg=True, timeout_ms=10000)
        await client.send_command("model gravity", arg=(0, 0, -9.81), timeout_ms=10000)

        # Generate balls
        await client.send_command(
            "ball generate",
            params={"number": 500, "radius": 0.5, "box": "-8 8"},
            timeout_ms=20000
        )

        # Set ball properties
        await client.send_command("ball attribute density", arg=2500.0, timeout_ms=10000)

        # IMPORTANT: Proper contact model setup with all required properties
        await client.send_command(
            "contact cmat default",
            params={
                "model": "linear",
                "property": {
                    "kn": 1.0e7,
                    "ks": 1.0e7,
                    "fric": 0.5,
                    "dp_nratio": 0.7
                }
            },
            timeout_ms=15000
        )

        # Add walls to make simulation more realistic
        await client.send_command("wall generate box", arg="-9 9", timeout_ms=10000)

        print("✓ Simulation setup complete (500 balls with proper contact model)\n")

        # ================================================================
        # SCENARIO 1: Timeout with model cycle (500 balls)
        # ================================================================
        print("=" * 70)
        print("SCENARIO 1: Timeout on Model Cycle (500 balls)")
        print("=" * 70)
        print("Command: model cycle 100000")
        print("Timeout: 3000ms (3 seconds) - intentionally too short for 500 balls")
        print("Expected: Timeout error with guidance\n")

        result = await client.send_command(
            command="model cycle",
            arg=100000,
            timeout_ms=3000,  # Very short for 100000 cycles with 500 balls
            run_in_background=False
        )

        print("\n" + "-" * 70)
        print("📊 ERROR MESSAGE ANALYSIS - Scenario 1")
        print("-" * 70)
        print(f"Status: {result.get('status')}")
        print(f"\nFull Message:")
        print(f"{result.get('message')}")

        data = result.get('data')
        if data:
            print(f"\nData field:")
            print(f"{data}")

        print("\n🔍 LLM-Friendliness Analysis:")
        message = result.get('message', '')

        # Check if message contains useful information
        has_timeout_mention = 'timeout' in message.lower()
        has_command_info = 'model solve' in message.lower() or 'cycle' in message.lower()
        has_background_suggestion = 'background' in message.lower()
        has_timeout_value = '5000' in message or '5s' in message.lower() or '5 second' in message.lower()

        print(f"  ✓ Mentions timeout: {has_timeout_mention}")
        print(f"  ✓ Shows which command failed: {has_command_info}")
        print(f"  ✓ Suggests background mode: {has_background_suggestion}")
        print(f"  ✓ Shows timeout value used: {has_timeout_value}")

        score = sum([has_timeout_mention, has_command_info, has_background_suggestion, has_timeout_value])
        print(f"\n📈 LLM-Friendliness Score: {score}/4")

        if score < 3:
            print("\n💡 Improvement Suggestions:")
            if not has_command_info:
                print("  • Include the command that timed out")
            if not has_background_suggestion:
                print("  • Suggest using run_in_background=True for long tasks")
            if not has_timeout_value:
                print("  • Show the timeout value that was used")

        print("-" * 70)

        # ================================================================
        # SCENARIO 2: Timeout with different cycle count
        # ================================================================
        print("\n" + "=" * 70)
        print("SCENARIO 2: Timeout on Different Cycle Count")
        print("=" * 70)
        print("Command: model cycle 50000")
        print("Timeout: 2000ms (2 seconds) - borderline timeout")
        print("Expected: Timeout error, LLM should learn to increase timeout\n")

        result = await client.send_command(
            command="model cycle",
            arg=50000,
            timeout_ms=2000,  # Borderline timeout
            run_in_background=False
        )

        print("\n" + "-" * 70)
        print("📊 ERROR MESSAGE ANALYSIS - Scenario 2")
        print("-" * 70)
        print(f"Status: {result.get('status')}")
        print(f"\nFull Message:")
        print(f"{result.get('message')}")

        print("\n🔍 Can LLM Learn From This?")
        message = result.get('message', '')

        # Check if LLM can extract actionable information
        can_increase_timeout = 'timeout' in message.lower()
        can_use_background = 'background' in message.lower()

        print(f"  Can learn to: Increase timeout? {can_increase_timeout}")
        print(f"  Can learn to: Use background mode? {can_use_background}")

        if can_increase_timeout or can_use_background:
            print("\n✅ Error message provides actionable guidance")
        else:
            print("\n⚠️  Error message may not guide LLM to correct solution")

        print("-" * 70)

        # ================================================================
        # RECOMMENDATION ANALYSIS
        # ================================================================
        print("\n" + "=" * 70)
        print("💡 RECOMMENDATIONS FOR ERROR MESSAGE IMPROVEMENT")
        print("=" * 70)

        print("\nCurrent Error Format (Assumed):")
        print('  "Command execution timed out after 5000ms"')

        print("\n✨ Suggested Improved Format:")
        print('  "Command \'model cycle 10000\' timed out after 5s."')
        print('  "For long-running commands, consider:"')
        print('  "  • Increase timeout (current: 5s, recommended: 30-60s)"')
        print('  "  • Use run_in_background=True to avoid blocking"')

        print("\n📋 Key Elements for LLM-Friendly Error Messages:")
        print("  1. ✅ Clear error type (timeout)")
        print("  2. ✅ Show exact command that failed")
        print("  3. ✅ Show timeout value used")
        print("  4. ✅ Provide specific recommendations:")
        print("     - Increase timeout (with suggested range)")
        print("     - Use background mode for long tasks")
        print("  5. ✅ Reference parameter documentation")

        print("\n🎯 Benefit:")
        print("  • LLM learns correct parameter values from errors")
        print("  • Reduces trial-and-error iterations")
        print("  • Aligns with 'self-correcting agent' design pattern")

        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await client.disconnect()
        print("\n✓ Disconnected from PFC server")


if __name__ == "__main__":
    print("\n🎯 Starting Timeout Error Message Quality Test\n")
    asyncio.run(test_timeout_scenarios())
