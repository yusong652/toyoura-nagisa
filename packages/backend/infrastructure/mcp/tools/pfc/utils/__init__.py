"""
PFC tool utilities.

Contains shared utilities for PFC MCP tools:
- models: Pydantic validation models and constants
- task_status_formatter: Task status formatting for LLM output
"""

from .models import (
    # Constants
    DESCRIPTION_MIN_LENGTH,
    DESCRIPTION_MAX_LENGTH,
    DEFAULT_OUTPUT_LINES,
    MAX_OUTPUT_LINES,
    DEFAULT_TASK_LIST_LIMIT,
    MAX_TASK_LIST_LIMIT,
    DEFAULT_SEARCH_LIMIT,
    MAX_SEARCH_LIMIT,
    MIN_TIMEOUT_MS,
    MAX_TIMEOUT_MS,
    MIN_WAIT_SECONDS,
    MAX_WAIT_SECONDS,
    # Annotated types
    TaskId,
    TaskDescription,
    ScriptPath,
    PlotOutputPath,
    OutputOffset,
    OutputLimit,
    FilterText,
    WaitSeconds,
    TimeoutMs,
    RunInBackground,
    TaskListLimit,
    SearchQuery,
    SearchLimit,
)

from .task_status_formatter import (
    TaskStatusData,
    FormattedTaskStatus,
    CONTEXT_INJECTION_MAX_CHARS,
    paginate_output,
    format_task_status_for_llm,
    format_task_status_for_context,
    create_task_status_data,
)

__all__ = [
    # Constants from models
    "DESCRIPTION_MIN_LENGTH",
    "DESCRIPTION_MAX_LENGTH",
    "DEFAULT_OUTPUT_LINES",
    "MAX_OUTPUT_LINES",
    "DEFAULT_TASK_LIST_LIMIT",
    "MAX_TASK_LIST_LIMIT",
    "DEFAULT_SEARCH_LIMIT",
    "MAX_SEARCH_LIMIT",
    "MIN_TIMEOUT_MS",
    "MAX_TIMEOUT_MS",
    "MIN_WAIT_SECONDS",
    "MAX_WAIT_SECONDS",
    # Annotated types from models
    "TaskId",
    "TaskDescription",
    "ScriptPath",
    "PlotOutputPath",
    "OutputOffset",
    "OutputLimit",
    "FilterText",
    "WaitSeconds",
    "TimeoutMs",
    "RunInBackground",
    "TaskListLimit",
    "SearchQuery",
    "SearchLimit",
    # From task_status_formatter
    "TaskStatusData",
    "FormattedTaskStatus",
    "CONTEXT_INJECTION_MAX_CHARS",
    "paginate_output",
    "format_task_status_for_llm",
    "format_task_status_for_context",
    "create_task_status_data",
]
