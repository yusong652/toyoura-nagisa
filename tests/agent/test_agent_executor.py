"""
Test Agent functionality.

This test verifies that the Agent class can:
1. Initialize correctly as a first-class citizen
2. Execute tasks with run() method
3. Make LLM calls
4. Handle tool execution
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "packages"))


async def init_app_context():
    """Initialize app context similar to FastAPI lifespan."""
    from fastapi import FastAPI
    from backend.infrastructure.llm.base.factory import initialize_factory
    from backend.infrastructure.mcp.mcp_server import mcp
    from fastmcp import Client
    from backend.shared.utils.app_context import set_app
    import threading

    print("[INIT] Initializing test environment...")

    app = FastAPI()
    set_app(app)

    # Initialize LLM Factory
    llm_factory = initialize_factory()
    llm_client = llm_factory.create_client()
    app.state.llm_client = llm_client
    app.state.llm_factory = llm_factory
    print(f"[INIT] LLM Client: {type(llm_client).__name__}")

    # Initialize MCP server and client
    app.state.mcp = mcp
    mcp.app = app  # type: ignore
    mcp_client = Client(mcp)
    app.state.mcp_client = mcp_client

    # Start MCP server in background thread
    mcp_thread = threading.Thread(target=lambda: mcp.run(transport="sse", port=9001), daemon=True)
    mcp_thread.start()
    print("[INIT] MCP Server started on port 9001")

    # Wait a bit for MCP server to start
    await asyncio.sleep(0.5)

    print("[INIT] Test environment ready\n")
    return app


async def test_agent_basic():
    """Test basic Agent functionality."""
    from backend.domain.models.agent import AgentActivity
    from backend.domain.models.agent_definitions import PFC_EXPLORER
    from backend.application.services.agent import Agent
    from backend.shared.utils.app_context import get_llm_client

    print("=== Agent Basic Test ===\n")

    # Get LLM client
    llm_client = get_llm_client()
    print(f"✓ LLM Client: {llm_client.__class__.__name__}")

    # Activity callback for monitoring
    activities = []
    def on_activity(activity: AgentActivity):
        activities.append(activity)
        print(f"  [{activity.event_type}] {activity.data}")

    # Create Agent instance (first-class citizen)
    explorer = Agent(
        definition=PFC_EXPLORER,
        llm_client=llm_client,
        on_activity=on_activity,
    )
    print(f"✓ Agent created: {explorer.display_name} ({explorer.name})")
    print(f"  - Tool profile: {PFC_EXPLORER.tool_profile}")
    print(f"  - Max iterations: {PFC_EXPLORER.max_iterations}")
    print(f"  - Timeout: {PFC_EXPLORER.timeout_seconds}s")

    # Test inputs
    inputs = {
        "objective": "Find the syntax for creating balls in PFC",
        "context": "User wants to create a DEM simulation with spherical particles"
    }

    print(f"\n--- Running Agent ---")
    print(f"Objective: {inputs['objective']}")
    print(f"Context: {inputs['context']}")
    print()

    # Run the agent (active behavior)
    result = await explorer.run(inputs)

    print(f"\n--- Result ---")
    print(f"Status: {result.status}")
    print(f"Summary: {result.summary}")
    print(f"Iterations: {result.iterations_used}")
    print(f"Time: {result.execution_time_seconds:.2f}s")

    if result.raw_response:
        print(f"\nResponse preview:")
        preview = result.raw_response[:500] + "..." if len(result.raw_response) > 500 else result.raw_response
        print(preview)

    print(f"\n--- Activities ({len(activities)}) ---")
    for act in activities:
        print(f"  [{act.event_type}]")

    return result


async def main():
    """Run tests with app context."""
    try:
        await init_app_context()
        result = await test_agent_basic()
        print(f"\n=== Test {'PASSED' if result.status == 'success' else 'COMPLETED with ' + result.status} ===")
    except Exception as e:
        print(f"\n=== Test FAILED ===")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
