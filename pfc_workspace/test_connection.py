"""
Test PFC WebSocket Server Connection

Run this script to test the connection to a running PFC server.
"""

import asyncio
import json
import sys

try:
    import websockets
except ImportError:
    print("Error: websockets module not found")
    print("Install with: pip install websockets")
    sys.exit(1)


async def test_connection():
    """Test WebSocket connection to PFC server."""

    uri = "ws://localhost:9001"

    print("=" * 60)
    print("PFC WebSocket Server Connection Test")
    print("=" * 60)
    print(f"Connecting to: {uri}")
    print()

    try:
        # Use asyncio.wait_for for timeout compatibility
        connect_coro = websockets.connect(uri)
        async with await asyncio.wait_for(connect_coro, timeout=5) as websocket:
            print("✓ Connected to PFC server!")
            print()

            # Test 1: Ping
            print("Test 1: Sending ping...")
            ping_msg = {
                "type": "ping",
                "timestamp": "test"
            }
            await websocket.send(json.dumps(ping_msg))
            response = await websocket.recv()
            response_data = json.loads(response)

            if response_data.get("type") == "pong":
                print(f"✓ Ping successful! Response: {response_data}")
            else:
                print(f"✗ Unexpected response: {response_data}")

            print()

            # Test 2: Simple command (will likely fail if itasca not available)
            print("Test 2: Sending test command...")
            command_msg = {
                "type": "command",
                "command_id": "test-001",
                "command": "ball.num",  # Get number of balls
                "params": {}
            }
            await websocket.send(json.dumps(command_msg))
            response = await websocket.recv()
            response_data = json.loads(response)

            print(f"Command response:")
            print(f"  Status: {response_data.get('status')}")
            print(f"  Message: {response_data.get('message')}")
            if response_data.get('data'):
                print(f"  Data: {response_data.get('data')}")
            if response_data.get('error'):
                print(f"  Error: {response_data.get('error')}")

            print()
            print("=" * 60)
            print("✓ Connection test completed successfully!")
            print("=" * 60)

    except asyncio.TimeoutError:
        print("✗ Connection timeout - is PFC server running?")
        print()
        print("Start PFC server with:")
        print('  "C:\\Program Files\\Itasca\\PFC700\\exe64\\pfc3d700_console.exe"')
        print("  PFC> python")
        print("  >>> exec(open(r'C:\\Dev\\Han\\aiNagisa\\pfc_workspace\\start_server.py').read())")
        return False

    except ConnectionRefusedError:
        print("✗ Connection refused - is PFC server running on port 9001?")
        return False

    except Exception as e:
        print(f"✗ Connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)
