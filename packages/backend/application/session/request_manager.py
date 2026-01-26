"""
Request lifecycle management service.

This module provides request deduplication and lifecycle management
for chat requests, ensuring only one active request per session.
"""

import asyncio
from typing import Dict, Optional
from contextlib import asynccontextmanager
import logging

logger = logging.getLogger(__name__)


class RequestManager:
    """
    Elegant request state management with automatic lifecycle handling.

    Provides clean context manager interface for request deduplication
    and state cleanup, eliminating the need for manual lock management
    in business logic.
    """

    def __init__(self):
        self._active_requests: Dict[str, str] = {}  # session_id -> request_id
        self._lock = asyncio.Lock()

    async def try_start_request(self, session_id: str, request_id: str, user_message_id: Optional[str] = None) -> bool:
        """
        Attempt to start a new request, rejecting if session already has active request.

        Args:
            session_id: Session identifier
            request_id: Unique request identifier
            user_message_id: Optional message ID for error notifications

        Returns:
            bool: True if request started successfully, False if duplicate detected
        """
        async with self._lock:
            if session_id in self._active_requests:
                existing_request = self._active_requests[session_id]
                error_msg = f"Duplicate request detected. Session {session_id} already has active request {existing_request}"

                # Send error notification if message ID available
                if user_message_id:
                    from backend.application.notifications import get_message_status_service
                    status_service = get_message_status_service()
                    if status_service:
                        await status_service.notify_error(session_id, user_message_id, error_msg)

                return False

            self._active_requests[session_id] = request_id
            return True

    async def finish_request(self, session_id: str, request_id: str) -> None:
        """
        Complete request and clean up state.

        Args:
            session_id: Session identifier
            request_id: Request identifier (for verification)
        """
        async with self._lock:
            # Only remove if it's the same request (defensive programming)
            if (session_id in self._active_requests and
                self._active_requests[session_id] == request_id):
                del self._active_requests[session_id]

    @asynccontextmanager
    async def request_context(self, session_id: str, request_id: str, user_message_id: Optional[str] = None):
        """
        Context manager for automatic request lifecycle management.

        Args:
            session_id: Session identifier
            request_id: Unique request identifier
            user_message_id: Optional message ID for error notifications

        Raises:
            Exception: If duplicate request detected (via return from context)
        """
        if not await self.try_start_request(session_id, request_id, user_message_id):
            # Duplicate request detected, early return (no cleanup needed)
            return

        try:
            yield  # Execute the request
        finally:
            await self.finish_request(session_id, request_id)


# Global request manager instance
request_manager = RequestManager()


def get_request_manager() -> RequestManager:
    """
    Get the global request manager instance.

    Returns:
        RequestManager: The singleton request manager instance
    """
    return request_manager
