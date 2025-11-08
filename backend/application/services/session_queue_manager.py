"""
Session-based message queue management service.

This module provides message queueing functionality to prevent message loss
when users send multiple messages while LLM is processing. Instead of rejecting
duplicate requests, messages are queued and processed sequentially.

Key Features:
1. Per-session message queues using asyncio.Queue
2. Automatic sequential processing (FIFO)
3. Queue status notifications to frontend
4. Graceful handling of concurrent message submissions

Architecture:
    User Message → Queue → Sequential Processing → Next Message

Example Flow:
    User sends Message1 → Processing
    User sends Message2 → Queued (position 1)
    User sends Message3 → Queued (position 2)
    Message1 complete → Auto-process Message2
"""

import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class SessionQueueManager:
    """
    Manages per-session message queues for sequential processing.

    Prevents message loss when users send multiple messages during LLM processing.
    Each session has its own queue, ensuring messages are processed in order.
    """

    def __init__(self):
        """Initialize the queue manager with empty state."""
        self._queues: Dict[str, asyncio.Queue] = {}  # session_id -> Queue of message_data
        self._processing: Dict[str, bool] = {}  # session_id -> is_processing flag
        self._lock = asyncio.Lock()  # Protect queue creation and state updates

    async def enqueue_message(self, session_id: str, message_data: dict) -> int:
        """
        Add a message to the session's queue.

        Args:
            session_id: Session identifier
            message_data: Complete message data to be processed (includes message content, files, etc.)

        Returns:
            int: Queue position (0 = processing now, 1+ = waiting in queue)
        """
        async with self._lock:
            # Create queue if it doesn't exist
            if session_id not in self._queues:
                self._queues[session_id] = asyncio.Queue()
                self._processing[session_id] = False

            # Add message to queue
            await self._queues[session_id].put(message_data)
            queue_size = self._queues[session_id].qsize()

            logger.info(f"Message queued for session {session_id}. Queue size: {queue_size}")

            # Return queue position (0 if being processed, otherwise position in queue)
            if self._processing[session_id]:
                return queue_size  # Position in waiting queue
            else:
                return 0  # Will be processed immediately

    async def start_processing(self, session_id: str) -> bool:
        """
        Start processing the message queue for a session.

        Only starts if not already processing. This prevents duplicate
        processing loops for the same session.

        Args:
            session_id: Session identifier

        Returns:
            bool: True if processing started, False if already processing
        """
        async with self._lock:
            if self._processing.get(session_id, False):
                logger.debug(f"Session {session_id} already processing, skipping start")
                return False

            self._processing[session_id] = True
            logger.info(f"Started processing queue for session {session_id}")
            return True

    async def process_queue(self, session_id: str, message_processor_callback):
        """
        Process all messages in the queue sequentially.

        This is the main processing loop. It processes messages one by one
        until the queue is empty, then marks the session as idle.

        Args:
            session_id: Session identifier
            message_processor_callback: Async function to process each message
                Signature: async def callback(session_id: str, message_data: dict) -> None
        """
        try:
            while True:
                # Get queue for this session
                queue = self._queues.get(session_id)
                if not queue:
                    logger.warning(f"No queue found for session {session_id}")
                    break

                # Check if queue is empty
                if queue.empty():
                    logger.info(f"Queue empty for session {session_id}, stopping processing")
                    break

                # Get next message (non-blocking check first to avoid hanging)
                try:
                    message_data = await asyncio.wait_for(queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    logger.debug(f"Queue get timeout for session {session_id}, checking if empty")
                    continue

                # Send queue position update to frontend before processing
                await self._notify_processing_start(session_id, queue.qsize())

                # Process the message
                logger.info(f"Processing message for session {session_id}. Remaining in queue: {queue.qsize()}")
                try:
                    await message_processor_callback(session_id, message_data)
                except Exception as e:
                    logger.error(f"Error processing message for session {session_id}: {e}")
                    # Continue processing next message even if this one failed
                    # Send error notification to frontend
                    await self._notify_processing_error(session_id, str(e))

                # Mark task as done
                queue.task_done()

                # Send queue update to frontend
                await self._notify_queue_update(session_id, queue.qsize())

        finally:
            # Always mark processing as complete when loop exits
            async with self._lock:
                self._processing[session_id] = False
                logger.info(f"Finished processing queue for session {session_id}")

    def is_processing(self, session_id: str) -> bool:
        """
        Check if a session is currently processing messages.

        Args:
            session_id: Session identifier

        Returns:
            bool: True if processing, False otherwise
        """
        return self._processing.get(session_id, False)

    def get_queue_size(self, session_id: str) -> int:
        """
        Get the current queue size for a session.

        Args:
            session_id: Session identifier

        Returns:
            int: Number of messages waiting in queue (0 if no queue exists)
        """
        queue = self._queues.get(session_id)
        return queue.qsize() if queue else 0

    async def clear_queue(self, session_id: str) -> int:
        """
        Clear all pending messages in a session's queue.

        Useful for handling user interrupts or session resets.

        Args:
            session_id: Session identifier

        Returns:
            int: Number of messages cleared
        """
        async with self._lock:
            queue = self._queues.get(session_id)
            if not queue:
                return 0

            cleared_count = 0
            while not queue.empty():
                try:
                    queue.get_nowait()
                    queue.task_done()
                    cleared_count += 1
                except asyncio.QueueEmpty:
                    break

            logger.info(f"Cleared {cleared_count} messages from session {session_id} queue")
            return cleared_count

    async def _notify_queue_update(self, session_id: str, queue_size: int):
        """
        Send queue size update to frontend via WebSocket.

        Args:
            session_id: Session identifier
            queue_size: Current queue size
        """
        try:
            from backend.infrastructure.websocket.connection_manager import get_connection_manager
            from backend.presentation.websocket.message_types import create_message, MessageType

            connection_manager = get_connection_manager()
            if not connection_manager:
                return

            # Create queue update message
            queue_msg = create_message(
                MessageType.QUEUE_UPDATE,
                session_id=session_id,
                payload={
                    "queue_size": queue_size,
                    "is_processing": self._processing.get(session_id, False),
                    "timestamp": datetime.now().isoformat()
                }
            )

            await connection_manager.send_json(session_id, queue_msg.model_dump())

        except Exception as e:
            logger.error(f"Failed to send queue update notification: {e}")

    async def _notify_processing_start(self, session_id: str, remaining_in_queue: int):
        """
        Notify frontend that a message is starting to be processed.

        Args:
            session_id: Session identifier
            remaining_in_queue: Number of messages still waiting
        """
        try:
            from backend.infrastructure.websocket.connection_manager import get_connection_manager
            from backend.presentation.websocket.message_types import create_message, MessageType

            connection_manager = get_connection_manager()
            if not connection_manager:
                return

            # Create processing start message
            processing_msg = create_message(
                MessageType.PROCESSING_START,
                session_id=session_id,
                payload={
                    "remaining_in_queue": remaining_in_queue,
                    "timestamp": datetime.now().isoformat()
                }
            )

            await connection_manager.send_json(session_id, processing_msg.model_dump())

        except Exception as e:
            logger.error(f"Failed to send processing start notification: {e}")

    async def _notify_processing_error(self, session_id: str, error_message: str):
        """
        Notify frontend that message processing encountered an error.

        Args:
            session_id: Session identifier
            error_message: Error description
        """
        try:
            from backend.infrastructure.websocket.connection_manager import get_connection_manager
            from backend.presentation.websocket.message_types import create_message, MessageType

            connection_manager = get_connection_manager()
            if not connection_manager:
                return

            # Create error message
            error_msg = create_message(
                MessageType.ERROR,
                session_id=session_id,
                error_code="QUEUE_PROCESSING_ERROR",
                error_message=error_message,
                details={"timestamp": datetime.now().isoformat()}
            )

            await connection_manager.send_json(session_id, error_msg.model_dump())

        except Exception as e:
            logger.error(f"Failed to send processing error notification: {e}")


# Global queue manager instance
_queue_manager: Optional[SessionQueueManager] = None


def get_queue_manager() -> SessionQueueManager:
    """
    Get or create the global queue manager instance.

    Returns:
        SessionQueueManager: The singleton queue manager instance
    """
    global _queue_manager
    if _queue_manager is None:
        _queue_manager = SessionQueueManager()
    return _queue_manager


def set_queue_manager(manager: SessionQueueManager):
    """
    Set the global queue manager instance.

    Args:
        manager: SessionQueueManager instance to set as global
    """
    global _queue_manager
    _queue_manager = manager
