"""Test script for refactored PFC SDK documentation system.

This script validates the new modular architecture by testing:
1. Path-based search
2. Keyword-based search
3. Contact type handling
4. Documentation loading and formatting
"""

from backend.infrastructure.pfc.sdk import (
    search_api,
    load_api_doc,
    format_api_signature,
    format_api_doc
)


def test_path_search():
    """Test exact path matching."""
    print("=" * 60)
    print("TEST 1: Path-based search")
    print("=" * 60)

    # Test regular path
    print("\n[1.1] Testing regular path: 'itasca.ball.create'")
    results = search_api("itasca.ball.create")
    assert len(results) > 0, "Should find itasca.ball.create"
    print(f"✓ Found: {results[0].api_name}")
    print(f"  Score: {results[0].score}")
    print(f"  Strategy: {results[0].strategy}")

    # Test object method
    print("\n[1.2] Testing object method: 'Ball.vel'")
    results = search_api("Ball.vel")
    assert len(results) > 0, "Should find Ball.vel"
    print(f"✓ Found: {results[0].api_name}")

    # Test case-insensitive
    print("\n[1.3] Testing case-insensitive: 'ball.vel'")
    results = search_api("ball.vel")
    assert len(results) > 0, "Should find Ball.vel (case-insensitive)"
    print(f"✓ Found: {results[0].api_name}")


def test_contact_types():
    """Test Contact type aliasing."""
    print("\n" + "=" * 60)
    print("TEST 2: Contact type handling")
    print("=" * 60)

    # Test Contact type query
    print("\n[2.1] Testing Contact type: 'BallBallContact.gap'")
    results = search_api("BallBallContact.gap")
    assert len(results) > 0, "Should find Contact.gap"
    print(f"✓ Found: {results[0].api_name}")
    print(f"  Metadata: {results[0].metadata}")

    # Verify metadata
    assert results[0].metadata is not None, "Should have metadata"
    assert 'contact_type' in results[0].metadata, "Should have contact_type"
    assert results[0].metadata['contact_type'] == "BallBallContact"
    print(f"✓ Contact type correctly identified: {results[0].metadata['contact_type']}")


def test_keyword_search():
    """Test natural language keyword search."""
    print("\n" + "=" * 60)
    print("TEST 3: Keyword-based search")
    print("=" * 60)

    # Test keyword search
    print("\n[3.1] Testing keyword: 'create ball'")
    results = search_api("create ball")
    assert len(results) > 0, "Should find APIs related to 'create ball'"
    print(f"✓ Found {len(results)} result(s):")
    for i, result in enumerate(results, 1):
        print(f"  {i}. {result.api_name} (score: {result.score})")

    print("\n[3.2] Testing keyword: 'measure count'")
    results = search_api("measure count")
    assert len(results) > 0, "Should find APIs related to 'measure count'"
    print(f"✓ Found {len(results)} result(s):")
    for i, result in enumerate(results, 1):
        print(f"  {i}. {result.api_name} (score: {result.score})")


def test_doc_loading():
    """Test documentation loading and formatting."""
    print("\n" + "=" * 60)
    print("TEST 4: Documentation loading and formatting")
    print("=" * 60)

    # Load documentation
    print("\n[4.1] Loading documentation for 'itasca.ball.create'")
    doc = load_api_doc("itasca.ball.create")
    assert doc is not None, "Should load documentation"
    print(f"✓ Loaded documentation")
    print(f"  Signature: {doc['signature']}")
    print(f"  Parameters: {len(doc.get('parameters', []))}")
    print(f"  Examples: {len(doc.get('examples', []))}")

    # Format signature
    print("\n[4.2] Formatting signature")
    sig = format_api_signature("itasca.ball.create")
    assert sig is not None, "Should format signature"
    print(f"✓ Formatted signature:")
    print(f"  {sig}")

    # Format full documentation
    print("\n[4.3] Formatting full documentation")
    results = search_api("itasca.ball.create")
    formatted = format_api_doc(doc, results[0])
    assert len(formatted) > 0, "Should format documentation"
    print(f"✓ Formatted documentation ({len(formatted)} chars)")
    print("\nFirst 200 chars of formatted doc:")
    print("-" * 60)
    print(formatted[:200] + "...")


def test_contact_formatting():
    """Test Contact type documentation formatting."""
    print("\n" + "=" * 60)
    print("TEST 5: Contact type documentation formatting")
    print("=" * 60)

    print("\n[5.1] Formatting Contact type documentation")
    results = search_api("BallBallContact.gap")
    doc = load_api_doc(results[0].api_name)
    formatted = format_api_doc(doc, results[0])

    # Verify official path appears in formatted doc
    assert "itasca.BallBallContact.gap" in formatted, "Should show official path"
    assert "Available for" in formatted, "Should show availability info"
    print(f"✓ Contact type correctly formatted")
    print("\nFirst 300 chars of formatted doc:")
    print("-" * 60)
    print(formatted[:300] + "...")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("PFC SDK REFACTORED ARCHITECTURE TEST SUITE")
    print("=" * 60)

    try:
        test_path_search()
        test_contact_types()
        test_keyword_search()
        test_doc_loading()
        test_contact_formatting()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        print("\nThe refactored architecture is working correctly!")
        print("Key improvements:")
        print("  • Modular design with clear separation of concerns")
        print("  • Strategy pattern for extensible search")
        print("  • Type-safe data models")
        print("  • Specialized Contact type handling")
        print("  • Clean, maintainable code structure")

    except AssertionError as e:
        print("\n" + "=" * 60)
        print("❌ TEST FAILED")
        print("=" * 60)
        print(f"Error: {e}")
        raise
    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ UNEXPECTED ERROR")
        print("=" * 60)
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
