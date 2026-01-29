"""
Test MCP integration with ToolManager.

Run with:
    uv run python packages/backend/tests/mcp/test_mcp_integration.py
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


async def test_tool_manager_integration():
    """Test that ToolManager includes MCP tools."""
    print("\n" + "=" * 60)
    print("Testing ToolManager + MCP Integration")
    print("=" * 60)

    # Step 1: Load internal tool registry
    print("\n[1] Loading internal tool registry...")
    # IMPORTANT: Use consistent import path (backend.* not packages.backend.*)
    from backend.application.tools.loader import load_tool_registry

    await load_tool_registry()

    from backend.application.tools.registry import TOOL_REGISTRY

    internal_tools = TOOL_REGISTRY.all()
    print(f"    Internal tools: {len(internal_tools)}")

    # Step 2: Initialize MCP connections
    print("\n[2] Initializing MCP connections...")
    # IMPORTANT: Use consistent import path (backend.* not packages.backend.*)
    # to ensure singleton pattern works correctly
    from backend.infrastructure.mcp.client import (
        initialize_mcp_clients,
        load_mcp_configs_from_yaml,
        get_mcp_client_manager,
        shutdown_mcp_clients,
    )

    configs = load_mcp_configs_from_yaml()
    enabled_configs = [c for c in configs if c.enabled]
    print(f"    Enabled MCP servers: {[c.name for c in enabled_configs]}")

    await initialize_mcp_clients(enabled_configs)

    mcp_manager = get_mcp_client_manager()
    mcp_tools = mcp_manager.get_all_tools()
    print(f"    MCP tools loaded: {list(mcp_tools.keys())}")

    # Step 3: Test get_standardized_tools
    print("\n[3] Testing get_standardized_tools()...")
    from backend.infrastructure.llm.providers.google.tool_manager import GoogleToolManager

    tool_manager = GoogleToolManager()
    all_tools = await tool_manager.get_standardized_tools(session_id="test-session")

    print(f"    Total tools: {len(all_tools)}")
    print(f"    Internal: {len(internal_tools)}, MCP: {len(mcp_tools)}")

    # Verify MCP tools are included
    mcp_tool_names = list(mcp_tools.keys())
    included_mcp = [name for name in mcp_tool_names if name in all_tools]
    print(f"    MCP tools included: {included_mcp}")

    # Verify MCP tool mapping
    print(f"    MCP tool mapping: {tool_manager._mcp_tool_mapping}")

    # Step 4: Test MCP tool execution
    print("\n[4] Testing MCP tool execution...")
    if "resolve-library-id" in all_tools:
        result = await tool_manager._execute_tool(
            tool_name="resolve-library-id",
            tool_args={
                "libraryName": "fastapi",
                "query": "FastAPI web framework",
            },
            session_id="test-session",
        )

        print(f"    Status: {result.get('status')}")
        if result.get("status") == "success":
            print(f"    Server: {result.get('data', {}).get('server')}")
            print("[OK] MCP tool execution successful!")
        else:
            print(f"    Error: {result.get('message')}")
    else:
        print("    [SKIP] resolve-library-id not available")

    # Step 5: Cleanup
    print("\n[5] Cleaning up...")
    await shutdown_mcp_clients()
    print("[OK] Cleanup complete")

    print("\n" + "=" * 60)
    print("Integration test completed!")
    print("=" * 60 + "\n")


async def main():
    try:
        await test_tool_manager_integration()
        return 0
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
