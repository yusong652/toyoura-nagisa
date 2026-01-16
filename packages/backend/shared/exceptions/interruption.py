"""
User interruption exceptions for toyoura-nagisa.

This module defines exceptions that represent user-initiated interruptions
rather than system errors, enabling graceful handling of user rejections
and feedback cycles.
"""

from typing import List, Optional




class UserRejectionInterruption(Exception):
    """
    User rejected tool execution - request should be interrupted.

    This represents a deliberate user interruption, not a system error.
    When raised, the request should:
    1. Save context with rejection responses (already done)
    2. NOT trigger content processing (post-processing, etc.)
    3. Wait for user's next input to continue naturally

    This follows Claude Code's standard pattern where tool rejections
    cause immediate interruption, and user feedback continues via new requests.
    """

    def __init__(self, session_id: str, rejected_tools: List[str], message: Optional[str] = None):
        """
        Initialize user rejection interruption.

        Args:
            session_id: Session where rejection occurred
            rejected_tools: List of tool names that were rejected
            message: Optional custom interruption message
        """
        self.session_id = session_id
        self.rejected_tools = rejected_tools
        self.interruption_type = 'user_rejection'

        if message:
            self.message = message
        else:
            tool_list = ', '.join(rejected_tools)
            self.message = f"User rejected tools: {tool_list}"

        super().__init__(self.message)

    def __str__(self) -> str:
        return f"UserRejectionInterruption(session={self.session_id}, tools={self.rejected_tools})"

    def __repr__(self) -> str:
        return self.__str__()
