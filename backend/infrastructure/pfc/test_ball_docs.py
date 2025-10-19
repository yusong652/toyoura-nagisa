"""Test script for ball module documentation."""

from backend.infrastructure.pfc.sdk_docs import search_api, load_api_doc, format_api_doc


def test_ball_functions():
    """Test loading ball module functions."""
    print("=" * 60)
    print("Testing ball Module Functions")
    print("=" * 60)

    # Test search_api with various queries
    test_queries = [
        "create ball",
        "nearest ball",
        "balls in box",
        "ball energy",
        "point in ball"
    ]

    for query in test_queries:
        api_name = search_api(query)
        print(f"\nSearch '{query}': {api_name}")

    # Test direct API loading
    test_apis = [
        "itasca.ball.create",
        "itasca.ball.containing",
        "itasca.ball.energy",
        "itasca.ball.inbox",
        "itasca.ball.maxid",
        "itasca.ball.near",
        "itasca.ball.list",
        "itasca.ball.find",
        "itasca.ball.count"
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
    """Test format_api_doc for ball functions."""
    print("\n\n" + "=" * 60)
    print("Testing Markdown Formatting")
    print("=" * 60)

    # Test inbox (has optional parameter)
    api_name = "itasca.ball.inbox"
    doc = load_api_doc(api_name)
    if doc:
        markdown = format_api_doc(doc, api_name)
        print(f"\nFormatted documentation for {api_name}:")
        print("-" * 60)
        print(markdown)

    # Test near (has optional parameter)
    api_name = "itasca.ball.near"
    doc = load_api_doc(api_name)
    if doc:
        markdown = format_api_doc(doc, api_name)
        print(f"\n\nFormatted documentation for {api_name}:")
        print("-" * 60)
        print(markdown)


if __name__ == "__main__":
    test_ball_functions()
    test_format()
    print("\n" + "=" * 60)
    print("ball module tests completed!")
    print("=" * 60)
