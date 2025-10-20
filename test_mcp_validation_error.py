"""
Test script to verify MCP validation error handling improvements.

This script tests the improved error formatting in extract.py by sending
tool calls with invalid parameters to the MCP server.

Prerequisites:
    - MCP server must be running (start with: uv run python backend/app.py)
    - Server should be accessible at http://localhost:9000/sse
"""

import asyncio
from fastmcp import Client as MCPClient
from mcp.types import CallToolRequestParams, CallToolRequest, ClientRequest, CallToolResult
from backend.infrastructure.mcp.utils import extract_tool_result_from_mcp


async def test_validation_error_handling():
    """Test validation error handling with different error scenarios."""

    print("=" * 80)
    print("Testing MCP Validation Error Handling")
    print("=" * 80)

    # Initialize MCP client with SSE transport
    # Connect to the running MCP server at port 9000
    mcp_client = MCPClient("http://localhost:9000/sse")

    try:
        async with mcp_client as mcp_async_client:
            print("\n✓ Connected to MCP server")

            # Test Case 1: Unexpected keyword argument (the original issue)
            print("\n" + "=" * 80)
            print("Test Case 1: Unexpected Keyword Argument (description)")
            print("=" * 80)

            params1 = CallToolRequestParams(
                name="pfc_execute_command",
                arguments={
                    "command": "model new",
                    "description": "Initializes a new, empty PFC model"  # Invalid parameter
                },
                _meta={"client_id": "test-session-001"}  # type: ignore
            )

            call_req1 = ClientRequest(CallToolRequest(method="tools/call", params=params1))

            try:
                result1 = await mcp_async_client.session.send_request(call_req1, CallToolResult)
                tool_result1 = extract_tool_result_from_mcp(result1)

                print("\n📋 Tool Result:")
                print(f"Status: {tool_result1.get('status')}")
                print(f"\n👤 Message (User Display with emoji):\n{tool_result1.get('message')}")
                print(f"\n🤖 LLM Content (Pure text, no emoji):\n{tool_result1.get('llm_content', {}).get('parts', [{}])[0].get('text', 'N/A')}")

            except Exception as e:
                print(f"\n❌ Error: {e}")

            # Test Case 2: Missing required parameter
            print("\n" + "=" * 80)
            print("Test Case 2: Missing Required Parameter (command)")
            print("=" * 80)

            params2 = CallToolRequestParams(
                name="pfc_execute_command",
                arguments={
                    # Missing "command" parameter
                    "timeout": 5000
                },
                _meta={"client_id": "test-session-002"}  # type: ignore
            )

            call_req2 = ClientRequest(CallToolRequest(method="tools/call", params=params2))

            try:
                result2 = await mcp_async_client.session.send_request(call_req2, CallToolResult)
                tool_result2 = extract_tool_result_from_mcp(result2)

                print("\n📋 Tool Result:")
                print(f"Status: {tool_result2.get('status')}")
                print(f"\n👤 Message (User Display with emoji):\n{tool_result2.get('message')}")
                print(f"\n🤖 LLM Content (Pure text, no emoji):\n{tool_result2.get('llm_content', {}).get('parts', [{}])[0].get('text', 'N/A')}")

            except Exception as e:
                print(f"\n❌ Error: {e}")

            # Test Case 3: Multiple unknown parameters
            print("\n" + "=" * 80)
            print("Test Case 3: Multiple Unknown Parameters")
            print("=" * 80)

            params3 = CallToolRequestParams(
                name="pfc_execute_command",
                arguments={
                    "command": "model new",
                    "description": "Test",  # Invalid
                    "extra_param": "value",  # Invalid
                    "another_invalid": 123   # Invalid
                },
                _meta={"client_id": "test-session-003"}  # type: ignore
            )

            call_req3 = ClientRequest(CallToolRequest(method="tools/call", params=params3))

            try:
                result3 = await mcp_async_client.session.send_request(call_req3, CallToolResult)
                tool_result3 = extract_tool_result_from_mcp(result3)

                print("\n📋 Tool Result:")
                print(f"Status: {tool_result3.get('status')}")
                print(f"\n👤 Message (User Display with emoji):\n{tool_result3.get('message')}")
                print(f"\n🤖 LLM Content (Pure text, no emoji):\n{tool_result3.get('llm_content', {}).get('parts', [{}])[0].get('text', 'N/A')}")

            except Exception as e:
                print(f"\n❌ Error: {e}")

            # Test Case 4: Valid call for comparison
            print("\n" + "=" * 80)
            print("Test Case 4: Valid Call (for comparison)")
            print("=" * 80)

            params4 = CallToolRequestParams(
                name="pfc_execute_command",
                arguments={
                    "command": "model new",
                    "timeout": 5000
                },
                _meta={"client_id": "test-session-004"}  # type: ignore
            )

            call_req4 = ClientRequest(CallToolRequest(method="tools/call", params=params4))

            try:
                result4 = await mcp_async_client.session.send_request(call_req4, CallToolResult)
                tool_result4 = extract_tool_result_from_mcp(result4)

                print("\n📋 Tool Result:")
                print(f"Status: {tool_result4.get('status')}")
                print(f"\n👤 Message (User Display):\n{tool_result4.get('message')}")
                print(f"\n🤖 LLM Content:\n{tool_result4.get('llm_content', {}).get('parts', [{}])[0].get('text', 'N/A')}")

            except Exception as e:
                print(f"\n❌ Error: {e}")

    except ConnectionError as e:
        print(f"\n❌ Cannot connect to MCP server: {e}")
        print("Make sure the MCP server is running on port 9000")
        print("Start it with: uv run python backend/infrastructure/mcp/smart_mcp_server.py")

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("Test Complete")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_validation_error_handling())
