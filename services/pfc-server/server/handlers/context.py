"""
Server Context for Handler Dependency Injection.

Provides a centralized context object containing all dependencies
that handlers need to perform their operations.
"""

from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from ..task_manager import TaskManager
    from ..script_executor import PFCScriptExecutor
    from ..main_thread_executor import MainThreadExecutor
    from ..quick_console_manager import QuickConsoleManager


class ServerContext:
    """
    Context object providing access to server dependencies for handlers.

    This class serves as a dependency injection container, allowing handlers
    to access shared resources without tight coupling to the server class.

    Attributes:
        task_manager: Manages task lifecycle and status tracking
        script_executor: Executes PFC Python scripts
        main_executor: Queue-based main thread execution
        quick_console_managers: Cache of QuickConsoleManager per workspace
    """

    def __init__(
        self,
        task_manager,  # type: TaskManager
        script_executor,  # type: PFCScriptExecutor
        main_executor,  # type: MainThreadExecutor
        quick_console_managers,  # type: Dict[str, QuickConsoleManager]
    ):
        # type: (...) -> None
        """
        Initialize server context with required dependencies.

        Args:
            task_manager: Task lifecycle manager
            script_executor: PFC script executor
            main_executor: Main thread executor for queue-based execution
            quick_console_managers: Dict mapping workspace paths to QuickConsoleManager
        """
        self.task_manager = task_manager
        self.script_executor = script_executor
        self.main_executor = main_executor
        self.quick_console_managers = quick_console_managers

    def get_quick_console_manager(self, workspace_path):
        # type: (str) -> QuickConsoleManager
        """
        Get or create QuickConsoleManager for a workspace.

        Args:
            workspace_path: Absolute path to the PFC workspace directory

        Returns:
            QuickConsoleManager instance for the workspace
        """
        from ..quick_console_manager import QuickConsoleManager

        if workspace_path not in self.quick_console_managers:
            self.quick_console_managers[workspace_path] = QuickConsoleManager(workspace_path)
        return self.quick_console_managers[workspace_path]
