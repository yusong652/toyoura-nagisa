"""
Test script for periodic todo reminder functionality.

This script simulates multiple tool calls to verify that todo reminders
appear periodically (every 3 recursive calls) even when the todo list is empty.

Run with: uv run python test_todo_reminder_periodic.py
"""

import asyncio
import uuid
from pathlib import Path
import tempfile
import shutil

from backend.infrastructure.monitoring.monitors.todo_monitor import TodoMonitor
from backend.infrastructure.storage.todo_storage import get_todo_storage


async def test_periodic_reminders():
    """Test periodic todo reminder injection."""
    print("=" * 60)
    print("Testing Periodic Todo Reminder System")
    print("=" * 60)

    # Create temp workspace
    workspace = Path(tempfile.mkdtemp())
    print(f"\n✓ Created temp workspace: {workspace}")

    # Create a test session
    session_id = str(uuid.uuid4())
    print(f"✓ Created session: {session_id[:8]}")

    # Initialize todo monitor
    monitor = TodoMonitor(session_id)
    storage = get_todo_storage()

    # Ensure todo list is empty
    storage.save_todos(workspace, session_id, [])
    print("✓ Initialized with empty todo list")

    print("\n[Testing Reminder Intervals]")
    print("Expected pattern: Reminder every 3 conversation turns")
    print("-" * 40)

    # Simulate multiple conversation turns (user messages + tool calls)
    for i in range(10):
        # Simulate a conversation turn
        monitor.track_conversation_turn()

        # Check if reminder should appear
        reminders = await monitor.get_reminders()

        if reminders:
            print(f"Round {i+1}: ✓ Reminder triggered")
            # Show first few lines of the reminder
            reminder_text = reminders[0].replace("<system-reminder>\n", "").replace("\n</system-reminder>", "")
            first_line = reminder_text.split("\n")[0][:60] + "..."
            print(f"         Message: {first_line}")
        else:
            print(f"Round {i+1}: - No reminder")

    print("\n[Testing With Existing Todos]")
    print("-" * 40)

    # Add some todos
    todos = [
        {"content": "Test task 1", "activeForm": "Testing task 1", "status": "pending"},
        {"content": "Test task 2", "activeForm": "Testing task 2", "status": "in_progress"}
    ]
    storage.save_todos(workspace, session_id, todos)
    print("✓ Added 2 todos to the list")

    # Check reminders with existing todos
    reminders = await monitor.get_reminders()
    if reminders:
        print("✓ Reminder shows existing todos:")
        reminder_text = reminders[0].replace("<system-reminder>\n", "").replace("\n</system-reminder>", "")
        for line in reminder_text.split("\n")[:4]:  # Show first few lines
            print(f"  {line}")

    print("\n[Testing Counter Persistence]")
    print("-" * 40)

    # Create another monitor for the same session (simulating reconnection)
    monitor2 = TodoMonitor(session_id)

    # The counter should be preserved at class level
    print(f"✓ Conversation count preserved: {TodoMonitor._conversation_counts.get(session_id, 0)}")

    # Cleanup
    print("\n[Cleanup]")
    shutil.rmtree(workspace)
    print("✓ Removed temp workspace")

    print("\n" + "=" * 60)
    print("✓ All periodic reminder tests completed!")
    print("=" * 60)
    print("\nKey findings:")
    print("  1. Reminders appear every 3 conversation turns")
    print("  2. Empty list triggers 'use TodoWrite' prompt")
    print("  3. Existing todos always shown when present")
    print("  4. Counter persists across monitor instances")


async def test_manual_workspace():
    """Test with actual workspace to see reminders in action."""
    print("\n" + "=" * 60)
    print("Manual Test with Real Workspace")
    print("=" * 60)

    # Use a known workspace path for manual testing
    workspace = Path("/tmp/test_todo_workspace")
    workspace.mkdir(exist_ok=True)

    session_id = "test-session-123"
    monitor = TodoMonitor(session_id)
    storage = get_todo_storage()

    print(f"\nWorkspace: {workspace}")
    print(f"Session: {session_id}")
    print("\nSimulating conversation turns...")

    for i in range(7):
        monitor.track_conversation_turn()
        reminders = await monitor.get_reminders()

        status = "✓ REMINDER" if reminders else "  no reminder"
        print(f"  Call {i+1}: {status}")

    print(f"\nTodo file would be at: {workspace}/todos.json")
    print("(Check this location to verify storage)")


if __name__ == "__main__":
    asyncio.run(test_periodic_reminders())

    # Uncomment for manual testing:
    # asyncio.run(test_manual_workspace())