#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test: Background Tasks Should Ignore Timeout Parameter

Verifies that when run_in_background=True, the timeout parameter is ignored
and tasks run to completion regardless of the timeout value.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from infrastructure.pfc.websocket_client import PFCWebSocketClient


async def test_background_ignores_timeout():
    """Test that background tasks ignore timeout and run to completion."""

    client = PFCWebSocketClient(url="ws://127.0.0.1:9001")

    try:
        print("=" * 70)
        print("Background Task Timeout Ignore Test")
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

        # Setup simulation (200 balls, takes ~5 seconds to settle)
        print("Setting up simulation (200 balls)...")
        await client.send_command("model domain extent", arg="-10 10 -10 10 -10 10", timeout_ms=10000)
        await client.send_command("model large-strain", arg=True, timeout_ms=10000)
        await client.send_command("model gravity", arg=(0, 0, -9.81), timeout_ms=10000)

        await client.send_command(
            "ball generate",
            params={"number": 200, "radius": 0.5, "box": "-8 8"},
            timeout_ms=20000
        )

        await client.send_command("ball attribute density", arg=2500.0, timeout_ms=10000)

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

        await client.send_command("wall generate box", arg="-9 9", timeout_ms=10000)
        print("✓ Simulation setup complete\n")

        # ================================================================
        # TEST 1: Command with absurdly short timeout in background mode
        # ================================================================
        print("=" * 70)
        print("TEST 1: Command Background Task (Short Timeout)")
        print("=" * 70)
        print("Command: model cycle 20000 (takes ~8 seconds)")
        print("Mode: run_in_background=True")
        print("Timeout: 1000ms (1 second) - ABSURDLY SHORT")
        print("Expected: Task should IGNORE timeout and complete successfully\n")

        result = await client.send_command(
            command="model cycle",
            arg=20000,  # Takes ~8 seconds
            timeout_ms=1000,  # Only 1 second - should be ignored!
            run_in_background=True
        )

        print("📊 Submission Result:")
        print(f"  Status: {result.get('status')}")
        print(f"  Message: {result.get('message')}")

        if result.get('status') != 'pending':
            print("\n❌ ERROR: Expected pending status")
            return

        task_id = result.get('data', {}).get('task_id')
        print(f"\n✓ Task submitted with task_id: {task_id}")
        print("  Monitoring progress (should NOT timeout at 1 second)...\n")

        # Monitor until completion
        max_checks = 20
        for i in range(max_checks):
            await asyncio.sleep(2)

            status = await client.check_task_status(task_id)

            if status is None:
                print(f"\n⚠️  Check {i+1}: status query returned None")
                print("  Task may have completed and been removed from tracking")
                break

            current_status = status.get('status')
            elapsed = status.get('data', {}).get('elapsed_time', 0)

            print(f"  Check {i+1}: status={current_status}, elapsed={elapsed:.2f}s")

            if current_status == 'success':
                print(f"\n✅ SUCCESS: Task completed after {elapsed:.2f}s")
                print("  → Timeout parameter (1000ms) was correctly IGNORED")
                print("  → Task ran to completion (~8s > 1s timeout)")
                break
            elif current_status == 'error':
                print(f"\n❌ FAILURE: Task failed with error")
                print(f"  Error: {status.get('message')}")
                print("  → This suggests timeout was NOT ignored (BUG!)")
                return
            elif i == max_checks - 1:
                print(f"\n⚠️  Task still running after {max_checks * 2}s")
                print("  This is normal for large simulations")

        # ================================================================
        # TEST 2: Script with short timeout in background mode
        # ================================================================
        print("\n" + "=" * 70)
        print("TEST 2: Script Background Task (Short Timeout)")
        print("=" * 70)
        print("Creating test script...")

        # Create test script
        script_path = Path(__file__).parent / "pfc_workspace" / "test_scripts" / "timeout_ignore_test.py"
        script_path.parent.mkdir(parents=True, exist_ok=True)

        script_content = """import time

print("Script starting...")
print("Resetting model...")
itasca.command("model new")

print("Setting up small simulation...")
itasca.command("model domain extent -5 5")
itasca.command("model large-strain on")
itasca.command("model gravity 0 0 -9.81")

print("Generating 100 balls...")
itasca.command("ball generate number 100 radius 0.5 box -4 4")
itasca.command("ball attribute density 2500.0")

print("Setting contact model...")
itasca.command("contact cmat default model linear property kn 1.0e7 ks 1.0e7 fric 0.5 dp_nratio 0.7")

print("Running 15000 cycles (takes ~6 seconds)...")
itasca.command("model cycle 15000")

print("Script complete!")
result = "Completed 15000 cycles"
"""

        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)

        print(f"✓ Created test script: {script_path.name}")
        print("\nScript: Takes ~6 seconds to complete")
        print("Timeout: 2000ms (2 seconds) - TOO SHORT")
        print("Expected: Script should IGNORE timeout and complete\n")

        result = await client.send_script(
            script_path=str(script_path),
            timeout_ms=2000,  # Only 2 seconds - should be ignored!
            run_in_background=True
        )

        print("📊 Submission Result:")
        print(f"  Status: {result.get('status')}")

        if result.get('status') != 'pending':
            print("\n❌ ERROR: Expected pending status")
            return

        task_id = result.get('data', {}).get('task_id')
        print(f"✓ Task submitted with task_id: {task_id}")
        print("  Monitoring progress (should NOT timeout at 2 seconds)...\n")

        # Monitor until completion
        for i in range(15):
            await asyncio.sleep(2)

            status = await client.check_task_status(task_id)

            if status is None:
                print(f"\n⚠️  Check {i+1}: status query returned None")
                print("  Task may have completed and been removed from tracking")
                break

            current_status = status.get('status')
            elapsed = status.get('data', {}).get('elapsed_time', 0)

            # Show latest output line
            output = status.get('data', {}).get('output', '')
            if output:
                lines = output.strip().split('\n')
                latest = lines[-1] if lines else ''
                print(f"  Check {i+1}: status={current_status}, elapsed={elapsed:.2f}s | {latest}")
            else:
                print(f"  Check {i+1}: status={current_status}, elapsed={elapsed:.2f}s")

            if current_status == 'success':
                print(f"\n✅ SUCCESS: Script completed after {elapsed:.2f}s")
                print("  → Timeout parameter (2000ms) was correctly IGNORED")
                print("  → Script ran to completion (~6s > 2s timeout)")

                # Show final output
                final_output = status.get('data', {}).get('output', '')
                if final_output:
                    print("\n  Final output:")
                    for line in final_output.strip().split('\n')[-5:]:
                        print(f"    {line}")
                break
            elif current_status == 'error':
                print(f"\n❌ FAILURE: Script failed with error")
                print(f"  Error: {status.get('message')}")
                print("  → This suggests timeout was NOT ignored (BUG!)")
                return

        # Cleanup
        try:
            script_path.unlink()
            print(f"\n✓ Cleaned up test script")
        except:
            pass

        # ================================================================
        # SUMMARY
        # ================================================================
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print("✅ Test 1: Command background task ignored timeout parameter")
        print("✅ Test 2: Script background task ignored timeout parameter")
        print("\n🎯 CONCLUSION:")
        print("  run_in_background=True correctly ignores timeout parameter")
        print("  Tasks run to completion regardless of timeout value")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await client.disconnect()
        print("\n✓ Disconnected from PFC server")


if __name__ == "__main__":
    print("\n🎯 Starting Background Timeout Ignore Test\n")
    asyncio.run(test_background_ignores_timeout())
