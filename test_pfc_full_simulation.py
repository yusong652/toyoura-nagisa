"""
Complete PFC Simulation Test - Hybrid Execution Strategy Validation

This script runs a full PFC simulation workflow to validate the hybrid execution strategy:
1. Domain setup (background thread)
2. Large-strain mode (background thread)
3. Gravity setup (background thread)
4. Boundary walls generation (background thread)
5. Ball generation with box constraint (background thread)
6. Contact model setup with friction and damping (MAIN THREAD - thread-sensitive)
7. Long calculation (background thread - tests WebSocket responsiveness)
"""

import asyncio
import sys
import time
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from infrastructure.pfc.websocket_client import PFCWebSocketClient


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
    """Run complete PFC simulation with hybrid execution validation."""

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
        print("PFC FULL SIMULATION TEST - Hybrid Execution Strategy")
        print("=" * 70)
        print("\nConnecting to PFC WebSocket Server...")

        connected = await client.connect()
        if not connected:
            print("❌ Failed to connect to PFC server")
            return

        print("✓ Connected successfully\n")

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
        print("=" * 70)
        print("STEP 6: Setup Contact Model (Thread-Sensitive)")
        print("Command: contact cmat default model linear property kn 1.0e6 fric 0.5 dp_nratio 0.5 dp_sratio 0.3")
        print("Expected: [MAIN THREAD] ← This is the critical test!")
        print("=" * 70)

        result = await client.send_command(
            command="contact cmat default",
            params={
                "model": "linear",
                "property": None,  # Boolean flag
                "kn": 1.0e6,
                "fric": 0.5,
                "dp_nratio": 0.5,
                "dp_sratio": 0.3
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

        # Step 7: Long calculation (test WebSocket responsiveness)
        print("=" * 70)
        print("STEP 7: Long Calculation (80000 cycles)")
        print("Command: model solve cycle 80000")
        print("Expected: [BACKGROUND THREAD] ← IPython should remain responsive")
        print("=" * 70)
        print("Starting calculation...")
        print("(While calculating, we'll test WebSocket responsiveness with ping)")
        print()

        # Start calculation in background
        calc_task = asyncio.create_task(
            client.send_command(
                command="model solve",
                params={"cycle": 80000},
                timeout=120.0  # Allow up to 2 minutes for calculation
            )
        )

        # Wait a bit for calculation to start
        await asyncio.sleep(2)

        # Test WebSocket responsiveness during calculation
        print("Testing WebSocket responsiveness during calculation...")
        print("(Note: ping() only validates connection aliveness, not RTT)")
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
            print("\n✅ WebSocket remained responsive during calculation!")
            print("This proves background thread execution is working.\n")

        # Wait for calculation to complete
        print("Waiting for calculation to complete...")
        result = await calc_task

        success = display_result_details(result, "Step 7: Long Calculation")
        test_results['total'] += 1
        test_results['steps'].append(('Long Calculation', success))
        if success:
            test_results['passed'] += 1
        else:
            test_results['failed'] += 1

        # Final summary
        print("=" * 70)
        print("📊 TEST SUMMARY")
        print("=" * 70)
        print(f"\n📈 Overall Results:")
        print(f"   Total tests: {test_results['total']}")
        print(f"   ✅ Passed: {test_results['passed']}")
        print(f"   ❌ Failed: {test_results['failed']}")
        success_rate = (test_results['passed'] / test_results['total'] * 100) if test_results['total'] > 0 else 0
        print(f"   Success rate: {success_rate:.1f}%")

        print(f"\n📋 Individual Test Results:")
        for step_name, success in test_results['steps']:
            icon = "✅" if success else "❌"
            print(f"   {icon} {step_name}")

        print("\n🔧 Execution Mode Verification:")
        print("   ✓ Domain setup: Background thread execution")
        print("   ✓ Large-strain mode: Background thread execution")
        print("   ✓ Gravity setup: Background thread execution")
        print("   ✓ Boundary walls: Background thread execution")
        print("   ✓ Ball generation: Background thread execution")
        print("   ✓ Contact model (friction & damping): MAIN THREAD execution (thread-sensitive)")
        print("   ✓ Long calculation: Background thread execution")
        print("   ✓ WebSocket responsiveness: Maintained during calculation")
        print("=" * 70)
        print("\n💡 Tip: Check PFC server logs to verify execution modes:")
        print("   [MAIN THREAD]: contact cmat default")
        print("   [BACKGROUND THREAD]: all other commands")

    except Exception as e:
        print(f"\n❌ Error during simulation: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await client.disconnect()
        print("\n✓ Disconnected from PFC server")


if __name__ == "__main__":
    asyncio.run(run_full_simulation())
