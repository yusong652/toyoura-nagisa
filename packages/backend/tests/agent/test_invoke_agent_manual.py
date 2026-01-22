"""
Manual test script for invoke_agent tool.

Run with:
    cd packages/backend && uv run python tests/agent/test_invoke_agent_manual.py
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


async def initialize_backend():
    """Initialize backend services like app.py does."""
    from fastapi import FastAPI
    from fastmcp import Client
    from backend.infrastructure.llm.base.factory import initialize_factory
    from backend.infrastructure.mcp.mcp_server import mcp
    from backend.shared.utils.app_context import set_app

    print("[INIT] Initializing backend for invoke_agent tests...")

    # Create minimal FastAPI app
    app = FastAPI()

    # Initialize LLM Factory and Client
    llm_factory = initialize_factory()
    
    from backend.infrastructure.storage.llm_config_manager import get_default_llm_config
    default_config = get_default_llm_config()
    if not default_config:
        # Fallback for tests if no default config
        default_config = {"provider": "google", "model": "gemini-2.0-flash-exp"}
        
    llm_client = llm_factory.create_client_with_config(
        provider=default_config["provider"],
        model=default_config["model"]
    )
    # app.state.llm_client = llm_client  # No longer used
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


async def test_invoke_agent_basic():
    """Test invoke_agent tool directly."""
    print("\n" + "=" * 60)
    print("TEST 1: invoke_agent tool - PFC Explorer")
    print("=" * 60)

    from backend.infrastructure.mcp.tools.agent.invoke_agent import invoke_agent

    # Create mock context
    context = MagicMock()
    context.client_id = "test_session_manual"

    prompt = """
I need to create balls in PFC. Please query the documentation and provide:
1. The exact command syntax for ball creation
2. A working Python example using itasca.command()
3. Any important parameters
"""

    print(f"\nInvoking SubAgent: pfc_explorer")
    print(f"Prompt: {prompt[:100]}...")

    result = await invoke_agent(
        context=context,
        description="Query ball creation syntax",
        prompt=prompt,
        subagent_type="pfc_explorer"
    )

    print(f"\n--- Result ---")
    print(f"Status: {result['status']}")
    print(f"Message: {result['message']}")

    if result['status'] == 'success':
        print(f"Iterations used: {result['data'].get('iterations_used', 'N/A')}")
        print(f"Execution time: {result['data'].get('execution_time_seconds', 'N/A'):.2f}s")
        response_text = result['llm_content']['parts'][0]['text']
        print(f"Response (first 500 chars):\n{response_text[:500]}...")
        return True
    else:
        print(f"Error: {result['message']}")
        return False


async def test_invoke_agent_unknown_type():
    """Test invoke_agent with unknown agent type."""
    print("\n" + "=" * 60)
    print("TEST 2: invoke_agent - Unknown agent type")
    print("=" * 60)

    from backend.infrastructure.mcp.tools.agent.invoke_agent import invoke_agent

    context = MagicMock()
    context.client_id = "test_session_error"

    # This should fail gracefully
    result = await invoke_agent(
        context=context,
        description="Test unknown agent",
        prompt="Test prompt",
        subagent_type="nonexistent_agent"  # type: ignore
    )

    print(f"\n--- Result ---")
    print(f"Status: {result['status']}")
    print(f"Message: {result['message']}")

    # Should be error status
    return result['status'] == 'error' and 'Unknown subagent type' in result['message']


async def test_tool_registration():
    """Test that invoke_agent is properly registered."""
    print("\n" + "=" * 60)
    print("TEST 3: Tool Registration Check")
    print("=" * 60)

    from backend.domain.models.agent_profiles import PFC_TOOLS

    # print(f"\ninvoke_agent in CODING_TOOLS: {'invoke_agent' in CODING_TOOLS} (should be False)")
    print(f"invoke_agent in PFC_TOOLS: {'invoke_agent' in PFC_TOOLS} (should be True)")
    # print(f"invoke_agent in GENERAL_TOOLS: {'invoke_agent' in GENERAL_TOOLS} (should be True)")
    # print(f"CODING_TOOLS count: {len(CODING_TOOLS)}")
    # print(f"GENERAL_TOOLS count: {len(GENERAL_TOOLS)}")

    # invoke_agent should be in PFC_TOOLS and GENERAL_TOOLS (for MainAgent to delegate)
    # but NOT in CODING_TOOLS (no SubAgent delegation needed for coding tasks)
    return (
        # 'invoke_agent' not in CODING_TOOLS and
        'invoke_agent' in PFC_TOOLS
        # 'invoke_agent' in GENERAL_TOOLS
    )


async def test_subagent_config():
    """Test SubAgent configuration."""
    print("\n" + "=" * 60)
    print("TEST 4: SubAgent Configuration")
    print("=" * 60)

    from backend.domain.models.agent_profiles import get_subagent_config, SUBAGENT_CONFIGS

    print(f"\nAvailable SubAgents: {list(SUBAGENT_CONFIGS.keys())}")

    config = get_subagent_config('pfc_explorer')
    print(f"\nPFC Explorer Config:")
    print(f"  Name: {config.name}")
    print(f"  Display Name: {config.display_name}")
    print(f"  Tool Profile: {config.tool_profile}")
    print(f"  Max Iterations: {config.max_iterations}")
    print(f"  Streaming: {config.streaming_enabled}")
    print(f"  Memory: {config.enable_memory}")
    print(f"  Tools (first 5): {list(config.tools)[:5]}...")

    # Critical: SubAgents must NOT have invoke_agent to prevent recursive spawning
    has_invoke_agent = 'invoke_agent' in config.tools
    print(f"  Has invoke_agent: {has_invoke_agent} (should be False)")

    return (
        config.name == 'pfc_explorer' and
        config.streaming_enabled is False and
        config.enable_memory is False and
        not has_invoke_agent  # SubAgents cannot spawn other SubAgents
    )


async def main():
    """Run all tests."""
    print("=" * 60)
    print("invoke_agent Tool Manual Tests")
    print("=" * 60)

    # Initialize backend first
    await initialize_backend()

    results = {}

    # Test 1: Registration check (no LLM needed)
    try:
        results["registration"] = await test_tool_registration()
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        results["registration"] = False

    # Test 2: Config check (no LLM needed)
    try:
        results["config"] = await test_subagent_config()
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        results["config"] = False

    # Test 3: Unknown agent type (no real LLM call)
    try:
        results["unknown_type"] = await test_invoke_agent_unknown_type()
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        results["unknown_type"] = False

    # Test 4: Real invocation (requires LLM)
    try:
        results["basic_invoke"] = await test_invoke_agent_basic()
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        results["basic_invoke"] = False

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
