"""
Test creating a ball in PFC via WebSocket.
"""

import asyncio
import json
import websockets


async def test_create_ball():
    """Test ball creation command."""

    uri = "ws://localhost:9001"

    print("=" * 60)
    print("PFC Ball Creation Test")
    print("=" * 60)
    print(f"Connecting to: {uri}\n")

    try:
        async with websockets.connect(uri) as websocket:
            print("✓ Connected to PFC server\n")

            # Test creating a ball using itasca.command
            print("Test: Creating a ball with radius 0.5...")
            command_msg = {
                "type": "command",
                "command_id": "create-ball-001",
                "command": "command",
                "params": {
                    "cmd": "ball create radius 0.5"
                }
            }

            await websocket.send(json.dumps(command_msg))
            print(f"Sent command: ball create radius 0.5")

            response = await websocket.recv()
            response_data = json.loads(response)

            print("\nResponse:")
            print(f"  Status: {response_data.get('status')}")
            print(f"  Message: {response_data.get('message')}")
            if response_data.get('data'):
                print(f"  Data: {response_data.get('data')}")
            if response_data.get('error'):
                print(f"  Error: {response_data.get('error')}")

            print("\n" + "=" * 60)

            if response_data.get('status') == 'success':
                print("✓ Ball creation test PASSED!")
            else:
                print("✗ Ball creation test FAILED")
                print("\nNote: The command format might need adjustment.")
                print("Try using PFC's itasca.command() directly:")
                print('  itasca.command("ball create radius 0.5")')

            print("=" * 60)

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_create_ball())
