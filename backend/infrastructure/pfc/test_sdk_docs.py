"""Test script for PFC SDK documentation system."""

from backend.infrastructure.pfc.sdk_docs import search_api, load_api_doc, format_api_doc


def test_module_functions():
    """Test loading module functions (itasca.ball.*)."""
    print("=" * 60)
    print("Testing Module Functions")
    print("=" * 60)

    # Test search_api
    api_name = search_api("create ball")
    print(f"\nSearch 'create ball': {api_name}")

    # Test load_api_doc
    if api_name:
        doc = load_api_doc(api_name)
        if doc:
            print(f"\nLoaded documentation for: {api_name}")
            print(f"Signature: {doc['signature']}")
            print(f"Description: {doc['description'][:100]}...")
        else:
            print(f"Failed to load documentation for: {api_name}")

    # Test direct API name
    api_name = "itasca.ball.count"
    doc = load_api_doc(api_name)
    if doc:
        print(f"\n\nDirect load: {api_name}")
        print(f"Signature: {doc['signature']}")
    else:
        print(f"Failed to load: {api_name}")


def test_object_methods():
    """Test loading object methods (Ball.*)."""
    print("\n\n" + "=" * 60)
    print("Testing Object Methods")
    print("=" * 60)

    # Test search_api for object method
    api_name = search_api("ball position")
    print(f"\nSearch 'ball position': {api_name}")

    # Test load_api_doc
    if api_name:
        doc = load_api_doc(api_name)
        if doc:
            print(f"\nLoaded documentation for: {api_name}")
            print(f"Signature: {doc['signature']}")
            print(f"Description: {doc['description']}")
        else:
            print(f"Failed to load documentation for: {api_name}")

    # Test various object methods
    test_methods = ["Ball.vel", "Ball.set_pos", "Ball.delete", "Ball.id"]
    for method_name in test_methods:
        doc = load_api_doc(method_name)
        if doc:
            print(f"\n✓ {method_name}: {doc['signature']}")
        else:
            print(f"\n✗ {method_name}: FAILED")


def test_format():
    """Test format_api_doc."""
    print("\n\n" + "=" * 60)
    print("Testing Markdown Formatting")
    print("=" * 60)

    api_name = "itasca.ball.create"
    doc = load_api_doc(api_name)
    if doc:
        markdown = format_api_doc(doc, api_name)
        print(f"\nFormatted documentation for {api_name}:")
        print("-" * 60)
        print(markdown)

    # Test object method formatting
    api_name = "Ball.set_pos"
    doc = load_api_doc(api_name)
    if doc:
        markdown = format_api_doc(doc, api_name)
        print(f"\n\nFormatted documentation for {api_name}:")
        print("-" * 60)
        print(markdown)


if __name__ == "__main__":
    test_module_functions()
    test_object_methods()
    test_format()
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)
