"""
Manual test script for Agent class.

Run with:
    cd packages/backend && uv run python tests/agent/test_agent_manual.py
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


async def initialize_backend():
    """Initialize backend services like app.py does."""
    from fastapi import FastAPI
    from fastmcp import Client
    from backend.infrastructure.llm.base.factory import initialize_factory
    from backend.infrastructure.mcp.smart_mcp_server import mcp
    from backend.shared.utils.app_context import set_app

    print("[INIT] Initializing backend for Agent tests...")

    # Create minimal FastAPI app
    app = FastAPI()

    # Initialize LLM Factory and Client
    llm_factory = initialize_factory()
    llm_client = llm_factory.create_client()
    app.state.llm_client = llm_client
    app.state.llm_factory = llm_factory
    print(f"[INIT] LLM Client initialized: {type(llm_client).__name__}")

    # Initialize MCP server and client
    app.state.mcp = mcp
    mcp.app = app  # type: ignore
    mcp_client = Client(mcp)
    app.state.mcp_client = mcp_client
    print("[INIT] MCP Client initialized")

    # Set global app instance
    set_app(app)
    print("[INIT] Backend initialization complete")

    return llm_client


# Import after path setup
from backend.domain.models.agent import AgentDefinition, AgentActivity
from backend.application.services.agent.agent import Agent


# Simple test agent definition (no tools, just text response)
# Uses "general" profile which falls back to base_prompt.md
TEST_AGENT_NO_TOOLS = AgentDefinition(
    name="general",  # Uses config/prompts/base_prompt.md
    display_name="Test Agent (No Tools)",
    description="Simple test agent that responds without using tools",
    tool_profile="disabled",  # No tools
    max_iterations=3,
    streaming_enabled=False,
    enable_memory=False,
)

# Test agent with coding tools
# Uses "general" profile with coding tools
TEST_AGENT_WITH_TOOLS = AgentDefinition(
    name="general",  # Uses config/prompts/base_prompt.md
    display_name="Test Agent (With Tools)",
    description="Test agent that can use coding tools",
    tool_profile="coding",  # Coding tool set
    max_iterations=5,
    streaming_enabled=False,
    enable_memory=False,
)


def activity_callback(activity: AgentActivity):
    """Print activity events for debugging."""
    print(f"  [Activity] {activity.event_type}: {activity.data}")


async def test_no_tools(llm_client):
    """Test agent without tools - should just respond."""
    print("\n" + "=" * 60)
    print("TEST 1: Agent without tools")
    print("=" * 60)

    agent = Agent(
        definition=TEST_AGENT_NO_TOOLS,
        llm_client=llm_client,
        on_activity=activity_callback,
    )

    print(f"\nRunning agent: {agent.display_name}")
    print(f"Input: What is 2 + 2?")

    result = await agent.run("What is 2 + 2?")

    print(f"\n--- Result ---")
    print(f"Status: {result.status}")
    print(f"Iterations: {result.iterations_used}")
    print(f"Time: {result.execution_time_seconds:.2f}s")
    if result.text:
        print(f"Response (first 200 chars): {result.text[:200]}...")

    return result.status == "success"


async def test_with_tools(llm_client):
    """Test agent with tools - should use read tool."""
    print("\n" + "=" * 60)
    print("TEST 2: Agent with tools")
    print("=" * 60)

    agent = Agent(
        definition=TEST_AGENT_WITH_TOOLS,
        llm_client=llm_client,
        on_activity=activity_callback,
    )

    print(f"\nRunning agent: {agent.display_name}")
    print(f"Input: Read the first 10 lines of pyproject.toml")

    result = await agent.run(
        "Read the first 10 lines of the file pyproject.toml in the current directory and summarize what you see."
    )

    print(f"\n--- Result ---")
    print(f"Status: {result.status}")
    print(f"Iterations: {result.iterations_used}")
    print(f"Time: {result.execution_time_seconds:.2f}s")
    if result.text:
        print(f"Response (first 500 chars): {result.text[:500]}...")

    return result.status == "success"


async def test_pfc_explorer(llm_client):
    """Test PFC Explorer agent (if PFC tools available)."""
    print("\n" + "=" * 60)
    print("TEST 3: PFC Explorer Agent")
    print("=" * 60)

    from backend.domain.models.agent_definitions import PFC_EXPLORER

    agent = Agent(
        definition=PFC_EXPLORER,
        llm_client=llm_client,
        on_activity=activity_callback,
    )

    print(f"\nRunning agent: {agent.display_name}")
    print(f"Input: Query ball create command syntax")

    result = await agent.run(
        "Find the syntax for creating balls in PFC using pfc_query_command. "
        "Context: I need to understand how to create particles in a DEM simulation."
    )

    print(f"\n--- Result ---")
    print(f"Status: {result.status}")
    print(f"Iterations: {result.iterations_used}")
    print(f"Time: {result.execution_time_seconds:.2f}s")
    if result.text:
        print(f"Response (first 500 chars): {result.text[:500]}...")

    return result.status == "success"


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Agent Manual Tests")
    print("=" * 60)

    # Initialize backend first
    llm_client = await initialize_backend()

    results = {}

    # Test 1: No tools
    try:
        results["no_tools"] = await test_no_tools(llm_client)
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        results["no_tools"] = False

    # Test 2: With tools
    try:
        results["with_tools"] = await test_with_tools(llm_client)
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        results["with_tools"] = False

    # Test 3: PFC Explorer (optional)
    try:
        results["pfc_explorer"] = await test_pfc_explorer(llm_client)
    except Exception as e:
        print(f"\n[ERROR] PFC Explorer test failed (this may be expected if PFC is not set up): {e}")
        results["pfc_explorer"] = False

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")

    all_passed = all(results.values())
    print(f"\nOverall: {'ALL PASSED' if all_passed else 'SOME FAILED'}")

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
