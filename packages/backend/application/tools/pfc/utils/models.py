"""
Pydantic models for PFC tool parameter validation.

Provides unified validation models with consistent error messages and reusable field types.
Centralizes validation logic that was previously scattered across tool implementations.
"""

from pathlib import PurePosixPath, PureWindowsPath
from typing import Annotated, Optional
from pydantic import Field
from pydantic.functional_validators import AfterValidator


# ============================================================================
# Constants
# ============================================================================

# Task description constraints
DESCRIPTION_MIN_LENGTH = 1
DESCRIPTION_MAX_LENGTH = 200

# Pagination defaults (for task output display)
DEFAULT_OUTPUT_LINES = 64
MAX_OUTPUT_LINES = 200
DEFAULT_TASK_LIST_LIMIT = 32
MAX_TASK_LIST_LIMIT = 100

# Search limits
DEFAULT_SEARCH_LIMIT = 10
MAX_SEARCH_LIMIT = 20

# Timeout constraints (milliseconds)
MIN_TIMEOUT_MS = 1000
MAX_TIMEOUT_MS = 600000

# Wait time constraints (seconds)
MIN_WAIT_SECONDS = 1
MAX_WAIT_SECONDS = 3600


# ============================================================================
# Custom Validators
# ============================================================================

def normalize_input(value: Optional[str], lowercase: bool = False) -> str:
    """Normalize user input: collapse whitespace, optionally lowercase.

    Args:
        value: Input string to normalize
        lowercase: Whether to convert to lowercase

    Returns:
        Normalized string with collapsed whitespace
    """
    if value is None:
        return ""
    normalized = " ".join(value.split())
    return normalized.lower() if lowercase else normalized


def validate_non_empty_string(value: str) -> str:
    """Validate that a string is not empty after stripping whitespace."""
    stripped = value.strip()
    if not stripped:
        raise ValueError("Value cannot be empty or whitespace only")
    return stripped


def validate_task_description(value: str) -> str:
    """Validate task description: non-empty, within length limits."""
    stripped = value.strip()
    if not stripped:
        raise ValueError(
            "description is required. Please provide a brief explanation of what this task does. "
            "Example: 'Initial settling simulation with 10k particles'"
        )
    if len(stripped) > DESCRIPTION_MAX_LENGTH:
        raise ValueError(
            f"description is too long ({len(stripped)} characters). "
            "Please keep it concise (recommended: 30-80 characters, max: 200). "
            "Focus on the task's purpose rather than implementation details."
        )
    return stripped


def validate_script_path(value: str) -> str:
    """Validate script path: non-empty after stripping."""
    stripped = value.strip()
    if not stripped:
        raise ValueError("entry_script is required and cannot be empty")
    return stripped


def validate_output_path(value: str) -> str:
    """Validate output path: absolute, non-empty, ends with .png."""
    stripped = value.strip()
    if not stripped:
        raise ValueError("output_path is required and cannot be empty")
    if not (PurePosixPath(stripped).is_absolute() or PureWindowsPath(stripped).is_absolute()):
        raise ValueError("output_path must be an absolute path")
    if not stripped.lower().endswith('.png'):
        raise ValueError("output_path must end with .png")
    return stripped


# ============================================================================
# Annotated Types (for use in tool function signatures)
# ============================================================================

# Task ID - required, non-empty string
TaskId = Annotated[
    str,
    AfterValidator(validate_non_empty_string),
    Field(
        ...,
        min_length=1,
        description="Task ID returned by pfc_execute_task (e.g., 'a1b2c3d4')"
    )
]

# Task description - required, length-limited
TaskDescription = Annotated[
    str,
    AfterValidator(validate_task_description),
    Field(
        ...,
        min_length=DESCRIPTION_MIN_LENGTH,
        max_length=DESCRIPTION_MAX_LENGTH,
        description=(
            "Brief description of what this task does (5-15 words). "
            "Examples: 'Compression test with 100kPa confining pressure', "
            "'Triaxial shear test under drained conditions'"
        )
    )
]

