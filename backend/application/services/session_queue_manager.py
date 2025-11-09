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
from typing import Dict, Optional, List
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

        # Message merging configuration (Claude Code style)
        self._merge_enabled = True  # Enable message merging
        self._merge_window = 0.8  # Wait 0.8s to collect messages
        self._max_merge_count = 10  # Max 10 messages per merge

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
        Process all messages in the queue sequentially with Claude Code style merging.

        This is the main processing loop. It intelligently merges rapid consecutive
        messages into a single request (like Claude Code does), improving efficiency
        and user experience.

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

                # Strategy: Wait a bit to collect multiple messages before processing
                # This allows rapid consecutive messages to be batched together
                current_queue_size = queue.qsize()
                print(f"[QueueManager] Queue has {current_queue_size} message(s), waiting {self._merge_window}s to collect more...", flush=True)

                if self._merge_enabled and current_queue_size > 0:
                    # Wait for merge window to allow more messages to arrive
                    await asyncio.sleep(self._merge_window)

                    # Check queue size again after waiting
                    final_queue_size = queue.qsize()
                    print(f"[QueueManager] After waiting, queue has {final_queue_size} message(s)", flush=True)

                # Collect all messages currently in queue (up to max_merge_count)
                messages_to_process = []
                max_to_collect = self._max_merge_count if self._merge_enabled else 1

                # Get current queue size before collecting
                messages_available = queue.qsize()
                print(f"[QueueManager] Attempting to collect {min(max_to_collect, messages_available)} messages from queue", flush=True)

                for i in range(min(max_to_collect, messages_available)):
                    try:
                        message = await asyncio.wait_for(queue.get(), timeout=0.5)
                        messages_to_process.append(message)

                        # Debug: show message content
                        msg_preview = str(message.get('content', ''))[:50] if isinstance(message, dict) else str(message)[:50]
                        print(f"[QueueManager] Collected message {i+1}: {msg_preview}", flush=True)
                    except asyncio.TimeoutError:
                        print(f"[QueueManager] Timeout getting message {i+1}, stopping collection", flush=True)
                        break

                # Fallback: if no messages collected, try with longer timeout
                if not messages_to_process:
                    try:
                        message = await asyncio.wait_for(queue.get(), timeout=1.0)
                        messages_to_process.append(message)
                    except asyncio.TimeoutError:
                        logger.debug(f"Queue get timeout for session {session_id}, checking if empty")
                        continue

                if len(messages_to_process) > 1:
                    print(f"[QueueManager] Collected {len(messages_to_process)} messages for merging", flush=True)

                # Mark all collected messages as retrieved from queue
                for _ in messages_to_process:
                    queue.task_done()

                # Send queue position update to frontend before processing
                await self._notify_processing_start(session_id, queue.qsize())

                # Process the message(s) - merge if multiple
                logger.info(f"Processing {len(messages_to_process)} message(s) for session {session_id}. Remaining in queue: {queue.qsize()}")
                print(f"[QueueManager] Processing {len(messages_to_process)} message(s)", flush=True)

                try:
                    if len(messages_to_process) == 1:
                        # Single message - process normally
                        print(f"[QueueManager] Single message mode - processing directly", flush=True)
                        await message_processor_callback(session_id, messages_to_process[0])
                    else:
                        # Multiple messages - merge and process
                        print(f"[QueueManager] Merging {len(messages_to_process)} messages...", flush=True)
                        merged_message = self._merge_messages(messages_to_process)
                        print(f"[QueueManager] Merged message preview: {str(merged_message.get('content', ''))[:200]}...", flush=True)
                        await message_processor_callback(session_id, merged_message)
                except Exception as e:
                    logger.error(f"Error processing message for session {session_id}: {e}")
                    # Continue processing next message even if this one failed
                    # Send error notification to frontend
                    await self._notify_processing_error(session_id, str(e))

                # Send queue update to frontend
                await self._notify_queue_update(session_id, queue.qsize())

        finally:
            # Always mark processing as complete when loop exits
            async with self._lock:
                self._processing[session_id] = False
                logger.info(f"Finished processing queue for session {session_id}")

    async def _try_collect_messages(self, session_id: str, queue: asyncio.Queue) -> List[dict]:
        """
        Try to collect additional messages from queue within merge window.

        Implements Claude Code style message merging by waiting a short time
        to see if more messages arrive, then collecting them for batch processing.

        Args:
            session_id: Session identifier
            queue: Message queue for this session

        Returns:
            List[dict]: Additional messages collected (empty if none)
        """
        collected = []
        merge_deadline = asyncio.get_event_loop().time() + self._merge_window

        while len(collected) < self._max_merge_count - 1:  # -1 because first message already retrieved
            # Calculate remaining time in merge window
            remaining_time = merge_deadline - asyncio.get_event_loop().time()
            if remaining_time <= 0:
                break

            try:
                # Try to get message with remaining timeout
                message = await asyncio.wait_for(
                    queue.get(),
                    timeout=min(remaining_time, 0.2)  # Check every 0.2s
                )
                collected.append(message)
                logger.debug(f"Collected message {len(collected)} for merging in session {session_id}")

            except asyncio.TimeoutError:
                # No more messages within timeout
                break
            except Exception as e:
                logger.warning(f"Error collecting messages for merge: {e}")
                break

        if collected:
            logger.info(f"Collected {len(collected)} additional messages for merging in session {session_id}")

        return collected

    def _merge_messages(self, messages: List[dict]) -> dict:
        """
        Merge multiple messages into a single formatted message (Claude Code style).

        Formats messages in a clear way that helps the LLM understand the user
        sent multiple consecutive messages that should be processed together.

        Args:
            messages: List of message data dictionaries

        Returns:
            dict: Merged message data with formatted content

        Example output (Claude Code style - English):
            "<system-reminder>
            The user sent the following message:
            1

            Please address this message and continue with your tasks.
            </system-reminder>

            <system-reminder>
            The user sent the following message:
            2

            Please address this message and continue with your tasks.
            </system-reminder>
            ..."
        """
        if len(messages) == 1:
            return messages[0]

        # Extract message texts
        message_texts = []
        for msg in messages:
            content = msg.get('content', '')
            if isinstance(content, str):
                message_texts.append(content)
            elif isinstance(content, list):
                # Handle multimodal messages (text + images)
                text_parts = [item.get('text', '') for item in content if item.get('type') == 'text']
                message_texts.append(' '.join(text_parts))

        # Format merged message in Claude Code style (system-reminder blocks)
        formatted_parts = []
        for text in message_texts:
            reminder_block = f"""<system-reminder>
The user sent the following message:
{text}

Please address this message and continue with your tasks.
</system-reminder>"""
            formatted_parts.append(reminder_block)

        formatted_content = '\n\n'.join(formatted_parts)

        # Create merged message data (use first message as template)
        merged = messages[0].copy()
        merged['content'] = formatted_content
        merged['_merged_count'] = len(messages)  # Metadata for debugging
        merged['_original_messages'] = message_texts  # Keep originals for reference

        logger.info(f"Merged {len(messages)} messages into single request (Claude Code style)")
        return merged

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
                MessageType.MESSAGE_PROCESSING_START,
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
