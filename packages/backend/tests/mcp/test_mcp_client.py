"""
Test script for external MCP client.

Run with:
    uv run python packages/backend/tests/mcp/test_external_client.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Load .env file
from dotenv import load_dotenv

load_dotenv(project_root / ".env")

from packages.backend.infrastructure.mcp.client import (
    MCPClient,
    MCPClientManager,
    MCPServerConfig,
    load_mcp_configs,
)


def get_context7_config() -> MCPServerConfig:
    """Get context7 server configuration from MCP config."""
    configs = load_mcp_configs()
    for config in configs:
        if config.name == "context7":
            return config

    # Fallback if not in config
    raise ValueError("context7 not found in MCP config")


async def test_context7_connection():
    """Test connecting to context7 MCP server."""
    print("\n" + "=" * 60)
    print("Testing context7 MCP Server Connection")
    print("=" * 60)

    config = get_context7_config()
    print(f"    Command: {config.command} {' '.join(config.args[:3])}...")  # Don't print API key

    client = MCPClient(config)

    print(f"\n[1] Connecting to {config.name}...")
    success = await client.connect()

    if not success:
        print("[FAILED] Could not connect to context7")
        return False

    print(f"[OK] Connected to {config.name}")

    # List tools
    print("\n[2] Available tools:")
    tools = client.get_tools()
    for name, tool in tools.items():
        print(f"    - {name}: {tool.description[:60]}...")

    # Test resolve-library-id
    print("\n[3] Testing 'resolve-library-id' tool...")
    result = await client.call_tool(
        "resolve-library-id",
        {
            "libraryName": "fastapi",
            "query": "FastAPI web framework for Python",
        },
    )

    if result["status"] == "success":
        print("[OK] Tool call successful")
        for content in result.get("content", []):
            if content.get("type") == "text":
                # Print first 500 chars
                text = content.get("text", "")[:500]
                print(f"    Response: {text}...")
    else:
        print(f"[FAILED] {result.get('message')}")

    # Disconnect
    print("\n[4] Disconnecting...")
    await client.disconnect()
    print("[OK] Disconnected")

    return True


async def test_manager():
    """Test the MCP manager with multiple servers."""
    print("\n" + "=" * 60)
    print("Testing MCPClientManager")
    print("=" * 60)

    manager = MCPClientManager()

    # Add context7
    config = get_context7_config()

    print("\n[1] Adding context7 server...")
    success = await manager.add_server(config)
    print(f"[{'OK' if success else 'FAILED'}] Add server: {success}")

    # List all tools
    print("\n[2] All available tools:")
    tools = manager.get_all_tools()
    for name in tools:
        print(f"    - {name}")

    # Test tool routing
    print("\n[3] Testing tool routing...")
    result = await manager.call_tool(
        "resolve-library-id",
        {
            "libraryName": "react",
            "query": "React frontend library",
        },
    )
    print(f"    Status: {result['status']}")
    print(f"    Server: {result.get('server', 'N/A')}")

    # Server info
    print("\n[4] Connected servers:")
    for info in manager.get_server_info():
        print(f"    - {info['name']}: {len(info['tools'])} tools")

    # Shutdown
    print("\n[5] Shutting down...")
    await manager.shutdown()
    print("[OK] Manager shutdown complete")


async def main():
    """Run all tests."""
    print("\n" + "#" * 60)
    print("# External MCP Client Tests")
    print("#" * 60)

    try:
        # Test single client
        await test_context7_connection()

        # Test manager
        await test_manager()

        print("\n" + "=" * 60)
        print("All tests completed!")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
