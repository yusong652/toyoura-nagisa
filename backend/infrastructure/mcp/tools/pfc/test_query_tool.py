"""
Simple test script for pfc_query_python_api tool
"""
import asyncio
from backend.infrastructure.mcp.tools.pfc.pfc_query_python_api import search_api, load_api_doc, format_api_doc

async def test_queries():
    """Test various query scenarios"""

    print("=" * 80)
    print("TEST 1: Search for 'create a ball'")
    print("=" * 80)
    api_name = search_api("create a ball")
    print(f"Found API: {api_name}")

    if api_name:
        api_doc = load_api_doc(api_name)
        if api_doc:
            formatted = format_api_doc(api_doc, api_name)
            print("\nFormatted documentation:")
            print(formatted)

    print("\n" + "=" * 80)
    print("TEST 2: Search for 'list all balls'")
    print("=" * 80)
    api_name = search_api("list all balls")
    print(f"Found API: {api_name}")

    if api_name:
        api_doc = load_api_doc(api_name)
        if api_doc:
            print(f"\nSignature: {api_doc['signature']}")
            print(f"Description: {api_doc['description']}")

    print("\n" + "=" * 80)
    print("TEST 3: Search for 'ball velocity'")
    print("=" * 80)
    api_name = search_api("ball velocity")
    print(f"Found API: {api_name}")

    if api_name:
        api_doc = load_api_doc(api_name)
        if api_doc:
            print(f"\nSignature: {api_doc['signature']}")
            print(f"Description: {api_doc['description']}")

    print("\n" + "=" * 80)
    print("TEST 4: Search for 'cubic packing' (should not find SDK)")
    print("=" * 80)
    api_name = search_api("cubic packing")
    print(f"Found API: {api_name}")
    if not api_name:
        print("✓ Correctly identified as not available in Python SDK")

    print("\n" + "=" * 80)
    print("All tests completed!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_queries())
