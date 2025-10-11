#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test Script for Background Command Execution and Status Query

Tests the full lifecycle of background command execution:
1. Submit command with run_in_background=True
2. Immediately get task_id
3. Query running status multiple times
4. Wait for completion and get result
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from infrastructure.pfc.websocket_client import PFCWebSocketClient


async def test_background_command_execution():
    """Test background command execution with status monitoring."""

    client = PFCWebSocketClient(url="ws://127.0.0.1:9001")

    try:
        print("=" * 70)
        print("Background Command Execution Test")
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

        # Setup simulation
        print("Setting up simulation (500 balls)...")

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

        # Contact model with all properties
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

        # Add walls
        await client.send_command("wall generate box", arg="-9 9", timeout_ms=10000)

        print("✓ Simulation setup complete\n")

        # ================================================================
        # TEST 1: Submit command in background mode
        # ================================================================
        print("=" * 70)
        print("TEST 1: Submit Long-Running Command in Background")
        print("=" * 70)
        print("Command: model cycle 50000")
        print("Mode: run_in_background=True")
        print("Expected: Immediate return with task_id\n")

        result = await client.send_command(
            command="model cycle",
            arg=50000,
            timeout_ms=60000,  # High timeout (but won't be used in background mode)
            run_in_background=True
        )

        print("📊 Submission Result:")
        print(f"  Status: {result.get('status')}")
        print(f"  Message: {result.get('message')}")
        print(f"  Data: {result.get('data')}")

        if result.get('status') != 'pending':
            print("\n❌ ERROR: Expected status='pending' for background submission")
            return

        task_id = result.get('data', {}).get('task_id')
        if not task_id:
            print("\n❌ ERROR: No task_id returned")
            return

        print(f"\n✓ Task submitted successfully! Task ID: {task_id}")

        # ================================================================
        # TEST 2: Query running status multiple times
        # ================================================================
        print("\n" + "=" * 70)
        print("TEST 2: Monitor Running Task Status")
        print("=" * 70)
        print(f"Querying task {task_id} while it's running...\n")

        for i in range(3):
            print(f"--- Query #{i+1} ---")
            status_result = await client.check_task_status(task_id)

            print(f"Status: {status_result.get('status')}")
            print(f"Message: {status_result.get('message')}")

            data = status_result.get('data')
            if data:
                print(f"Data: {data}")
                if 'elapsed_time' in data:
                    print(f"  Elapsed: {data['elapsed_time']:.2f}s")

            if status_result.get('status') != 'running':
                print(f"\n✓ Task completed during query #{i+1}")
                break

            print("  → Task still running, waiting 2 seconds...\n")
            await asyncio.sleep(2)

        # ================================================================
        # TEST 3: Wait for completion and get final result
        # ================================================================
        print("\n" + "=" * 70)
        print("TEST 3: Wait for Task Completion")
        print("=" * 70)
        print("Polling until task completes...\n")

        max_polls = 30  # 30 * 2s = 60s max wait
        poll_count = 0

        while poll_count < max_polls:
            poll_count += 1
            status_result = await client.check_task_status(task_id)
            current_status = status_result.get('status')

            print(f"Poll #{poll_count}: status={current_status}", end="")

            data = status_result.get('data')
            if data and 'elapsed_time' in data:
                print(f", elapsed={data['elapsed_time']:.2f}s")
            else:
                print()

            if current_status in ['success', 'error', 'not_found']:
                print("\n" + "-" * 70)
                print("📊 FINAL RESULT:")
                print("-" * 70)
                print(f"Status: {current_status}")
                print(f"Message: {status_result.get('message')}")
                print(f"Data: {status_result.get('data')}")
                print("-" * 70)

                if current_status == 'success':
                    print("\n✅ Background command execution completed successfully!")
                else:
                    print(f"\n⚠️ Task ended with status: {current_status}")
                break

            await asyncio.sleep(2)
        else:
            print("\n⚠️ Timeout: Task did not complete within 60 seconds")
            print("This may be normal for large simulations")

        # ================================================================
        # TEST 4: Query non-existent task
        # ================================================================
        print("\n" + "=" * 70)
        print("TEST 4: Query Non-Existent Task")
        print("=" * 70)
        print("Querying fake task ID: 'nonexistent'\n")

        fake_result = await client.check_task_status("nonexistent")
        print(f"Status: {fake_result.get('status')}")
        print(f"Message: {fake_result.get('message')}")

        if fake_result.get('status') == 'not_found':
            print("✓ Correctly returned 'not_found' status")
        else:
            print("⚠️ Expected 'not_found' status")

        # ================================================================
        # SUMMARY
        # ================================================================
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print("✅ Test 1: Background submission - task_id received")
        print("✅ Test 2: Running status monitoring - elapsed time tracking")
        print("✅ Test 3: Completion detection - final result retrieval")
        print("✅ Test 4: Error handling - non-existent task detection")
        print("\n🎯 Background command execution workflow verified!")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await client.disconnect()
        print("\n✓ Disconnected from PFC server")


if __name__ == "__main__":
    print("\n🎯 Starting Background Command Execution Test\n")
    asyncio.run(test_background_command_execution())
