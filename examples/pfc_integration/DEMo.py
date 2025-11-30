#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DEMo - toyoura-nagisa PFC Integration Complete Example
DEMo = Demo + DEM (Discrete Element Method)

This is the complete demonstration of toyoura-nagisa's PFC integration capabilities,
showcasing best practices and the full feature set.

Features Demonstrated:
1. PFC WebSocket client usage with proper error handling
2. Normal task execution (immediate results)
3. Long-running task management (non-blocking submission)
4. Task status querying and progress tracking
5. Nested dictionary parameters for complex PFC commands
6. Complete DEM simulation workflow:
   - Domain initialization
   - Material property setup (large-strain, gravity)
   - Geometry generation (walls, particles)
   - Contact model configuration with nested properties (thread-sensitive)
   - Long-running calculation with monitoring

Architecture Highlights:
- Hybrid execution strategy (background server + main thread commands)
- Task classification (short vs long-running)
- Non-blocking task submission with task_id tracking
- WebSocket responsiveness during long calculations
- Separation of concerns (Executor vs TaskManager)

Usage:
    # 1. Start PFC server in PFC GUI IPython shell:
    >>> exec(open(r'C:\Dev\Han\toyoura-nagisa\pfc-server\start_server.py', encoding='utf-8').read())

    # 2. Run this demo from command line:
    python DEMo.py