# Script path - required, non-empty
ScriptPath = Annotated[
    str,
    AfterValidator(validate_script_path),
    Field(
        ...,
        min_length=1,
        description="The absolute path to the entry script to execute"
    )
]

# Output path for plot capture - required, must end with .png
PlotOutputPath = Annotated[
    str,
    AfterValidator(validate_output_path),
    Field(
        ...,
        pattern=r"(?i).*\.png$",
        description="Absolute path for PNG file. Directory auto-created if not exists."
    )
]

# Skip newest tasks for pagination (task list)
SkipNewestTasks = Annotated[
    int,
    Field(
        default=0,
        ge=0,
        description="Skip N newest tasks before selecting the page (0=latest page)."
    )
]

# Skip newest output lines for reverse-tail pagination
SkipNewestLines = Annotated[
    int,
    Field(
        default=0,
        ge=0,
        description=(
            "Skip N newest output lines before selecting the page. "
            "0 = latest page, 64 = one page older when limit=64."
        )
    )
]

# Output limit for pagination
OutputLimit = Annotated[
    int,
    Field(
        default=DEFAULT_OUTPUT_LINES,
        ge=1,
        le=MAX_OUTPUT_LINES,
        description=f"Lines to display (default: {DEFAULT_OUTPUT_LINES}, max: {MAX_OUTPUT_LINES})"
    )
]

# Optional filter text
FilterText = Annotated[
    Optional[str],
    Field(
        default=None,
        description="Optional text filter - only show lines containing this text (case-sensitive)"
    )
]

# Wait seconds for rate limiting
WaitSeconds = Annotated[
    float,
    Field(
        default=1,
        ge=MIN_WAIT_SECONDS,
        le=MAX_WAIT_SECONDS,
        description=(
            f"Wait N seconds before checking status ({MIN_WAIT_SECONDS}-{MAX_WAIT_SECONDS}s). "
            "Use to avoid frequent polling. Example: wait_seconds=30 for long simulations"
        )
    )
]

# Timeout in milliseconds
TimeoutMs = Annotated[
    Optional[int],
    Field(
        default=None,
        ge=MIN_TIMEOUT_MS,
        le=MAX_TIMEOUT_MS,
        description=(
            "Timeout in milliseconds (omit or null = no limit). "
            "Only applies when run_in_background=False. "
            "Recommended: 60000-120000ms for testing."
        )
    )
]

# Run in background flag
RunInBackground = Annotated[
    bool,
    Field(
        default=True,
        description=(
            "When true (default), returns task_id immediately without blocking. "
            "When false, waits for completion. "
            "Use pfc_check_task_status to monitor background tasks."
        )
    )
]

# Task list limit
TaskListLimit = Annotated[
    int,
    Field(
        default=DEFAULT_TASK_LIST_LIMIT,
        ge=1,
        le=MAX_TASK_LIST_LIMIT,
        description=f"Max tasks to return (default: {DEFAULT_TASK_LIST_LIMIT}, max: {MAX_TASK_LIST_LIMIT})"
    )
]

# Search query
SearchQuery = Annotated[
    str,
    AfterValidator(validate_non_empty_string),
    Field(
        ...,
        min_length=1,
        description=(
            "Search keywords for PFC commands. Examples: 'ball create', "
            "'contact property', 'model solve'. Case-insensitive."
        )
    )
]

# Python API search query
PythonAPISearchQuery = Annotated[
    str,
    AfterValidator(validate_non_empty_string),
    Field(
        ...,
        min_length=1,
        description=(
            "Search keywords for PFC Python SDK API. Examples: 'ball pos', "
            "'contact force', 'model solve'. Case-insensitive."
        )
    )
]

# Search limit
SearchLimit = Annotated[
    int,
    Field(
        default=DEFAULT_SEARCH_LIMIT,
        ge=1,
        le=MAX_SEARCH_LIMIT,
        description=f"Maximum number of results (1-{MAX_SEARCH_LIMIT})."
    )
]
