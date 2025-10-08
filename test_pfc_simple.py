"""Simple PFC connection test"""

import asyncio
import websockets
import json

async def test_simple():
    try:
        # Try to connect with explicit IPv4 address
        print("Connecting to ws://127.0.0.1:9001...")
        async with websockets.connect(
            "ws://127.0.0.1:9001",
            open_timeout=10,
            ping_interval=None  # Disable auto-ping for simple test
        ) as websocket:
            print("✓ Connected!")

            # Send a simple command
            message = {
                "type": "command",
                "command_id": "test1",
                "command": "model gravity",
                "arg": (0, 0, -9.81),
                "params": {}
            }

            print(f"Sending: {message}")
            await websocket.send(json.dumps(message))

            # Wait for response
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            print(f"✓ Response: {response}")

    except asyncio.TimeoutError:
        print("❌ Timeout waiting for response")
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_simple())
