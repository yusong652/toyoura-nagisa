"""
PFC Server Managers.

State managers for handling various server-side concerns.
"""

from .quick_console import QuickConsoleManager
from .git_version import GitVersionManager, get_git_manager, find_git_root
from .interrupt import (
    request_interrupt,
    check_interrupt,
    clear_interrupt,
    get_pending_interrupts,
    set_current_task,
    clear_current_task,
    get_current_task,
    register_interrupt_callback,
    unregister_interrupt_callback,
    is_callback_registered,
)

__all__ = [
    # Quick console
    "QuickConsoleManager",
    # Git version
    "GitVersionManager",
    "get_git_manager",
    "find_git_root",
    # Interrupt
    "request_interrupt",
    "check_interrupt",
    "clear_interrupt",
    "get_pending_interrupts",
    "set_current_task",
    "clear_current_task",
    "get_current_task",
    "register_interrupt_callback",
    "unregister_interrupt_callback",
    "is_callback_registered",
]
