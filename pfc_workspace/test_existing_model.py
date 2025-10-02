"""
Test PFC commands on existing model (without model new).

Assumes user already has PFC open with a model initialized.
"""

import asyncio
import json
import websockets


async def send_command(ws, command, params=None):
    """Helper to send command and get response."""
    import uuid
    cmd_id = str(uuid.uuid4())

    msg = {
        "type": "command",
        "command_id": cmd_id,
        "command": command,
        "params": params or {}
    }

    await ws.send(json.dumps(msg))
    response = await asyncio.wait_for(ws.recv(), timeout=10)
    return json.loads(response)


async def test_existing_model():
    """Test PFC commands on existing model."""

    uri = "ws://localhost:9001"

    print("=" * 60)
    print("PFC Existing Model Test")
    print("=" * 60)
    print("NOTE: Assumes PFC is open with domain already set")
    print("=" * 60)

    try:
        async with websockets.connect(uri) as websocket:
            print("✓ Connected to PFC server\n")

            # Step 1: Set domain (in case not set)
            print("Step 1: Ensuring domain is set...")
            result = await send_command(websocket, "command",
                                       {"cmd": "model domain extent -5 5"})
            print(f"  Status: {result.get('status')}")
            print()

            # Step 2: Create a ball
            print("Step 2: Creating a ball...")
            result = await send_command(websocket, "command",
                                       {"cmd": "ball create radius 0.5"})
            print(f"  Status: {result.get('status')}")
            if result.get('error'):
                print(f"  Error: {result.get('error')}")
            else:
                print(f"  Message: {result.get('message')}")
            print()

            # Step 3: Check ball count
            print("Step 3: Checking ball count...")
            result = await send_command(websocket, "ball.count")
            print(f"  Status: {result.get('status')}")
            print(f"  Ball count: {result.get('data')}")
            print()

            # Step 4: Try to get ball list (if any)
            if result.get('data', 0) > 0:
                print("Step 4: Getting ball list...")
                result = await send_command(websocket, "ball.list")
                print(f"  Status: {result.get('status')}")
                if result.get('data'):
                    print(f"  Balls: {result.get('data')[:200]}...")  # First 200 chars
                print()

            print("=" * 60)
            print("✓ Test completed!")
            print("=" * 60)

    except asyncio.TimeoutError:
        print("\n✗ Command timeout")
        print("Check PFC console for errors")
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_existing_model())
