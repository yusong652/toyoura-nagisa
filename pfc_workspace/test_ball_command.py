"""
Test PFC ball creation using itasca.command() syntax.
"""

import asyncio
import json
import websockets


async def test_ball_command():
    """Test ball creation using itasca.command()."""

    uri = "ws://localhost:9001"

    print("=" * 60)
    print("PFC Ball Creation Test (itasca.command)")
    print("=" * 60)

    try:
        async with websockets.connect(uri) as websocket:
            print("✓ Connected to PFC server\n")

            # Test 1: Create a ball using itasca.command()
            print("Test 1: Creating a ball...")
            create_cmd = {
                "type": "command",
                "command_id": "test-create-001",
                "command": "command",  # This will call itasca.command()
                "params": {
                    "cmd": "ball create radius 0.5"
                }
            }

            await websocket.send(json.dumps(create_cmd))
            response1 = await asyncio.wait_for(websocket.recv(), timeout=5)
            result1 = json.loads(response1)

            print(f"  Status: {result1.get('status')}")
            print(f"  Message: {result1.get('message')}")
            if result1.get('error'):
                print(f"  Error: {result1.get('error')}")
            print()

            # Test 2: Get ball count using itasca.ball.count()
            print("Test 2: Checking ball count...")
            count_cmd = {
                "type": "command",
                "command_id": "test-count-001",
                "command": "ball.count",  # This will call itasca.ball.count()
                "params": {}
            }

            await websocket.send(json.dumps(count_cmd))
            response2 = await asyncio.wait_for(websocket.recv(), timeout=5)
            result2 = json.loads(response2)

            print(f"  Status: {result2.get('status')}")
            print(f"  Message: {result2.get('message')}")
            print(f"  Ball count: {result2.get('data')}")
            if result2.get('error'):
                print(f"  Error: {result2.get('error')}")

            print("\n" + "=" * 60)
            if result1.get('status') == 'success':
                print("✓ Ball creation test PASSED!")
            else:
                print("✗ Ball creation test FAILED")
            print("=" * 60)

    except asyncio.TimeoutError:
        print("\n✗ Command timeout - PFC might be processing")
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_ball_command())
