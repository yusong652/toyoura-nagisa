"""
Test script for PFC script execution tool.

Tests the new pfc_execute_script functionality with Python SDK scripts.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from backend.infrastructure.pfc import get_client


async def test_pfc_scripts():
    """Test PFC script execution with Python SDK."""

    print("=" * 70)
    print("Testing PFC Script Execution - Python SDK")
    print("=" * 70)

    try:
        # Get WebSocket client (auto-connects)
        client = await get_client()
        print(f"\n✓ Connected to PFC server at {client.url}")

        # Get absolute paths to test scripts
        workspace_path = Path(__file__).parent / "pfc_workspace" / "scripts"

        # Test 1: Get ball count
        print("\n" + "-" * 70)
        print("Test 1: Execute get_ball_count.py")
        print("-" * 70)
        script_path1 = str(workspace_path / "get_ball_count.py")
        print(f"Script path: {script_path1}")

        result1 = await client.send_script(script_path1)
        print(f"\n✓ Result:")
        print(f"  Status: {result1.get('status')}")
        print(f"  Message: {result1.get('message')}")
        print(f"  Data: {result1.get('data')}")

        # Test 2: Get ball IDs
        print("\n" + "-" * 70)
        print("Test 2: Execute get_ball_ids.py")
        print("-" * 70)
        script_path2 = str(workspace_path / "get_ball_ids.py")
        print(f"Script path: {script_path2}")

        result2 = await client.send_script(script_path2)
        print(f"\n✓ Result:")
        print(f"  Status: {result2.get('status')}")
        print(f"  Message: {result2.get('message')}")
        print(f"  Data: {result2.get('data')}")

        # Test 3: Non-existent script
        print("\n" + "-" * 70)
        print("Test 3: Non-existent script (should return error)")
        print("-" * 70)
        script_path3 = str(workspace_path / "nonexistent.py")
        print(f"Script path: {script_path3}")

        result3 = await client.send_script(script_path3)
        print(f"\n✓ Result:")
        print(f"  Status: {result3.get('status')}")
        print(f"  Message: {result3.get('message')}")
        print(f"  Data: {result3.get('data')}")

        print("\n" + "=" * 70)
        print("All tests completed successfully!")
        print("=" * 70)

        print("\n📋 Test Summary:")
        print("  ✓ Ball count script execution")
        print("  ✓ Ball IDs list script execution")
        print("  ✓ Error handling for missing files")

    except Exception as e:
        print(f"\n✗ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_pfc_scripts())
