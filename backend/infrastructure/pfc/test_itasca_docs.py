"""Test script for itasca module documentation."""

from backend.infrastructure.pfc.sdk_docs import search_api, load_api_doc, format_api_doc


def test_itasca_functions():
    """Test loading itasca module functions."""
    print("=" * 60)
    print("Testing itasca Module Functions")
    print("=" * 60)

    # Test search_api with various queries
    test_queries = [
        "execute command",
        "run simulation",
        "current step",
        "timestep"
    ]

    for query in test_queries:
        api_name = search_api(query)
        print(f"\nSearch '{query}': {api_name}")

    # Test direct API loading
    test_apis = [
        "itasca.command",
        "itasca.cycle",
        "itasca.timestep",
        "itasca.mech_age",
        "itasca.dim",
        "itasca.gravity",
        "itasca.set_gravity",
        "itasca.add_save_variable",
        "itasca.set_callback",
        "itasca.deterministic"
    ]

    print("\n" + "-" * 60)
    print("Direct API Loading")
    print("-" * 60)

    for api_name in test_apis:
        doc = load_api_doc(api_name)
        if doc:
            print(f"\n✓ {api_name}")
            print(f"  Signature: {doc['signature']}")
            print(f"  Description: {doc['description'][:80]}...")
        else:
            print(f"\n✗ {api_name}: FAILED")


def test_format():
    """Test format_api_doc for itasca functions."""
    print("\n\n" + "=" * 60)
    print("Testing Markdown Formatting")
    print("=" * 60)

    # Test itasca.command
    api_name = "itasca.command"
    doc = load_api_doc(api_name)
    if doc:
        markdown = format_api_doc(doc, api_name)
        print(f"\nFormatted documentation for {api_name}:")
        print("-" * 60)
        print(markdown)

    # Test itasca.cycle
    api_name = "itasca.cycle"
    doc = load_api_doc(api_name)
    if doc:
        markdown = format_api_doc(doc, api_name)
        print(f"\n\nFormatted documentation for {api_name}:")
        print("-" * 60)
        print(markdown)


if __name__ == "__main__":
    test_itasca_functions()
    test_format()
    print("\n" + "=" * 60)
    print("itasca module tests completed!")
    print("=" * 60)
