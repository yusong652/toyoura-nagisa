"""
Test script for PFC workspace synchronization.

This script tests the workspace root detection logic for PFC profile:
1. Without PFC server: Should fallback to aiNagisa/pfc_workspace
2. With PFC server: Should use PFC server's actual working directory
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from shared.utils.prompt.builder import _get_workspace_root


def test_pfc_workspace_without_server():
    """Test workspace detection when PFC server is not running."""
    print("=" * 70)
    print("Test 1: PFC workspace without server (should use fallback)")
    print("=" * 70)

    try:
        workspace = _get_workspace_root(agent_profile="pfc")
        print(f"✓ Workspace root: {workspace}")

        # Check if it's the fallback path
        expected_fallback = str(Path(__file__).parent / "pfc_workspace")
        if workspace == expected_fallback:
            print(f"✓ Using expected fallback: {expected_fallback}")
        else:
            print(f"⚠ Unexpected workspace path")
            print(f"  Expected: {expected_fallback}")
            print(f"  Got: {workspace}")

        return workspace
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_general_workspace():
    """Test workspace detection for general profile."""
    print("\n" + "=" * 70)
    print("Test 2: General profile workspace")
    print("=" * 70)

    try:
        workspace = _get_workspace_root(agent_profile="general")
        print(f"✓ Workspace root: {workspace}")

        expected_workspace = str(Path(__file__).parent / "workspace")
        if workspace == expected_workspace:
            print(f"✓ Using expected workspace: {expected_workspace}")
        else:
            print(f"⚠ Unexpected workspace path")
            print(f"  Expected: {expected_workspace}")
            print(f"  Got: {workspace}")

        return workspace
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Run all tests."""
    print("\n")
    print("PFC Workspace Synchronization Tests")
    print("=" * 70)

    # Test 1: PFC workspace without server
    pfc_workspace = test_pfc_workspace_without_server()

    # Test 2: General workspace
    general_workspace = test_general_workspace()

    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    print(f"PFC workspace (no server): {pfc_workspace}")
    print(f"General workspace: {general_workspace}")
    print()
    print("Note: To test PFC server connection, start the PFC server first")
    print("      and check the logs for workspace detection messages.")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