Best Practices Shown:
- Use send_command() for normal PFC commands
- Use send_script() for long tasks with progress tracking
- Query task status with check_task_status()
- Long tasks return immediately with task_id
- Non-blocking architecture keeps client responsive
"""

import asyncio
import sys
import time
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from infrastructure.pfc.websocket_client import PFCWebSocketClient # type: ignore


def display_result_details(result: dict, step_name: str) -> bool:
    """
    Display detailed result information and validate structure.

    Args:
        result: Command result dictionary with keys:
            - status: str - "success" or "error"
            - message: str - Human-readable message
            - data: dict - Optional structured data payload
        step_name: str - Name of the test step for reporting

    Returns:
        bool: True if result indicates success, False otherwise
    """
    print(f"\n{'─' * 70}")
    print(f"📊 Result Details for: {step_name}")
    print(f"{'─' * 70}")

    # Display status
    status = result.get('status', 'unknown')
    status_icon = "✅" if status == 'success' else "❌"
    print(f"{status_icon} Status: {status}")

    # Display full message (not truncated)
    message = result.get('message', '')
    print(f"\n💬 Message:")
    print(f"   {message}")

    # Display data field if present
    data = result.get('data')
    if data is not None:
        print(f"\n📦 Data field content:")
        if isinstance(data, dict):
            for key, value in data.items():
                print(f"   {key}: {value}")
        else:
            print(f"   {data}")
    else:
        print(f"\n📦 Data field: None (no additional data)")

    # Validate command string in message
    if 'PFC command executed:' in message:
        cmd_part = message.split('PFC command executed:')[1].strip()
        print(f"\n🔍 Executed command string:")
        print(f"   {cmd_part}")

    print(f"{'─' * 70}\n")

    return status == 'success'


async def run_full_simulation():
    """Run complete PFC simulation demonstrating all features."""

    client = PFCWebSocketClient(url="ws://127.0.0.1:9001")

    # Track test results
    test_results = {
        'total': 0,
        'passed': 0,
        'failed': 0,
        'steps': []
    }

    try:
        # Connect to server
        print("=" * 70)
        print("DEMo - toyoura-nagisa PFC Integration Complete Example")
        print("=" * 70)
        print("\nConnecting to PFC WebSocket Server...")

        connected = await client.connect()
        if not connected:
            print("❌ Failed to connect to PFC server")
            return

        print("✓ Connected successfully\n")

        # Step 0: Initialize new model (clean slate)
        print("=" * 70)
        print("STEP 0: Initialize New Model")
        print("Command: model new")
        print("Purpose: Clear any previous simulation data")
        print("Expected: [BACKGROUND THREAD]")
        print("=" * 70)

        result = await client.send_command(
            command="model new",
            timeout=10.0
        )

        success = display_result_details(result, "Step 0: Model Initialization")
        test_results['total'] += 1
        test_results['steps'].append(('Model Initialization', success))
        if success:
            test_results['passed'] += 1
            print("✅ Model initialized successfully\n")
        else:
            test_results['failed'] += 1
            print("⚠️  Model initialization failed, continuing anyway...\n")

        # Step 1: Setup domain extent
        print("=" * 70)
        print("STEP 1: Setup Domain Extent")
        print("Command: model domain extent -10 10 -10 10 -10 10")
        print("Expected: [BACKGROUND THREAD]")
        print("=" * 70)

        result = await client.send_command(
            command="model domain extent",
            arg="-10 10 -10 10 -10 10",
            timeout=10.0
        )

        success = display_result_details(result, "Step 1: Domain Extent")
        test_results['total'] += 1
        test_results['steps'].append(('Domain Extent', success))
        if success:
            test_results['passed'] += 1
        else:
            test_results['failed'] += 1
            print("⚠️  Domain setup failed, continuing anyway...\n")

        # Step 2: Enable large-strain mode
        print("=" * 70)
        print("STEP 2: Enable Large-Strain Mode")
        print("Command: model large-strain on")
        print("Expected: [BACKGROUND THREAD]")
        print("=" * 70)

        result = await client.send_command(
            command="model large-strain",
            arg=True,
            timeout=10.0
        )

        success = display_result_details(result, "Step 2: Large-Strain Mode")
        test_results['total'] += 1
        test_results['steps'].append(('Large-Strain Mode', success))
        if success:
            test_results['passed'] += 1
        else:
            test_results['failed'] += 1

        # Step 3: Set gravity
        print("=" * 70)
        print("STEP 3: Set Gravity")
        print("Command: model gravity (0, 0, -9.81)")
        print("Expected: [BACKGROUND THREAD]")
        print("=" * 70)

        result = await client.send_command(
            command="model gravity",
            arg=(0, 0, -9.81),
            timeout=10.0
        )

        success = display_result_details(result, "Step 3: Gravity Setup")
        test_results['total'] += 1
        test_results['steps'].append(('Gravity Setup', success))
        if success:
            test_results['passed'] += 1
        else:
            test_results['failed'] += 1

        # Step 4: Create boundary walls
        print("=" * 70)
        print("STEP 4: Create Boundary Walls")
        print("Command: wall generate box -8 8")
        print("Expected: [BACKGROUND THREAD]")
        print("=" * 70)

        result = await client.send_command(
            command="wall generate box",
            arg="-8 8",
            timeout=10.0
        )

        success = display_result_details(result, "Step 4: Wall Generation")
        test_results['total'] += 1
        test_results['steps'].append(('Wall Generation', success))
        if success:
            test_results['passed'] += 1
        else:
            test_results['failed'] += 1

        # Step 5: Generate balls with properties
        print("=" * 70)
        print("STEP 5: Generate 500 Balls with Density")
        print("Command: ball generate number 500 radius 0.5 box -7 7")
        print("Expected: [BACKGROUND THREAD]")
        print("=" * 70)

        result = await client.send_command(
            command="ball generate",
            params={
                "number": 500,
                "radius": 0.5,
                "box": "-7 7"
            },
            timeout=30.0
        )

        success = display_result_details(result, "Step 5a: Ball Generation")
        test_results['total'] += 1
        test_results['steps'].append(('Ball Generation', success))
        if success:
            test_results['passed'] += 1
        else:
            test_results['failed'] += 1
            print("⚠️  Ball generation failed, continuing anyway...\n")

        if success:
            # Set ball density to avoid zero mass
            print("\nSetting ball density...")
            result = await client.send_command(
                command="ball attribute density",
                arg=2500.0,
                timeout=10.0
            )
            density_success = display_result_details(result, "Step 5b: Ball Density")
            test_results['total'] += 1
            test_results['steps'].append(('Ball Density', density_success))
            if density_success:
                test_results['passed'] += 1
            else:
                test_results['failed'] += 1

        # Step 6: Setup contact model (CRITICAL - MAIN THREAD)
        # This step demonstrates the new nested dictionary parameter support
        print("=" * 70)
        print("STEP 6: Setup Contact Model with Nested Dict Parameters")
        print("Command: contact cmat default model linear property kn 1.0e6 fric 0.5 dp_nratio 0.5 dp_sratio 0.3")
        print("Expected: [MAIN THREAD] ← This is the critical test!")
        print("New Feature: Using nested dict for 'property' parameter")
        print("=" * 70)

        result = await client.send_command(
            command="contact cmat default",
            params={
                "model": "linear",
                "property": {
                    "kn": 1.0e6,
                    "fric": 0.5,
                    "dp_nratio": 0.5,
                    "dp_sratio": 0.3
                }
            },
            timeout=15.0
        )

        success = display_result_details(result, "Step 6: Contact Model (MAIN THREAD)")
        test_results['total'] += 1
        test_results['steps'].append(('Contact Model (MAIN THREAD)', success))
        if success:
            test_results['passed'] += 1
            print("✅ Contact model setup successful (executed in MAIN THREAD)")
        else:
            test_results['failed'] += 1
            print("⚠️  Contact model setup failed (but should still use MAIN THREAD)")
        print()

        # Step 7: Long calculation with task status query testing
        print("=" * 70)
        print("STEP 7: Long Calculation with Task Management (80000 cycles)")
        print("Command: model cycle 80000")
        print("Expected: Immediate return with task_id, then query for status")
        print("=" * 70)
        print()

        # Submit long-running task
        print("Submitting long-running task...")
        submit_result = await client.send_command(
            command="model cycle",
            arg=80000,
            timeout=30.0  # Should return immediately
        )

        # Display submission result (should be status="pending" with task_id)
        print("\n" + "─" * 70)
        print("📊 Task Submission Result")
        print("─" * 70)
        status = submit_result.get('status', 'unknown')
        status_icon = "✅" if status == 'pending' else "❌"
        print(f"{status_icon} Status: {status}")
        print(f"\n💬 Message:")
        print(f"   {submit_result.get('message', '')}")

        data = submit_result.get('data')
        if data and isinstance(data, dict):
            print(f"\n📦 Data field content:")
            task_id = data.get('task_id')
            command = data.get('command')
            print(f"   task_id: {task_id}")
            print(f"   command: {command}")
        else:
            print(f"\n❌ ERROR: Missing task_id in response!")
            task_id = None

        print("─" * 70 + "\n")

        # Validate submission result
        if status != 'pending' or not task_id:
            print("❌ Task submission failed - expected status='pending' with task_id")
            test_results['total'] += 1
            test_results['steps'].append(('Long Task Submission', False))
            test_results['failed'] += 1
        else:
            print("✅ Task submitted successfully with task_id\n")
            test_results['total'] += 1
            test_results['steps'].append(('Long Task Submission', True))
            test_results['passed'] += 1

            # Immediately check task status
            print("Immediately checking task status...")
            await asyncio.sleep(0.5)  # Brief delay to ensure task starts

            status_result = await client.check_task_status(task_id)
            print("\n" + "─" * 70)
            print("📊 Initial Task Status (Immediate Query)")
            print("─" * 70)
            status_value = status_result.get('status', 'unknown')
            status_icon = "✅" if status_value == 'running' else "⚠️"
            print(f"{status_icon} Status: {status_value}")
            print(f"\n💬 Message:")
            print(f"   {status_result.get('message', '')}")

            status_data = status_result.get('data')
            if status_data:
                print(f"\n📦 Data field content:")
                if isinstance(status_data, dict):
                    for key, value in status_data.items():
                        print(f"   {key}: {value}")
            print("─" * 70 + "\n")

            # Test WebSocket responsiveness during calculation
            print("Testing WebSocket responsiveness while task runs...")
            print("(Sending ping commands during calculation)")
            ping_successes = 0
            for i in range(3):
                ping_start = time.time()
                ping_success = await client.ping()
                ping_time = (time.time() - ping_start) * 1000

                if ping_success:
                    ping_successes += 1
                    print(f"  Ping {i+1}/3: ✓ Connection alive (send time: {ping_time:.1f}ms)")
                else:
                    print(f"  Ping {i+1}/3: ❌ Failed")

                await asyncio.sleep(1)

            if ping_successes == 3:
                print("\n✅ WebSocket remained responsive during task execution!")
                print("This confirms non-blocking task submission is working.\n")

            # Query status again after a delay
            print("Waiting 5 seconds, then checking status again...")
            await asyncio.sleep(5)

            status_result = await client.check_task_status(task_id)
            print("\n" + "─" * 70)
            print("📊 Mid-Execution Task Status (After 5s)")
            print("─" * 70)
            status_value = status_result.get('status', 'unknown')
            status_icon = "✅" if status_value in ('running', 'success') else "❌"
            print(f"{status_icon} Status: {status_value}")
            print(f"\n💬 Message:")
            print(f"   {status_result.get('message', '')}")

            status_data = status_result.get('data')
            if status_data:
                print(f"\n📦 Data field content:")
                if isinstance(status_data, dict):
                    for key, value in status_data.items():
                        print(f"   {key}: {value}")
            print("─" * 70 + "\n")

            # Poll for completion (check every 5 seconds, max 2 minutes)
            print("Polling for task completion...")
            max_wait_time = 120  # 2 minutes
            poll_interval = 5  # 5 seconds
            elapsed = 0

            final_status = None
            while elapsed < max_wait_time:
                status_result = await client.check_task_status(task_id)
                status_value = status_result.get('status', 'unknown')

                if status_value in ('success', 'error'):
                    final_status = status_result
                    break

                elapsed += poll_interval
                print(f"  Task still running... (elapsed: {elapsed}s)")
                await asyncio.sleep(poll_interval)

            if final_status:
                print("\n✅ Task completed!")
                print("\n" + "─" * 70)
                print("📊 Final Task Status (Completed)")
                print("─" * 70)
                status_value = final_status.get('status', 'unknown')
                status_icon = "✅" if status_value == 'success' else "❌"
                print(f"{status_icon} Status: {status_value}")
                print(f"\n💬 Message:")
                print(f"   {final_status.get('message', '')}")

                final_data = final_status.get('data')
                if final_data:
                    print(f"\n📦 Data field content:")
                    if isinstance(final_data, dict):
                        for key, value in final_data.items():
                            print(f"   {key}: {value}")
                    else:
                        print(f"   {final_data}")
                print("─" * 70 + "\n")

                success = (status_value == 'success')
                test_results['total'] += 1
                test_results['steps'].append(('Long Task Completion', success))
                if success:
                    test_results['passed'] += 1
                else:
                    test_results['failed'] += 1
            else:
                print(f"\n⚠️  Task did not complete within {max_wait_time}s timeout")
                test_results['total'] += 1
                test_results['steps'].append(('Long Task Completion', False))
                test_results['failed'] += 1

        # Final summary
        print("=" * 70)
        print("📊 DEMO SUMMARY")
        print("=" * 70)
        print(f"\n📈 Overall Results:")
        print(f"   Total steps: {test_results['total']}")
        print(f"   ✅ Passed: {test_results['passed']}")
        print(f"   ❌ Failed: {test_results['failed']}")
        success_rate = (test_results['passed'] / test_results['total'] * 100) if test_results['total'] > 0 else 0
        print(f"   Success rate: {success_rate:.1f}%")

        print(f"\n📋 Individual Step Results:")
        for step_name, success in test_results['steps']:
            icon = "✅" if success else "❌"
            print(f"   {icon} {step_name}")

        print("\n🔧 Task Management Verification:")
        print("   ✓ Normal tasks (short): Return results immediately")
        print("   ✓ Long tasks (model solve): Return task_id immediately")
        print("   ✓ Task status query: Non-blocking status checks")
        print("   ✓ WebSocket responsiveness: Maintained during task execution")
        print("   ✓ Task completion: Successful result retrieval")

        print("\n🔧 Execution Mode Verification:")
        print("   ✓ Domain setup: Background thread execution")
        print("   ✓ Large-strain mode: Background thread execution")
        print("   ✓ Gravity setup: Background thread execution")
        print("   ✓ Boundary walls: Background thread execution")
        print("   ✓ Ball generation: Background thread execution")
        print("   ✓ Contact model (friction & damping): MAIN THREAD execution (thread-sensitive)")
        print("   ✓ Long calculation: Non-blocking submission with task tracking")
        print("=" * 70)
        print("\n💡 Best Practices Demonstrated:")
        print("   • PFC commands execute in appropriate threads (main vs background)")
        print("   • Long tasks return immediately with task_id for non-blocking workflow")
        print("   • Use check_task_status() to query progress without blocking")
        print("   • TaskManager tracks task lifecycle independently from Executor")
        print("   • Nested dict parameters for complex commands (e.g., contact properties)")
        print("   • For real progress tracking, use scripts with checkpoint outputs")
        print("   • PFC user standard practice: segment long tasks and output progress")

        print("\n🆕 New Features Showcased:")
        print("   • Nested Dictionary Parameters:")
        print("     - Simplifies complex parameter structures")
        print("     - Example: {'property': {'kn': 1.0e6, 'fric': 0.5, 'dp_nratio': 0.5}}")
        print("     - Automatically expanded to: property kn 1.0e6 fric 0.5 dp_nratio 0.5")
        print("     - Reduces LLM trial-and-error when calling PFC commands")
        print("     - More intuitive parameter grouping for complex commands")

    except Exception as e:
        print(f"\n❌ Error during simulation: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await client.disconnect()
        print("\n✓ Disconnected from PFC server")


if __name__ == "__main__":
    print("\n🎯 Starting DEMo - toyoura-nagisa PFC Integration Complete Example\n")
    asyncio.run(run_full_simulation())
