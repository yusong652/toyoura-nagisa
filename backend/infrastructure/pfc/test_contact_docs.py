"""Test script for contact module documentation."""

from backend.infrastructure.pfc.sdk_docs import search_api, load_api_doc, format_api_doc


def test_contact_functions():
    """Test loading contact module functions."""
    print("=" * 60)
    print("Testing contact Module Functions")
    print("=" * 60)

    # Test search_api with various queries
    test_queries = [
        "count contacts",
        "contact energy",
        "find contact",
        "list contacts",
        "contact property index"
    ]

    for query in test_queries:
        api_name = search_api(query)
        print(f"\nSearch '{query}': {api_name}")

    # Test direct API loading
    test_apis = [
        "itasca.contact.count",
        "itasca.contact.energy",
        "itasca.contact.find",
        "itasca.contact.list",
        "itasca.contact.model_prop_index"
    ]

    print("\n" + "-" * 60)
    print("Direct API Loading")
    print("-" * 60)

    for api_name in test_apis:
        doc = load_api_doc(api_name)
        if doc:
            print(f"\n✓ {api_name}")
            print(f"  Signature: {doc['signature']}")
        else:
            print(f"\n✗ {api_name}: FAILED")


def test_format():
    """Test format_api_doc for contact functions."""
    print("\n\n" + "=" * 60)
    print("Testing Markdown Formatting")
    print("=" * 60)

    # Test count (has multiple optional parameters)
    api_name = "itasca.contact.count"
    doc = load_api_doc(api_name)
    if doc:
        markdown = format_api_doc(doc, api_name)
        print(f"\nFormatted documentation for {api_name}:")
        print("-" * 60)
        print(markdown)

    # Test find (has mixed parameter types)
    api_name = "itasca.contact.find"
    doc = load_api_doc(api_name)
    if doc:
        markdown = format_api_doc(doc, api_name)
        print(f"\n\nFormatted documentation for {api_name}:")
        print("-" * 60)
        print(markdown)


if __name__ == "__main__":
    test_contact_functions()
    test_format()
    print("\n" + "=" * 60)
    print("contact module tests completed!")
    print("=" * 60)
