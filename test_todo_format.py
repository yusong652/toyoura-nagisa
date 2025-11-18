"""Test todo reminder format matches Claude Code exactly."""

import asyncio
from pathlib import Path
import tempfile
import shutil

from backend.infrastructure.monitoring.monitors.todo_monitor import TodoMonitor
from backend.infrastructure.storage.todo_storage import get_todo_storage


async def test_format():
    """Test that our format matches Claude Code."""
    workspace = Path(tempfile.mkdtemp())
    session_id = 'test-format-123'
    monitor = TodoMonitor(session_id)
    storage = get_todo_storage()

    print("Testing Todo Format (Claude Code style)")
    print("=" * 50)

    # Add some todos
    todos = [
        {'content': 'Review and verify todo reminder format', 'activeForm': 'Reviewing', 'status': 'in_progress'},
        {'content': 'Compare with Claude Code injection format', 'activeForm': 'Comparing', 'status': 'pending'},
        {'content': 'Update format if needed', 'activeForm': 'Updating', 'status': 'pending'}
    ]
    storage.save_todos(workspace, session_id, todos)

    # Force a reminder (3 turns)
    for _ in range(3):
        monitor.track_conversation_turn()

    # Mock the workspace resolution
    import unittest.mock as mock
    with mock.patch('backend.infrastructure.monitoring.monitors.todo_monitor.get_workspace_for_session_sync', return_value=workspace):
        reminders = await monitor.get_reminders()
    if reminders:
        # Extract just the content without tags
        content = reminders[0].replace('<system-reminder>\n', '').replace('\n</system-reminder>', '')
        print("\nGenerated format:")
        print("-" * 50)
        print(content)
        print("-" * 50)

        print("\nExpected Claude Code format:")
        print("-" * 50)
        print("Here are the existing contents of your todo list:")
        print("")
        print("[1. [in_progress] Review and verify todo reminder format")
        print("2. [pending] Compare with Claude Code injection format")
        print("3. [pending] Update format if needed]")
        print("-" * 50)

        # Check if format matches
        expected = """Here are the existing contents of your todo list:

[1. [in_progress] Review and verify todo reminder format
2. [pending] Compare with Claude Code injection format
3. [pending] Update format if needed]"""

        if content == expected:
            print("\n✅ FORMAT MATCHES CLAUDE CODE EXACTLY!")
        else:
            print("\n❌ Format differs from Claude Code")
            print("\nDifferences:")
            for i, (line1, line2) in enumerate(zip(content.split('\n'), expected.split('\n')), 1):
                if line1 != line2:
                    print(f"  Line {i}:")
                    print(f"    Got:      '{line1}'")
                    print(f"    Expected: '{line2}'")

    shutil.rmtree(workspace)


if __name__ == "__main__":
    asyncio.run(test_format())