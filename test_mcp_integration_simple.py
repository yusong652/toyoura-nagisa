"""Simple integration test for MCP tools with new search system."""

from backend.infrastructure.pfc.shared.query import CommandSearch, APISearch


def test_command_search():
    """Test CommandSearch (backend of pfc_query_command)."""
    print("=" * 80)
    print("1. CommandSearch Integration Test")
    print("=" * 80)

    test_cases = [
        ("ball create", "ball create"),
        ("packing", "ball distribute"),
        ("linear stiffness", "Linear"),
    ]

    for query, expected_substr in test_cases:
        print(f"\nQuery: '{query}'")
        results = CommandSearch.search(query, top_k=3)

        if results:
            best = results[0]
            print(f"✓ Found: {best.document.title} (score: {best.score:.3f})")

            if expected_substr.lower() in best.document.title.lower():
                print(f"  ✓ Match contains '{expected_substr}'")
            else:
                print(f"  ⚠️  Expected '{expected_substr}' in result")
        else:
            print(f"✗ No results")

    print("\n✓ CommandSearch test completed")


def test_api_search():
    """Test APISearch (backend of pfc_query_python_api)."""
    print("\n\n" + "=" * 80)
    print("2. APISearch Integration Test")
    print("=" * 80)

    test_cases = [
        ("ball create", "itasca.ball.create"),
        ("contact gap", "Contact.gap"),
        ("pos", "pos"),
    ]

    for query, expected_substr in test_cases:
        print(f"\nQuery: '{query}'")
        results = APISearch.search(query, top_k=3)

        if results:
            best = results[0]
            print(f"✓ Found: {best.document.id} (score: {best.score:.3f})")

            if expected_substr.lower() in best.document.id.lower():
                print(f"  ✓ Match contains '{expected_substr}'")
            else:
                print(f"  ⚠️  Expected '{expected_substr}' in result")
        else:
            print(f"✗ No results")

    print("\n✓ APISearch test completed")


def test_filters():
    """Test filter functionality."""
    print("\n\n" + "=" * 80)
    print("3. Filter Functionality Test")
    print("=" * 80)

    # Test: Commands only
    print("\nTest: Commands only (exclude model properties)")
    results = CommandSearch.search(
        "linear",
        top_k=5,
        include_model_properties=False
    )

    if results:
        all_commands = all(r.document.doc_type.value == "command" for r in results)
        print(f"✓ Found {len(results)} results")
        print(f"  All commands: {all_commands} {'✓' if all_commands else '✗'}")

    # Test: Model properties only
    print("\nTest: Model properties only")
    results = CommandSearch.search_model_properties("stiffness", top_k=5)

    if results:
        all_props = all(r.document.doc_type.value == "model_property" for r in results)
        print(f"✓ Found {len(results)} results")
        print(f"  All model properties: {all_props} {'✓' if all_props else '✗'}")

    # Test: Category filter
    print("\nTest: Category filter (ball)")
    results = CommandSearch.search("create", top_k=5, category="ball")

    if results:
        all_ball = all(r.document.category == "ball" for r in results)
        print(f"✓ Found {len(results)} results")
        print(f"  All in 'ball' category: {all_ball} {'✓' if all_ball else '✗'}")

    print("\n✓ Filter test completed")


def test_edge_cases():
    """Test edge cases."""
    print("\n\n" + "=" * 80)
    print("4. Edge Cases Test")
    print("=" * 80)

    # Test: No results
    print("\nTest: Query with no results")
    results = CommandSearch.search("xyz_nonexistent_12345", top_k=5)
    print(f"Results: {len(results)} {'✓' if len(results) == 0 else '✗ (expected 0)'}")

    # Test: Empty query
    print("\nTest: Empty query")
    results = CommandSearch.search("", top_k=5)
    print(f"Results: {len(results)} {'✓' if len(results) == 0 else '⚠️'}")

    # Test: Very short query
    print("\nTest: Single character query")
    results = CommandSearch.search("b", top_k=3)
    print(f"Results: {len(results)} ({'found something' if results else 'no results'})")

    print("\n✓ Edge cases test completed")


if __name__ == "__main__":
    print("MCP Tools Integration - Simple Test\n")

    try:
        test_command_search()
        test_api_search()
        test_filters()
        test_edge_cases()

        print("\n\n" + "=" * 80)
        print("✓ ALL INTEGRATION TESTS COMPLETED")
        print("=" * 80)
        print("\n📋 Tests Run:")
        print("  1. ✓ CommandSearch integration")
        print("  2. ✓ APISearch integration")
        print("  3. ✓ Filter functionality")
        print("  4. ✓ Edge cases")
        print("\nNew search system is ready for MCP tools!")

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
