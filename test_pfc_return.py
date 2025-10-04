"""
Test to check if PFC commands return values.
"""

import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from infrastructure.pfc import get_client


async def test_return_values():
    """Test different PFC commands to see which ones return values."""

    print("=" * 70)
    print("Testing PFC Command Return Values")
    print("=" * 70)

    client = await get_client()

    # Test 1: ball.num (query command)
    print("\n" + "-" * 70)
    print("Test 1: ball.num (should return number)")
    print("-" * 70)
    result1 = await client.send_command("ball.num")
    print(f"Status: {result1.get('status')}")
    print(f"Message: {result1.get('message')}")
    print(f"Data: {result1.get('data')}")

    # Test 2: model.title (query command)
    print("\n" + "-" * 70)
    print("Test 2: model.title (should return title string)")
    print("-" * 70)
    result2 = await client.send_command("model.title")
    print(f"Status: {result2.get('status')}")
    print(f"Message: {result2.get('message')}")
    print(f"Data: {result2.get('data')}")

    # Test 3: model.version (query command)
    print("\n" + "-" * 70)
    print("Test 3: model.version (should return version)")
    print("-" * 70)
    result3 = await client.send_command("model.version")
    print(f"Status: {result3.get('status')}")
    print(f"Message: {result3.get('message')}")
    print(f"Data: {result3.get('data')}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(test_return_values())
