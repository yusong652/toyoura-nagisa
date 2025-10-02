#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DEMo - aiNagisa PFC Integration Hello World

This is the "Hello World" example for aiNagisa's PFC integration.
DEMo = Demo + DEM (Discrete Element Method)

Demonstrates:
- Connecting to PFC WebSocket server
- Initializing model domain
- Creating a particle (ball)
- Querying model state
"""

import asyncio
from websockets.asyncio.client import connect
import json
from uuid import uuid4

async def send_command(websocket, command, params):
    """Send a command and wait for response"""
    cmd_id = str(uuid4())
    message = {
        "type": "command",
        "command_id": cmd_id,
        "command": command,
        "params": params
    }

    print(f"\n→ Sending: {command}")
    print(f"  Params: {params}")

    await websocket.send(json.dumps(message))
    response = await websocket.recv()
    result = json.loads(response)

    print(f"← Response:")
    print(f"  Status: {result.get('status')}")
    print(f"  Data: {result.get('data')}")
    print(f"  Message: {result.get('message')}")

    return result

async def demo():
    """Run the DEMo - create a ball in PFC"""
    uri = "ws://127.0.0.1:9001"
    print("=" * 60)
    print("DEMo - aiNagisa PFC Integration Hello World")
    print("=" * 60)
    print(f"\nConnecting to PFC server at {uri}...")

    try:
        async with connect(uri) as websocket:
            print("✓ Connected!\n")
            print("=" * 60)

            # Step 1: Initialize domain
            print("\n[Step 1] Initializing domain...")
            result = await send_command(
                websocket,
                "command",
                {"cmd": "model domain extent -5 5"}
            )

            # Step 2: Create a ball
            print("\n[Step 2] Creating ball...")
            result = await send_command(
                websocket,
                "command",
                {"cmd": "ball create radius 0.5 position (0,0,0)"}
            )

            # Step 3: Query ball count
            print("\n[Step 3] Querying ball count...")
            result = await send_command(
                websocket,
                "ball.count",
                {}
            )

            # Step 4: List all balls
            print("\n[Step 4] Listing all balls...")
            result = await send_command(
                websocket,
                "ball.list",
                {}
            )

            print("\n" + "=" * 60)
            print("✓ All commands executed successfully!")
            print("=" * 60)

    except Exception as e:
        print(f"\n✗ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("\n🎯 Starting DEMo...\n")
    asyncio.run(demo())
