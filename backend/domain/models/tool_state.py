"""
Tool execution state models for aiNagisa.

Domain models representing the state of tool execution workflows,
particularly for user confirmation and feedback scenarios.
"""

from dataclasses import dataclass


@dataclass
class PendingRejection:
    """
    State object for a tool execution that was rejected by user.

    Tracks rejections awaiting user feedback to be incorporated
    into the conversation context.
    """
    tool_call_id: str
    tool_name: str