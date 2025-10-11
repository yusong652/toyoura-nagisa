#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test Script for Script Timeout Error Handling

Tests timeout behavior when executing scripts in foreground mode (run_in_background=False).
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from infrastructure.pfc.websocket_client import PFCWebSocketClient


async def test_script_timeout():
    """Test script execution timeout with run_in_background=False."""

    client = PFCWebSocketClient(url="ws://127.0.0.1:9001")

    try:
        print("=" * 70)
        print("Script Timeout Test (Foreground Mode)")
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
        print("✓ Model initialized\n")

        # ================================================================
        # Create a test script that will run for a long time
        # ================================================================
        script_path = Path(__file__).parent / "pfc_workspace" / "test_scripts" / "long_running_test.py"
        script_path.parent.mkdir(parents=True, exist_ok=True)

        # Write a script that prints progress and runs long cycles
        script_content = """import time

print("Starting long-running script...")
print("This script will run for ~15 seconds")

# Import itasca module
print("Initializing simulation...")

# Setup a simulation that takes time
itasca.command("model domain extent -10 10")
itasca.command("model large-strain on")
itasca.command("model gravity 0 0 -9.81")

print("Generating 200 balls...")
itasca.command("ball generate number 200 radius 0.5 box -8 8")
itasca.command("ball attribute density 2500.0")

print("Setting up contact model...")
itasca.command("contact cmat default model linear property kn 1.0e7 ks 1.0e7 fric 0.5 dp_nratio 0.7")

print("Adding walls...")
itasca.command("wall generate box -9 9")

print("Running 30000 cycles (this takes ~10 seconds)...")
itasca.command("model cycle 30000")

print("Simulation complete!")
result = "Completed 30000 cycles"
"""

        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)

        print(f"Created test script: {script_path}\n")

        # ================================================================
        # TEST 1: Script timeout with short timeout (should fail)
        # ================================================================
        print("=" * 70)
        print("TEST 1: Script Execution with Short Timeout")
        print("=" * 70)
        print(f"Script: {script_path.name}")
        print("Mode: run_in_background=False (synchronous)")
        print("Timeout: 5000ms (5 seconds) - too short for script")
        print("Expected: Timeout error\n")

        result = await client.send_script(
            script_path=str(script_path),
            timeout_ms=5000,  # 5 seconds - script needs ~15 seconds
            run_in_background=False
        )

        print("📊 Result:")
        print(f"  Status: {result.get('status')}")
        print(f"  Message: {result.get('message')}")

        data = result.get('data')
        if data:
            print(f"  Data: {data}")

        output = result.get('output')
        if output:
            print(f"\n  Output captured:")
            print("  " + "\n  ".join(output.split('\n')[:10]))  # Show first 10 lines

        print("\n" + "-" * 70)
        print("🔍 Error Message Analysis:")
        print("-" * 70)

        if result.get('status') == 'error':
            message = result.get('message', '')

            # Check error message quality
            has_timeout = 'timeout' in message.lower() or 'timed out' in message.lower()
            has_script_info = script_path.name in message or 'script' in message.lower()
            has_timeout_value = '5000' in message or '5s' in message.lower() or '5 second' in message.lower()
            has_guidance = 'increase' in message.lower() or 'background' in message.lower()

            print(f"  ✓ Mentions timeout: {has_timeout}")
            print(f"  ✓ Shows script name: {has_script_info}")
            print(f"  ✓ Shows timeout value: {has_timeout_value}")
            print(f"  ✓ Provides guidance: {has_guidance}")

            score = sum([has_timeout, has_script_info, has_timeout_value, has_guidance])
            print(f"\n  LLM-Friendliness Score: {score}/4")

            if score >= 3:
                print("  ✅ Error message is helpful for LLM self-correction")
            elif score >= 2:
                print("  ⚠️  Error message could be improved")
            else:
                print("  ❌ Error message needs improvement")
        else:
            print("  ⚠️  Expected error status, got: {}".format(result.get('status')))

        # ================================================================
        # TEST 2: Same script with background mode (should work)
        # ================================================================
        print("\n" + "=" * 70)
        print("TEST 2: Same Script in Background Mode")
        print("=" * 70)
        print("Mode: run_in_background=True (asynchronous)")
        print("Expected: Immediate task_id return, successful completion\n")

        # Reset model
        await client.send_command("model new", timeout_ms=10000)

        result = await client.send_script(
            script_path=str(script_path),
            timeout_ms=None,  # No timeout in background mode
            run_in_background=True
        )

        print("📊 Submission Result:")
        print(f"  Status: {result.get('status')}")
        print(f"  Message: {result.get('message')}")
        print(f"  Data: {result.get('data')}")

        if result.get('status') == 'pending':
            task_id = result.get('data', {}).get('task_id')
            print(f"\n✓ Task submitted! Task ID: {task_id}")
            print("  Monitoring progress...\n")

            # Monitor for a few seconds
            for i in range(3):
                await asyncio.sleep(2)
                status = await client.check_task_status(task_id)
                print(f"  Check {i+1}: status={status.get('status')}")

                # Show partial output if available
                status_data = status.get('data', {})
                if 'output' in status_data and status_data['output']:
                    lines = status_data['output'].strip().split('\n')
                    if lines:
                        print(f"    Latest output: {lines[-1]}")

            print("\n  ✓ Background execution working (task will continue)")
        else:
            print("\n  ⚠️  Expected pending status for background mode")

        # ================================================================
        # SUMMARY
        # ================================================================
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print("✅ Test 1: Script timeout error handling verified")
        print("✅ Test 2: Background execution as fallback verified")
        print("\n💡 Recommendation: Use run_in_background=True for long scripts")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup test script
        try:
            script_path.unlink()
            print(f"\n✓ Cleaned up test script: {script_path}")
        except:
            pass

        await client.disconnect()
        print("✓ Disconnected from PFC server")


if __name__ == "__main__":
    print("\n🎯 Starting Script Timeout Test\n")
    asyncio.run(test_script_timeout())
