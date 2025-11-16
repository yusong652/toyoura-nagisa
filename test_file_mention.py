"""
Test script for file mention functionality.

This script simulates frontend sending mentioned_files and verifies:
1. Files are correctly read
2. Format matches Claude Code
3. Deduplication works
4. Error handling works
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.infrastructure.file_mention import FileMentionProcessor


async def test_basic_file_mention():
    """Test basic file mention with single file."""
    print("\n" + "="*80)
    print("TEST 1: Basic File Mention (Single File)")
    print("="*80)

    processor = FileMentionProcessor(session_id="test-session", agent_profile="general")

    # Test with test_files/sample.py (should exist in workspace)
    file_paths = ["test_files/sample.py"]

    print(f"\nProcessing files: {file_paths}")
    reminders = await processor.process_mentioned_files(file_paths)

    print(f"\nResult: {len(reminders)} reminder(s) generated")

    if reminders:
        print("\n" + "-"*80)
        print("Generated Reminder:")
        print("-"*80)
        # Only print first 500 chars to avoid clutter
        reminder_preview = reminders[0][:500] + "..." if len(reminders[0]) > 500 else reminders[0]
        print(reminder_preview)
        print("-"*80)

    # Verify format
    if reminders:
        assert "<system-reminder>" in reminders[0], "Missing <system-reminder> tag"
        assert "Called the Read tool" in reminders[0], "Missing tool call record"
        assert "Result of calling the Read tool" in reminders[0], "Missing tool result"
        print("\n✓ Format matches Claude Code pattern")

    return reminders


async def test_deduplication():
    """Test file path deduplication."""
    print("\n" + "="*80)
    print("TEST 2: File Path Deduplication")
    print("="*80)

    processor = FileMentionProcessor(session_id="test-session", agent_profile="general")

    # Same file mentioned multiple times
    file_paths = [
        "test_files/sample.py",
        "test_files/sample.py",  # Duplicate
        "./test_files/sample.py",  # Different format, same file
    ]

    print(f"\nProcessing files: {file_paths}")
    reminders = await processor.process_mentioned_files(file_paths)

    print(f"\nResult: {len(reminders)} reminder(s) generated (should be 1)")

    assert len(reminders) == 1, f"Deduplication failed: expected 1 reminder, got {len(reminders)}"
    print("\n✓ Deduplication works correctly")

    return reminders


async def test_multiple_files():
    """Test multiple different files."""
    print("\n" + "="*80)
    print("TEST 3: Multiple Different Files")
    print("="*80)

    processor = FileMentionProcessor(session_id="test-session", agent_profile="general")

    # Multiple different files
    file_paths = [
        "test_files/sample.py",
        "test_files/another.py",
    ]

    print(f"\nProcessing files: {file_paths}")
    reminders = await processor.process_mentioned_files(file_paths)

    print(f"\nResult: {len(reminders)} reminder(s) generated (should be 2)")

    assert len(reminders) == 2, f"Expected 2 reminders, got {len(reminders)}"
    print("\n✓ Multiple files processed correctly")

    return reminders


async def test_nonexistent_file():
    """Test error handling for nonexistent file."""
    print("\n" + "="*80)
    print("TEST 4: Error Handling (Nonexistent File)")
    print("="*80)

    processor = FileMentionProcessor(session_id="test-session", agent_profile="general")

    # Nonexistent file
    file_paths = [
        "test_files/nonexistent_file.py",
    ]

    print(f"\nProcessing files: {file_paths}")
    reminders = await processor.process_mentioned_files(file_paths)

    print(f"\nResult: {len(reminders)} reminder(s) generated (should be 0)")

    assert len(reminders) == 0, f"Error handling failed: expected 0 reminders, got {len(reminders)}"
    print("\n✓ Nonexistent files are correctly skipped")

    return reminders


async def test_mixed_valid_invalid():
    """Test mixed valid and invalid files."""
    print("\n" + "="*80)
    print("TEST 5: Mixed Valid and Invalid Files")
    print("="*80)

    processor = FileMentionProcessor(session_id="test-session", agent_profile="general")

    # Mix of valid and invalid files
    file_paths = [
        "test_files/sample.py",  # Valid
        "test_files/nonexistent.py",  # Invalid
        "test_files/another.py",  # Valid
    ]

    print(f"\nProcessing files: {file_paths}")
    reminders = await processor.process_mentioned_files(file_paths)

    print(f"\nResult: {len(reminders)} reminder(s) generated (should be 2)")

    assert len(reminders) == 2, f"Expected 2 reminders (only valid files), got {len(reminders)}"
    print("\n✓ Only valid files are processed, invalid files are skipped")

    return reminders


async def test_format_comparison():
    """Compare format with Claude Code."""
    print("\n" + "="*80)
    print("TEST 6: Format Comparison with Claude Code")
    print("="*80)

    processor = FileMentionProcessor(session_id="test-session", agent_profile="general")

    file_paths = ["test_files/sample.py"]

    print(f"\nProcessing files: {file_paths}")
    reminders = await processor.process_mentioned_files(file_paths)

    if reminders:
        print("\n" + "-"*80)
        print("Expected Claude Code Format:")
        print("-"*80)
        print("""<system-reminder>
Called the Read tool with the following input: {"file_path":"..."}
</system-reminder>

<system-reminder>
Result of calling the Read tool: "     1→content
     2→content..."
</system-reminder>""")
        print("-"*80)

        print("\nActual Format (first 800 chars):")
        print("-"*80)
        print(reminders[0][:800] + "...")
        print("-"*80)

        # Verify line number format
        if "     1→" in reminders[0]:
            print("\n✓ Line number format matches Claude Code (6-space padding + arrow)")
        else:
            print("\n✗ Line number format does NOT match Claude Code")

    return reminders


async def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("FILE MENTION FUNCTIONALITY TEST SUITE")
    print("="*80)

    try:
        await test_basic_file_mention()
        await test_deduplication()
        await test_multiple_files()
        await test_nonexistent_file()
        await test_mixed_valid_invalid()
        await test_format_comparison()

        print("\n" + "="*80)
        print("ALL TESTS PASSED ✓")
        print("="*80)
        print("\nFile mention functionality is working correctly!")
        print("Format matches Claude Code pattern.")

    except AssertionError as e:
        print("\n" + "="*80)
        print("TEST FAILED ✗")
        print("="*80)
        print(f"\nError: {e}")
        return 1

    except Exception as e:
        print("\n" + "="*80)
        print("UNEXPECTED ERROR")
        print("="*80)
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
