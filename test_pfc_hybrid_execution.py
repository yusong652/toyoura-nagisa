"""
Test script for PFC hybrid execution strategy.

This script tests the new hybrid execution mechanism:
- Main thread execution for thread-sensitive commands (contact cmat default)
- Background thread execution for regular commands (model solve, etc.)
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from infrastructure.pfc.websocket_client import PFCWebSocketClient


async def test_hybrid_execution():
    """Test hybrid execution strategy with different command types."""

    # Create client
    client = PFCWebSocketClient(url="ws://localhost:9001")

    try:
        # Connect to server
        print("=" * 60)
        print("Connecting to PFC WebSocket Server...")
        print("=" * 60)
        connected = await client.connect()

        if not connected:
            print("❌ Failed to connect to PFC server")
            print("Please ensure PFC server is running in PFC GUI")
            return

        print("✓ Connected successfully\n")

        # Test 1: Thread-sensitive command (should execute in MAIN THREAD)
        print("=" * 60)
        print("TEST 1: Thread-sensitive command (contact cmat default)")
        print("Expected: [MAIN THREAD] execution in server logs")
        print("=" * 60)

        try:
            result = await client.send_command(
                command="contact cmat default",
                params={"model": "linear", "inheritance": None},
                timeout=30.0
            )

            print(f"Status: {result.get('status')}")
            print(f"Message: {result.get('message')}")
            if result.get('data'):
                print(f"Data: {result.get('data')}")
            print()

        except Exception as e:
            print(f"❌ Test 1 failed: {e}\n")

        # Test 2: Regular command (should execute in BACKGROUND THREAD)
        print("=" * 60)
        print("TEST 2: Regular command (model gravity)")
        print("Expected: [BACKGROUND THREAD] execution in server logs")
        print("=" * 60)

        try:
            result = await client.send_command(
                command="model gravity",
                arg=(0, 0, -9.81),
                timeout=10.0
            )

            print(f"Status: {result.get('status')}")
            print(f"Message: {result.get('message')}")
            if result.get('data'):
                print(f"Data: {result.get('data')}")
            print()

        except Exception as e:
            print(f"❌ Test 2 failed: {e}\n")

        # Test 3: Ping during execution (verify WebSocket is responsive)
        print("=" * 60)
        print("TEST 3: WebSocket responsiveness (ping)")
        print("Expected: Immediate pong response")
        print("=" * 60)

        try:
            ping_success = await client.ping()

            if ping_success:
                print("✓ Ping successful - WebSocket is responsive")
            else:
                print("❌ Ping failed")
            print()

        except Exception as e:
            print(f"❌ Test 3 failed: {e}\n")

        # Test 4: Multiple concurrent commands (if background execution works)
        print("=" * 60)
        print("TEST 4: Concurrent commands test")
        print("Expected: Both commands execute without blocking")
        print("=" * 60)

        try:
            # Send two commands concurrently
            task1 = client.send_command("model gravity", arg=(0, 0, -10), timeout=10.0)
            task2 = client.send_command("model large-strain", arg=True, timeout=10.0)

            results = await asyncio.gather(task1, task2, return_exceptions=True)

            for i, result in enumerate(results, 1):
                if isinstance(result, Exception):
                    print(f"Command {i}: ❌ {result}")
                else:
                    print(f"Command {i}: ✓ {result.get('status')} - {result.get('message', '')[:80]}")
            print()

        except Exception as e:
            print(f"❌ Test 4 failed: {e}\n")

        print("=" * 60)
        print("All tests completed!")
        print("=" * 60)
        print("\nCheck PFC server logs for execution mode markers:")
        print("  - [MAIN THREAD]: contact cmat default")
        print("  - [BACKGROUND THREAD]: model gravity, model large-strain")

    finally:
        # Cleanup
        await client.disconnect()
        print("\n✓ Disconnected from PFC server")


if __name__ == "__main__":
    # Run tests
    asyncio.run(test_hybrid_execution())
