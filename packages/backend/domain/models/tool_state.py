"""
Tool execution state models for toyoura-nagisa.

Domain models representing the state of tool execution workflows,
particularly for user confirmation and feedback scenarios.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class PendingRejection:
    """
    State object for a tool execution that was rejected by user and awaiting feedback.

    Uses asyncio.Future to elegantly pause tool execution while waiting for user feedback,
    allowing the original tool calling chain to resume without duplicating streaming logic.
    The function_call context is preserved in the execution stack, not stored here.
    """
    tool_call_id: str
    tool_name: str
    active: bool = True
    feedback_future: Optional[asyncio.Future] = field(default_factory=lambda: asyncio.Future())