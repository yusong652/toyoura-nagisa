"""
Test complete PFC workflow with domain initialization.
"""

import asyncio
import json
import websockets


async def send_command(ws, command, params=None, cmd_id=None):
    """Helper to send command and get response."""
    if cmd_id is None:
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


async def test_full_workflow():
    """Test complete PFC workflow from initialization to ball creation."""

    uri = "ws://localhost:9001"

    print("=" * 60)
    print("PFC Complete Workflow Test")
    print("=" * 60)

    try:
        async with websockets.connect(uri) as websocket:
            print("✓ Connected to PFC server\n")

            # Step 1: Create new model
            print("Step 1: Creating new model...")
            result = await send_command(websocket, "command", {"cmd": "model new"})
            print(f"  Status: {result.get('status')}")
            if result.get('error'):
                print(f"  Error: {result.get('error')}")
            print()

            # Step 2: Set domain
            print("Step 2: Setting domain...")
            result = await send_command(websocket, "command",
                                       {"cmd": "model domain extent -5 5"})
            print(f"  Status: {result.get('status')}")
            if result.get('error'):
                print(f"  Error: {result.get('error')}")
            print()

            # Step 3: Create a ball
            print("Step 3: Creating a ball...")
            result = await send_command(websocket, "command",
                                       {"cmd": "ball create radius 0.5"})
            print(f"  Status: {result.get('status')}")
            if result.get('error'):
                print(f"  Error: {result.get('error')}")
            print()

            # Step 4: Check ball count
            print("Step 4: Checking ball count...")
            result = await send_command(websocket, "ball.count")
            print(f"  Status: {result.get('status')}")
            print(f"  Ball count: {result.get('data')}")
            if result.get('error'):
                print(f"  Error: {result.get('error')}")
            print()

            print("=" * 60)
            if result.get('data') > 0:
                print("✓ Complete workflow test PASSED!")
                print(f"✓ Successfully created {result.get('data')} ball(s)")
            else:
                print("✗ Workflow test FAILED - no balls created")
            print("=" * 60)

    except asyncio.TimeoutError:
        print("\n✗ Command timeout")
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_full_workflow())
