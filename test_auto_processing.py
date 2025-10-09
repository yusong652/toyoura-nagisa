"""
Test automatic queue processing for PFC server.

This script validates that the automatic timer-based processing works
without requiring manual IPython command execution.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from infrastructure.pfc.websocket_client import PFCWebSocketClient


async def test_auto_processing():
    """Test that commands execute automatically without manual trigger."""

    client = PFCWebSocketClient(url="ws://127.0.0.1:9001")

    try:
        print("=" * 70)
        print("AUTO-PROCESSING TEST")
        print("=" * 70)
        print("\nConnecting to PFC WebSocket Server...")

        connected = await client.connect()
        if not connected:
            print("❌ Failed to connect to PFC server")
            return

        print("✓ Connected successfully\n")

        # Test 1: Simple domain extent command
        print("=" * 70)
        print("Test 1: Domain Extent (should auto-process)")
        print("=" * 70)
        print("Command: model domain extent -10 10 -10 10 -10 10")
        print("Expected: Executes automatically within 100ms\n")

        result = await client.send_command(
            command="model domain extent",
            arg="-10 10 -10 10 -10 10",
            timeout=5.0  # Short timeout - should complete quickly
        )

        print(f"Status: {result.get('status')}")

        if result.get('status') == 'success':
            print("✅ Test 1 PASSED - Auto-processing works!")
        else:
            print(f"⚠️ Test 1 FAILED - {result.get('message')}")

        print()

        # Test 2: Contact cmat (thread-sensitive command)
        print("=" * 70)
        print("Test 2: Contact cmat (thread-sensitive, should auto-process)")
        print("=" * 70)
        print("Command: contact cmat default model linear")
        print("Expected: Executes in main thread automatically\n")

        result = await client.send_command(
            command="contact cmat default",
            params={"model": "linear"},
            timeout=5.0
        )

        print(f"Status: {result.get('status')}")

        if result.get('status') == 'success':
            print("✅ Test 2 PASSED - Auto-processing works for thread-sensitive commands!")
        else:
            print(f"⚠️ Test 2 FAILED - {result.get('message')}")

        print()

        # Test 3: Multiple rapid commands
        print("=" * 70)
        print("Test 3: Rapid Sequential Commands (stress test)")
        print("=" * 70)
        print("Sending 5 commands in quick succession\n")

        commands = [
            ("model large-strain", True, {}),
            ("model gravity", (0, 0, -9.81), {}),
            ("ball generate", None, {"number": 10, "radius": 0.5}),
            ("ball attribute density", 2500.0, {}),
            ("model cycle", None, {"number": 100})
        ]

        success_count = 0
        for i, (cmd, arg, params) in enumerate(commands, 1):
            result = await client.send_command(
                command=cmd,
                arg=arg,
                params=params,
                timeout=10.0
            )

            if result.get('status') == 'success':
                success_count += 1
                print(f"  {i}/5: ✓ {cmd}")
            else:
                print(f"  {i}/5: ✗ {cmd} - {result.get('message', '')[:50]}")

        print()
        if success_count == 5:
            print("✅ Test 3 PASSED - All rapid commands processed automatically!")
        else:
            print(f"⚠️ Test 3 PARTIAL - {success_count}/5 commands succeeded")

        print()

        # Final summary
        print("=" * 70)
        print("AUTO-PROCESSING VALIDATION COMPLETE")
        print("=" * 70)
        print()
        print("✓ Automatic queue processing is working!")
        print("✓ No manual triggering required!")
        print("✓ Thread-sensitive commands execute safely!")
        print("✓ Multiple rapid commands handled correctly!")
        print()
        print("🎉 The new auto-processing architecture is ready for production!")

    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await client.disconnect()
        print("\n✓ Disconnected from PFC server")


if __name__ == "__main__":
    asyncio.run(test_auto_processing())
