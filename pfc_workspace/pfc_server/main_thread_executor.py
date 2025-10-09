"""
PFC Main Thread Executor - Thread-safe task queue for main thread execution.

This module provides task queue mechanism to execute PFC commands in the main thread
while WebSocket server runs in background thread.

Python 3.6 compatible implementation.
"""

import queue
import logging
import threading
from concurrent.futures import Future
from typing import Callable, Any

# Module logger
logger = logging.getLogger("PFC-Server")


class MainThreadExecutor:
    """
    Execute tasks in PFC IPython main thread via queue.

    WebSocket server (background thread) submits tasks via submit(),
    IPython main thread processes tasks via process_tasks().
    """

    def __init__(self):
        """Initialize executor with thread-safe queue."""
        self.task_queue = queue.Queue()
        self.main_thread_id = threading.current_thread().ident
        self.main_thread_name = threading.current_thread().name
        logger.info("✓ MainThreadExecutor initialized")
        logger.info("  Main thread: {} (ID: {})".format(
            self.main_thread_name, self.main_thread_id
        ))

    def submit(self, func, *args, **kwargs):
        # type: (Callable[..., Any], Any, Any) -> Future
        """
        Submit task to main thread queue (called from background thread).

        Args:
            func: Function to execute in main thread
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Future: Future object to await result

        Example:
            # From background thread
            future = executor.submit(itasca.command, "ball generate number 100")
            result = await loop.run_in_executor(None, future.result, timeout)
        """
        future = Future()
        self.task_queue.put((func, args, kwargs, future))
        logger.debug("Task submitted: {} (queue size: {})".format(
            func.__name__, self.task_queue.qsize()
        ))
        return future

    def process_tasks(self):
        # type: () -> int
        """
        Process all pending tasks in queue (called from main thread).

        This method should be called from IPython main thread, either:
        - Via post_execute hook (automatic after each IPython command)
        - Via manual loop (run_task_loop())

        Returns:
            int: Number of tasks processed

        Note:
            Non-blocking - processes all available tasks and returns.
        """
        # Check if we're in the main thread
        current_thread_id = threading.current_thread().ident
        current_thread_name = threading.current_thread().name
        is_main_thread = (current_thread_id == self.main_thread_id)

        if not is_main_thread:
            logger.warning(
                "⚠️  process_tasks() called from WRONG THREAD! "
                "Current: {} (ID: {}), Expected: {} (ID: {})".format(
                    current_thread_name, current_thread_id,
                    self.main_thread_name, self.main_thread_id
                )
            )

        processed_count = 0

        # Process all pending tasks
        while True:
            try:
                # Non-blocking get
                func, args, kwargs, future = self.task_queue.get_nowait()
                processed_count += 1

                # Log thread information for first task
                if processed_count == 1:
                    thread_status = "MAIN THREAD" if is_main_thread else "WRONG THREAD"
                    logger.info(
                        "Processing tasks in {} ({}, ID: {})".format(
                            thread_status, current_thread_name, current_thread_id
                        )
                    )

                try:
                    # Execute task
                    result = func(*args, **kwargs)
                    future.set_result(result)
                    logger.debug("✓ Task completed: {}".format(func.__name__))

                except Exception as e:
                    # Set exception on future
                    future.set_exception(e)
                    logger.error("✗ Task failed: {} - {}".format(func.__name__, e))

            except queue.Empty:
                # Queue empty, exit
                break

        if processed_count > 0:
            logger.info("Processed {} task(s)".format(processed_count))

        return processed_count

    def queue_size(self):
        # type: () -> int
        """
        Get current queue size.

        Returns:
            int: Number of pending tasks
        """
        return self.task_queue.qsize()
