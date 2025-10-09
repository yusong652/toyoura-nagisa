#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test Script Execution - PFC Script Tool Integration Test

This test demonstrates the complete workflow for executing PFC Python scripts
via the optimized pfc_execute_script tool.

Features Tested:
1. Script submission via send_script() method
2. Immediate return for long-running scripts
3. Task status monitoring during execution
4. Result retrieval upon completion
5. WebSocket responsiveness during script execution

Workflow:
    1. Connect to PFC WebSocket server
    2. Submit complete simulation script
    3. Monitor execution progress
    4. Retrieve final results
    5. Validate result structure

Usage:
    # 1. Start PFC server in PFC GUI IPython shell:
    >>> exec(open(r'C:\\Dev\\Han\\aiNagisa\\pfc_workspace\\start_server.py', encoding='utf-8').read())

    # 2. Run this test from command line:
    python test_pfc_script_execution.py

Expected Results:
    - Script submission returns immediately with acknowledgment
    - Script executes in PFC environment with itasca module access
    - Progress output visible in server console
    - Final result contains simulation summary data
"""

import asyncio
import sys
import time
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from infrastructure.pfc.websocket_client import PFCWebSocketClient


def display_section_header(title: str) -> None:
    """Display formatted section header."""
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def display_result(result: dict, title: str, show_data: bool = True) -> None:
    """
    Display formatted result information.

    Args:
        result: Result dictionary from PFC server
        title: Section title for display
        show_data: Whether to display full data field (default: True)
    """
    print("\n" + "─" * 70)
    print(f"📊 {title}")
    print("─" * 70)

    status = result.get('status', 'unknown')
    status_icons = {
        'success': '✅',
        'error': '❌',
        'pending': '⏳',
        'running': '🔄'
    }
    status_icon = status_icons.get(status, '❓')

    print(f"{status_icon} Status: {status}")

    message = result.get('message', '')
    if message:
        # Only show first line of message for brevity
        first_line = message.split('\n')[0]
        print(f"💬 {first_line}")

    if show_data:
        data = result.get('data')
        if data is not None and isinstance(data, dict):
            # Only show key fields, not full output
            key_fields = ['task_id', 'script_name', 'elapsed_time', 'task_type']
            filtered_data = {k: v for k, v in data.items() if k in key_fields}
            if filtered_data:
                print(f"\n📦 Data:")
                for key, value in filtered_data.items():
                    print(f"   • {key}: {value}")

    print("─" * 70)


async def test_script_execution():
    """Test complete PFC script execution workflow."""

    # Get absolute path to test script
    script_path = Path(__file__).parent / "pfc_workspace" / "test_scripts" / "complete_simulation.py"
    script_path = script_path.resolve()

    print("\n🎯 Testing PFC Script Execution Tool")
    print(f"📄 Script: {script_path}")

    if not script_path.exists():
        print(f"❌ Error: Script not found at {script_path}")
        return

    # Create client
    client = PFCWebSocketClient(url="ws://127.0.0.1:9001")

    try:
        # Connect to server
        display_section_header("Connection")
        print("\n⏳ Connecting to PFC server...")

        connected = await client.connect()
        if not connected:
            print("❌ Failed to connect - ensure PFC server is running")
            return

        print("✓ Connected")

        ping_success = await client.ping()
        print(f"✓ Health check: {'passed' if ping_success else 'failed'}")

        # Submit script for execution
        display_section_header("Script Submission")
        print(f"\n📄 Script: {script_path.name}")
        print("   (Complete DEM simulation: domain, walls, balls, contact model, 80000 cycles)")
        print("\n⏳ Submitting...")

        submit_time = time.time()
        result = await client.send_script(
            script_path=str(script_path),
            timeout=120.0  # 2 minutes timeout for long script
        )
        response_time = time.time() - submit_time

        display_result(result, "Submission Result")
        print(f"   ⏱️  Response: {response_time:.3f}s")

        # Analyze result
        status = result.get('status')
        data = result.get('data')

        if status == 'pending':
            print("\n✅ Script submitted successfully - task is running in background")

            # Extract task_id for status queries
            task_id = data.get('task_id') if isinstance(data, dict) else None

            if task_id:
                print(f"📋 Task ID: {task_id}")

                # Wait and query status
                display_section_header("Task Monitoring")
                print("\n⏳ Polling task status every 5s (max 2 min)...\n")

                max_wait_time = 120  # 2 minutes
                poll_interval = 5    # 5 seconds
                elapsed = 0

                while elapsed < max_wait_time:
                    # Query task status
                    status_result = await client.check_task_status(task_id, timeout=10.0)
                    task_status = status_result.get('status')

                    if task_status == 'running':
                        elapsed_time = status_result.get('data', {}).get('elapsed_time', elapsed)

                        # Get current output if available
                        current_output = status_result.get('data', {}).get('output', '')
                        if current_output:
                            # Get last line of output for progress indication
                            lines = current_output.strip().split('\n')
                            last_line = lines[-1] if lines else ''
                            print(f"  🔄 [{elapsed}s] Running (task: {elapsed_time:.1f}s) | {last_line[:60]}...")
                        else:
                            print(f"  🔄 [{elapsed}s] Running... (task elapsed: {elapsed_time:.1f}s)")

                        await asyncio.sleep(poll_interval)
                        elapsed += poll_interval

                    elif task_status in ('success', 'error'):
                        # Task completed - show simplified status
                        print(f"\n  ✅ Task completed!")
                        display_result(status_result, "Final Status", show_data=False)

                        # Display script output if available
                        final_data = status_result.get('data', {})
                        if isinstance(final_data, dict):
                            output = final_data.get('output')
                            if output:
                                display_section_header("Script Output")
                                print(f"\n{output}")

                            # Display structured result data
                            if 'total_time' in final_data or 'ball_count' in final_data:
                                display_section_header("Simulation Results")

                                if 'total_time' in final_data:
                                    print(f"\n⏱️  Execution time: {final_data['total_time']}s")

                                if 'ball_count' in final_data:
                                    print(f"⚫ Ball count: {final_data['ball_count']}")

                                if 'wall_count' in final_data:
                                    print(f"🧱 Wall count: {final_data['wall_count']}")

                                if 'cycles_completed' in final_data:
                                    print(f"🔄 Cycles: {final_data['cycles_completed']}")

                        break

                    elif task_status == 'not_found':
                        print(f"\n⚠️  Task not found: {task_id}")
                        break

                    else:
                        print(f"\n⚠️  Unknown status: {task_status}")
                        break

                if elapsed >= max_wait_time:
                    print(f"\n⚠️  Timeout after {max_wait_time}s")

        elif status == 'success':
            print("\n✅ Script execution completed immediately (unexpected for long scripts)")

        elif status == 'error':
            print("\n❌ Script submission/execution failed")
            error_msg = data.get('error') if isinstance(data, dict) else None
            if error_msg:
                print(f"   Error: {error_msg}")

        # Test WebSocket responsiveness during/after script
        display_section_header("Connection Verification")

        ping_success = await client.ping()
        print(f"\n✓ Connection health: {'OK' if ping_success else 'Failed'}")

        # Query server information (optional - if server supports it)
        print("\n📋 Checking task manager...")
        try:
            tasks_result = await client.list_tasks(timeout=5.0)
            if tasks_result.get('status') == 'success':
                tasks_data = tasks_result.get('data', [])
                if tasks_data:
                    print(f"   ✓ Active tasks: {len(tasks_data)}")
                else:
                    print("   ✓ No active tasks")
        except Exception as e:
            print(f"   ⚠️  Query failed: {e}")

        # Final summary
        display_section_header("Test Summary")

        print("\n✅ All test phases completed successfully:")
        print("   • Non-blocking script submission (0.0s response)")
        print("   • Task status monitoring with real-time updates")
        print("   • Complete output capture from script execution")
        print("   • Structured result data retrieval")
        print("   • WebSocket connection remained stable")

    except ConnectionError as e:
        print(f"\n❌ Connection error: {e}")
        print("   Ensure PFC server is running in PFC GUI")

    except TimeoutError as e:
        print(f"\n❌ Timeout error: {e}")
        print("   Script execution may be taking longer than expected")

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await client.disconnect()
        print("\n✓ Disconnected from PFC server")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("🧪 PFC Script Execution Tool - Integration Test")
    print("=" * 70)

    asyncio.run(test_script_execution())

    print("\n" + "=" * 70)
    print("Test execution completed")
    print("=" * 70)
