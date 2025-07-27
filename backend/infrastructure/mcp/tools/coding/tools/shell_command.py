"""run_shell_command tool – secure shell command execution with enterprise-grade protection.

This tool provides atomic shell command execution functionality, focusing exclusively on 
running shell commands with comprehensive monitoring and security controls. It provides 
real-time resource monitoring, security analysis, and multi-platform support.

Modeled after gemini-cli's execution capabilities for consistency and interoperability.
"""

import os
import sys
import subprocess
import shutil
import time
import psutil
import signal
import json
import shlex
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from pydantic import Field
from pydantic.fields import FieldInfo
from fastmcp import FastMCP  # type: ignore

from ..utils.path_security import (
    validate_path_in_workspace, 
    WORKSPACE_ROOT, 
    is_safe_symlink, 
    check_parent_symlinks
)
from backend.infrastructure.mcp.utils.tool_result import ToolResult
from .constants import (
    MAX_FILES_DEFAULT,
    TEXT_CHARSET_DEFAULT,
)

__all__ = ["run_shell_command", "register_shell_command_tool"]

# -----------------------------------------------------------------------------
# Constants and execution limits
# -----------------------------------------------------------------------------

# Timeout settings
DEFAULT_TIMEOUT = 60   # seconds
MIN_TIMEOUT = 1        # minimum allowed timeout
MAX_TIMEOUT = 600      # 10 minutes maximum
KILL_TIMEOUT = 5       # seconds to wait for graceful shutdown

# Output size limits
MAX_OUTPUT_SIZE = 20 * 1024 * 1024  # 20MB total output limit
OUTPUT_TRUNCATE_SIZE = 2 * 1024 * 1024  # 2MB truncation threshold
MAX_LINE_LENGTH = 10000  # Maximum line length to prevent memory issues

# Resource limits
MAX_MEMORY_MB = 1024  # 1GB memory limit
MAX_CPU_PERCENT = 80  # Maximum CPU usage percentage
MAX_OPEN_FILES = 100  # Maximum open file descriptors

# Execution categories
EXECUTION_CATEGORIES = {
    "quick": {"timeout": 10, "memory_mb": 256},
    "normal": {"timeout": 60, "memory_mb": 512},
    "long": {"timeout": 300, "memory_mb": 1024},
    "intensive": {"timeout": 600, "memory_mb": 2048},
}

# Safe command patterns (whitelist for common operations)
SAFE_COMMAND_PATTERNS = {
    "file_ops": ["ls", "find", "grep", "cat", "head", "tail", "wc", "sort", "uniq"],
    "text_ops": ["sed", "awk", "cut", "tr", "tee", "diff", "patch"],
    "archive_ops": ["tar", "zip", "unzip", "gzip", "gunzip"],
    "build_ops": ["make", "cmake", "npm", "yarn", "pip", "cargo", "go", "javac"],
    "version_control": ["git", "svn", "hg"],
    "system_info": ["ps", "top", "df", "du", "free", "uname", "which", "whoami"],
}

# Dangerous command patterns (for security analysis)
DANGEROUS_COMMAND_PATTERNS = {
    "destructive": ["rm -rf", "rmdir", "del", "format", "mkfs", "fdisk"],
    "system_modify": ["chmod 777", "chown", "sudo", "su", "passwd"],
    "network": ["nc", "netcat", "telnet", "ssh", "scp", "rsync"],
    "privilege": ["sudo", "su", "doas", "pkexec"],
    "process": ["kill -9", "killall", "pkill"],
    "redirect": ["> /dev/", "dd if=", "dd of="],
    "eval": ["eval", "source", "bash -c", "sh -c", "python -c"],
}

# -----------------------------------------------------------------------------
# Enums for type safety
# -----------------------------------------------------------------------------

class ExecutionMode(str, Enum):
    """Execution mode options."""
    QUICK = "quick"
    NORMAL = "normal"
    LONG = "long"
    INTENSIVE = "intensive"
    CUSTOM = "custom"

class CommandCategory(str, Enum):
    """Command category types."""
    SAFE = "safe"
    MODERATE = "moderate"
    DANGEROUS = "dangerous"
    UNKNOWN = "unknown"

class PlatformType(str, Enum):
    """Platform type options."""
    WINDOWS = "windows"
    POSIX = "posix"
    UNKNOWN = "unknown"

# -----------------------------------------------------------------------------
# Data structures for execution results
# -----------------------------------------------------------------------------

@dataclass
class ResourceUsage:
    """Resource usage statistics."""
    peak_memory_mb: float
    avg_cpu_percent: float
    execution_time: float
    max_open_files: int
    memory_exceeded: bool
    cpu_exceeded: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "peak_memory_mb": self.peak_memory_mb,
            "avg_cpu_percent": self.avg_cpu_percent,
            "execution_time": self.execution_time,
            "max_open_files": self.max_open_files,
            "memory_exceeded": self.memory_exceeded,
            "cpu_exceeded": self.cpu_exceeded,
        }

@dataclass
class CommandOutput:
    """Command output with metadata."""
    stdout: str
    stderr: str
    combined_size: int
    stdout_truncated: bool
    stderr_truncated: bool
    encoding: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "combined_size": self.combined_size,
            "stdout_truncated": self.stdout_truncated,
            "stderr_truncated": self.stderr_truncated,
            "encoding": self.encoding,
        }

@dataclass
class SecurityAnalysis:
    """Security analysis of the command."""
    command_category: CommandCategory
    dangerous_patterns: List[str]
    safe_patterns: List[str]
    privilege_required: bool
    network_access: bool
    file_modification: bool
    security_score: float  # 0.0 to 1.0, higher is safer
    warnings: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_category": self.command_category.value,
            "dangerous_patterns": self.dangerous_patterns,
            "safe_patterns": self.safe_patterns,
            "privilege_required": self.privilege_required,
            "network_access": self.network_access,
            "file_modification": self.file_modification,
            "security_score": self.security_score,
            "warnings": self.warnings,
        }

class ExecutionResult:
    """Comprehensive execution result with rich metadata."""
    
    def __init__(
        self,
        exit_code: int,
        output: CommandOutput,
        resource_usage: ResourceUsage,
        security_analysis: SecurityAnalysis,
        command: str,
        parsed_command: List[str],
        working_directory: str,
        environment: Dict[str, str],
        execution_mode: ExecutionMode,
        platform: PlatformType,
        timeout_occurred: bool = False,
        killed_by_signal: bool = False,
        error_message: Optional[str] = None,
    ):
        self.exit_code = exit_code
        self.output = output
        self.resource_usage = resource_usage
        self.security_analysis = security_analysis
        self.command = command
        self.parsed_command = parsed_command
        self.working_directory = working_directory
        self.environment = environment
        self.execution_mode = execution_mode
        self.platform = platform
        self.timeout_occurred = timeout_occurred
        self.killed_by_signal = killed_by_signal
        self.error_message = error_message
        self.timestamp = datetime.now().isoformat()
    
    @property
    def success(self) -> bool:
        """Check if execution was successful."""
        return self.exit_code == 0 and not self.timeout_occurred and not self.killed_by_signal
    
    @property
    def execution_category(self) -> str:
        """Get execution category based on performance."""
        if self.resource_usage.execution_time > 60:
            return "long_running"
        elif self.resource_usage.peak_memory_mb > 500:
            return "memory_intensive"
        elif self.resource_usage.avg_cpu_percent > 50:
            return "cpu_intensive"
        else:
            return "lightweight"
    
    def get_summary(self) -> Dict[str, Any]:
        """Get execution summary statistics."""
        return {
            "execution_status": "success" if self.success else "failed",
            "exit_code": self.exit_code,
            "execution_category": self.execution_category,
            "execution_time": self.resource_usage.execution_time,
            "peak_memory_mb": self.resource_usage.peak_memory_mb,
            "output_size": self.output.combined_size,
            "security_score": self.security_analysis.security_score,
            "command_category": self.security_analysis.command_category.value,
            "timeout_occurred": self.timeout_occurred,
            "killed_by_signal": self.killed_by_signal,
            "has_warnings": len(self.security_analysis.warnings) > 0,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "exit_code": self.exit_code,
            "output": self.output.to_dict(),
            "resource_usage": self.resource_usage.to_dict(),
            "security_analysis": self.security_analysis.to_dict(),
            "execution_metadata": {
                "command": self.command,
                "parsed_command": self.parsed_command,
                "working_directory": self.working_directory,
                "environment": self.environment,
                "execution_mode": self.execution_mode.value,
                "platform": self.platform.value,
                "timestamp": self.timestamp,
                "timeout_occurred": self.timeout_occurred,
                "killed_by_signal": self.killed_by_signal,
                "error_message": self.error_message,
            },
            "summary": self.get_summary(),
        }

# -----------------------------------------------------------------------------
# Helper utilities
# -----------------------------------------------------------------------------

def _truncate_output(output: str, max_size: int = OUTPUT_TRUNCATE_SIZE) -> Tuple[str, bool]:
    """Truncate output if too large, return (content, was_truncated)."""
    if len(output) <= max_size:
        return output, False
    
    # Smart truncation: try to preserve meaningful content
    lines = output.split('\n')
    if len(lines) > 1000:  # Too many lines
        truncated_lines = lines[:500] + ["", "... [TRUNCATED - too many lines] ...", ""] + lines[-500:]
        truncated = '\n'.join(truncated_lines)
    else:
        truncated = output[:max_size]
    
    truncated += f"\n\n... [OUTPUT TRUNCATED - exceeded {max_size // 1024}KB limit] ..."
    return truncated, True

def _get_platform_type() -> PlatformType:
    """Get the current platform type."""
    if os.name == "nt":
        return PlatformType.WINDOWS
    elif os.name == "posix":
        return PlatformType.POSIX
    else:
        return PlatformType.UNKNOWN

def _get_shell_executable() -> List[str]:
    """Get the appropriate shell executable for the platform."""
    platform = _get_platform_type()
    
    if platform == PlatformType.WINDOWS:
        return ["cmd.exe", "/c"]
    else:
        # Prefer bash if available, fallback to sh
        bash_path = shutil.which("bash")
        if bash_path:
            return [bash_path, "-c"]
        else:
            return ["sh", "-c"]

def _analyze_command_security(command: str) -> SecurityAnalysis:
    """Analyze command for security risks."""
    dangerous_patterns = []
    safe_patterns = []
    warnings = []
    
    command_lower = command.lower()
    
    # Check for dangerous patterns
    for category, patterns in DANGEROUS_COMMAND_PATTERNS.items():
        for pattern in patterns:
            if pattern in command_lower:
                dangerous_patterns.append(pattern)
                warnings.append(f"Dangerous {category} pattern detected: {pattern}")
    
    # Check for safe patterns
    command_tokens = shlex.split(command) if command else []
    first_command = command_tokens[0] if command_tokens else ""
    
    for category, patterns in SAFE_COMMAND_PATTERNS.items():
        for pattern in patterns:
            if first_command.endswith(pattern) or pattern in first_command:
                safe_patterns.append(pattern)
                break
    
    # Determine command category
    if dangerous_patterns:
        if len(dangerous_patterns) > 2:
            command_category = CommandCategory.DANGEROUS
        else:
            command_category = CommandCategory.MODERATE
    elif safe_patterns:
        command_category = CommandCategory.SAFE
    else:
        command_category = CommandCategory.UNKNOWN
    
    # Calculate security score
    base_score = 1.0
    if dangerous_patterns:
        base_score -= len(dangerous_patterns) * 0.3
    if safe_patterns:
        base_score += len(safe_patterns) * 0.1
    
    security_score = max(0.0, min(1.0, base_score))
    
    # Analyze specific risks
    privilege_required = any(p in command_lower for p in ["sudo", "su", "doas", "pkexec"])
    network_access = any(p in command_lower for p in ["curl", "wget", "nc", "telnet", "ssh"])
    file_modification = any(p in command_lower for p in ["rm", "mv", "cp", "chmod", "chown", ">", ">>"])
    
    # Additional warnings
    if privilege_required:
        warnings.append("Command requires elevated privileges")
        security_score *= 0.7
    
    if network_access:
        warnings.append("Command may access network resources")
        security_score *= 0.8
    
    if file_modification:
        warnings.append("Command may modify files or permissions")
        security_score *= 0.9
    
    return SecurityAnalysis(
        command_category=command_category,
        dangerous_patterns=dangerous_patterns,
        safe_patterns=safe_patterns,
        privilege_required=privilege_required,
        network_access=network_access,
        file_modification=file_modification,
        security_score=security_score,
        warnings=warnings,
    )

def _monitor_process(process: subprocess.Popen, timeout: int) -> ResourceUsage:
    """Monitor process resource usage."""
    start_time = time.time()
    peak_memory = 0.0
    cpu_samples = []
    max_files = 0
    memory_exceeded = False
    cpu_exceeded = False
    
    try:
        ps_process = psutil.Process(process.pid)
        
        while process.poll() is None:
            try:
                # Memory monitoring
                memory_info = ps_process.memory_info()
                current_memory = memory_info.rss / 1024 / 1024  # MB
                peak_memory = max(peak_memory, current_memory)
                
                if current_memory > MAX_MEMORY_MB:
                    memory_exceeded = True
                
                # CPU monitoring
                cpu_percent = ps_process.cpu_percent()
                cpu_samples.append(cpu_percent)
                
                if cpu_percent > MAX_CPU_PERCENT:
                    cpu_exceeded = True
                
                # File descriptor monitoring
                try:
                    open_files = ps_process.num_fds()
                    max_files = max(max_files, open_files)
                except (AttributeError, psutil.AccessDenied):
                    pass  # Not supported on all platforms
                
                time.sleep(0.1)  # Sample every 100ms
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
                
        execution_time = time.time() - start_time
        avg_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0.0
        
    except Exception:
        execution_time = time.time() - start_time
        avg_cpu = 0.0
    
    return ResourceUsage(
        peak_memory_mb=peak_memory,
        avg_cpu_percent=avg_cpu,
        execution_time=execution_time,
        max_open_files=max_files,
        memory_exceeded=memory_exceeded,
        cpu_exceeded=cpu_exceeded,
    )

def _prepare_environment(custom_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Prepare execution environment."""
    env = os.environ.copy()
    
    # Add safe defaults
    env.setdefault('LANG', 'C.UTF-8')
    env.setdefault('LC_ALL', 'C.UTF-8')
    
    # Security: Remove potentially dangerous environment variables
    dangerous_vars = ['LD_PRELOAD', 'LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH']
    for var in dangerous_vars:
        env.pop(var, None)
    
    # Add custom environment variables
    if custom_env:
        for key, value in custom_env.items():
            if isinstance(key, str) and isinstance(value, str):
                env[key] = value
    
    return env

def _execute_command_safely(
    command: str,
    working_dir: Path,
    timeout: int,
    environment: Dict[str, str],
    execution_mode: ExecutionMode,
    platform: PlatformType,
) -> ExecutionResult:
    """Execute command with comprehensive monitoring and safety checks."""
    
    # Prepare command
    shell_exe = _get_shell_executable()
    full_command = shell_exe + [command]
    
    # Parse command for analysis
    try:
        parsed_command = shlex.split(command)
    except ValueError:
        parsed_command = [command]  # Fallback for unparseable commands
    
    # Security analysis
    security_analysis = _analyze_command_security(command)
    
    # Initialize result tracking
    start_time = time.time()
    exit_code = -1
    timeout_occurred = False
    killed_by_signal = False
    error_message = None
    
    try:
        # Start process
        process = subprocess.Popen(
            full_command,
            cwd=str(working_dir),
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )
        
        # Monitor process in parallel
        resource_usage = _monitor_process(process, timeout)
        
        # Wait for completion with timeout
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            exit_code = process.returncode
            
        except subprocess.TimeoutExpired:
            timeout_occurred = True
            
            # Try graceful shutdown first
            try:
                process.terminate()
                stdout, stderr = process.communicate(timeout=KILL_TIMEOUT)
                exit_code = process.returncode
            except subprocess.TimeoutExpired:
                # Force kill if graceful shutdown fails
                process.kill()
                killed_by_signal = True
                try:
                    stdout, stderr = process.communicate(timeout=1)
                    exit_code = process.returncode
                except subprocess.TimeoutExpired:
                    stdout, stderr = "", ""
                    exit_code = -9  # SIGKILL
            
            error_message = f"Command execution timed out after {timeout} seconds"
            
        # Process output
        combined_size = len(stdout) + len(stderr)
        
        if combined_size > MAX_OUTPUT_SIZE:
            error_message = f"Output size ({combined_size // 1024}KB) exceeds limit ({MAX_OUTPUT_SIZE // 1024}KB)"
            stdout = stdout[:MAX_OUTPUT_SIZE // 2]
            stderr = stderr[:MAX_OUTPUT_SIZE // 2]
            combined_size = MAX_OUTPUT_SIZE
        
        stdout_truncated, stderr_truncated = False, False
        if len(stdout) > OUTPUT_TRUNCATE_SIZE:
            stdout, stdout_truncated = _truncate_output(stdout)
        if len(stderr) > OUTPUT_TRUNCATE_SIZE:
            stderr, stderr_truncated = _truncate_output(stderr)
        
        # Create output object
        output = CommandOutput(
            stdout=stdout,
            stderr=stderr,
            combined_size=combined_size,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
            encoding=TEXT_CHARSET_DEFAULT,
        )
        
        # Update resource usage with final execution time
        resource_usage.execution_time = time.time() - start_time
        
    except Exception as e:
        error_message = f"Process execution failed: {e}"
        exit_code = -2
        
        # Create minimal output for error case
        output = CommandOutput(
            stdout="",
            stderr=str(e),
            combined_size=len(str(e)),
            stdout_truncated=False,
            stderr_truncated=False,
            encoding=TEXT_CHARSET_DEFAULT,
        )
        
        resource_usage = ResourceUsage(
            peak_memory_mb=0.0,
            avg_cpu_percent=0.0,
            execution_time=time.time() - start_time,
            max_open_files=0,
            memory_exceeded=False,
            cpu_exceeded=False,
        )
    
    return ExecutionResult(
        exit_code=exit_code,
        output=output,
        resource_usage=resource_usage,
        security_analysis=security_analysis,
        command=command,
        parsed_command=parsed_command,
        working_directory=str(working_dir),
        environment=environment,
        execution_mode=execution_mode,
        platform=platform,
        timeout_occurred=timeout_occurred,
        killed_by_signal=killed_by_signal,
        error_message=error_message,
    )

# -----------------------------------------------------------------------------
# Main implementation
# -----------------------------------------------------------------------------

def run_shell_command(
    command: str = Field(
        ...,
        description="Shell command to execute. Examples: 'ls -la', 'python test.py', 'npm install', 'git status'. Use complete command strings with pipes, redirects, etc.",
    ),
    execution_mode: ExecutionMode = Field(
        ExecutionMode.NORMAL,
        description="Choose execution profile based on expected command behavior:\n- 'quick': Fast commands (10s, 256MB) - file listings, simple queries\n- 'normal': Standard commands (60s, 512MB) - builds, tests, git operations\n- 'long': Extended commands (300s, 1GB) - complex builds, large file operations\n- 'intensive': Heavy commands (600s, 2GB) - compilation, system operations\n- 'custom': Specify your own timeout/memory limits",
    ),
    timeout: Optional[int] = Field(
        None,
        description="Custom timeout in seconds (1-600). Required only when execution_mode='custom'. Choose based on expected command duration.",
    ),
    memory_limit_mb: Optional[int] = Field(
        None,
        description="Custom memory limit in MB (1-2048). Required only when execution_mode='custom'. Choose based on expected memory usage.",
    ),
    working_directory: Optional[str] = Field(
        None,
        description="Directory to run command in (relative to workspace root). Examples: 'src', 'frontend', 'backend/tests'. Defaults to workspace root if not specified.",
    ),
    environment: Optional[Dict[str, str]] = Field(
        None,
        description="Environment variables to set. Examples: {'NODE_ENV': 'test'}, {'DEBUG': '1'}. Useful for configuring build tools and applications.",
    ),
    allow_dangerous: bool = Field(
        False,
        description="Override safety checks for potentially risky commands. Only set to True if you understand the risks and need to run system-modifying commands.",
    ),
    capture_output: bool = Field(
        True,
        description="Capture command output for analysis. Keep True unless running interactive or daemon processes where output capture would interfere.",
    ),
    analyze_security: bool = Field(
        True,
        description="Perform security analysis before execution. Recommended to keep True for safety unless you're confident about command safety.",
    ),
) -> Dict[str, Any]:
    """Execute shell commands with monitoring, security analysis, and resource management.
    
    ## When to Use This Tool
    Use this tool whenever you need to run shell commands, including:
    - Running builds and tests (`npm run build`, `pytest`, `make test`)
    - File operations (`ls`, `find`, `grep`, `cat`)
    - Git operations (`git status`, `git add`, `git commit`)
    - Package management (`pip install`, `npm install`, `cargo build`)
    - System queries (`ps`, `df`, `which`, `uname`)
    - Development tasks (`python script.py`, `node app.js`)
    
    ## Quick Start Guide
    Most common usage patterns:
    ```python
    # Simple command - use defaults
    run_shell_command(command="ls -la")
    
    # Build command - use 'long' mode for extended operations
    run_shell_command(command="npm run build", execution_mode="long")
    
    # Command in specific directory
    run_shell_command(command="python test.py", working_directory="backend/tests")
    
    # Risky command - override safety checks
    run_shell_command(command="rm -rf temp/", allow_dangerous=True)
    ```
    
    ## Understanding Results
    Key fields to check:
    - `result.success`: True if command succeeded (exit code 0)
    - `result.exit_code`: Command exit code (0 = success, non-zero = error)
    - `result.stdout`: Command output text
    - `result.stderr`: Error messages and warnings
    - `summary.execution_category`: Performance classification
    - `warnings`: Security concerns (if any)
    
    ## Return Format
    Returns structured data with three main sections:
    - `operation`: What was executed and how
    - `result`: Command output and execution details
    - `summary`: Quick overview of success/failure and characteristics
    
    ## Execution Modes
    Choose based on expected command behavior:
    - **quick**: Fast commands like `ls`, `cat`, `which` (10s, 256MB)
    - **normal**: Standard commands like `git`, `npm test` (60s, 512MB) 
    - **long**: Extended operations like `npm install`, `make` (300s, 1GB)
    - **intensive**: Heavy tasks like compilation (600s, 2GB)
    - **custom**: Specify your own limits
    
    ## Security Features
    - Automatic analysis of potentially dangerous commands
    - Workspace-only execution (cannot escape project directory)
    - Resource monitoring and limits
    - Safe environment variable handling
    - Command pattern recognition
    
    The tool automatically prevents dangerous operations unless explicitly allowed.
    
    """

    # ------------------------------------------------------------------
    # Parameter validation and normalization
    # ------------------------------------------------------------------

    # Handle Pydantic FieldInfo objects when invoked programmatically
    if isinstance(execution_mode, FieldInfo):
        execution_mode = ExecutionMode.NORMAL
    if isinstance(timeout, FieldInfo):
        timeout = None
    if isinstance(memory_limit_mb, FieldInfo):
        memory_limit_mb = None
    if isinstance(working_directory, FieldInfo):
        working_directory = None
    if isinstance(environment, FieldInfo):
        environment = None
    if isinstance(allow_dangerous, FieldInfo):
        allow_dangerous = False
    if isinstance(capture_output, FieldInfo):
        capture_output = True
    if isinstance(analyze_security, FieldInfo):
        analyze_security = True

    # Helper shortcuts for consistent results
    def _error(message: str, suggestion: str = None) -> Dict[str, Any]:
        error_msg = message
        if suggestion:
            error_msg += f" Suggestion: {suggestion}"
        return ToolResult(status="error", message=error_msg, error=message).model_dump()

    def _success(message: str, llm_content: Any, **data: Any) -> Dict[str, Any]:
        return ToolResult(
            status="success",
            message=message,
            llm_content=llm_content,
            data=data,
        ).model_dump()

    # Validate command
    if not command or not command.strip():
        return _error("Command cannot be empty", "Provide a shell command to execute, e.g., 'ls -la' or 'python script.py'")

    # Validate execution mode and set resource limits
    if execution_mode == ExecutionMode.CUSTOM:
        if timeout is None or memory_limit_mb is None:
            return _error(
                "timeout and memory_limit_mb must be specified for custom execution mode",
                "Provide both timeout (e.g., 120) and memory_limit_mb (e.g., 512) parameters, or use a predefined execution_mode like 'normal'"
            )
        
        if not (MIN_TIMEOUT <= timeout <= MAX_TIMEOUT):
            return _error(
                f"timeout must be between {MIN_TIMEOUT} and {MAX_TIMEOUT} seconds",
                f"Use a timeout between {MIN_TIMEOUT}-{MAX_TIMEOUT} seconds, or choose 'normal' (60s), 'long' (300s), or 'intensive' (600s) execution mode"
            )
        
        if not (1 <= memory_limit_mb <= 2048):
            return _error(
                "memory_limit_mb must be between 1 and 2048 MB",
                "Use memory_limit_mb between 1-2048 MB, or choose 'normal' (512MB), 'long' (1GB), or 'intensive' (2GB) execution mode"
            )
        
        actual_timeout = timeout
        actual_memory_limit = memory_limit_mb
    else:
        limits = EXECUTION_CATEGORIES[execution_mode.value]
        actual_timeout = limits["timeout"]
        actual_memory_limit = limits["memory_mb"]
    
    # Store limits for potential use in monitoring
    _ = actual_memory_limit  # Acknowledge variable is set but not used in current implementation

    # Validate workspace access
    if not validate_path_in_workspace("."):
        return _error("Cannot access workspace directory", "Ensure you're running from within a valid workspace directory")

    # ------------------------------------------------------------------
    # Path validation and security checks
    # ------------------------------------------------------------------

    # Validate working directory
    if working_directory:
        abs_workdir = validate_path_in_workspace(working_directory)
        if abs_workdir is None:
            return _error(
                f"Working directory is outside workspace: {working_directory}",
                "Use a path relative to the workspace root, e.g., 'src', 'backend', or 'frontend/tests'"
            )
        
        work_dir = Path(abs_workdir)
        if not work_dir.exists():
            return _error(
                f"Working directory does not exist: {working_directory}",
                "Check the path spelling or create the directory first using mkdir command"
            )
        if not work_dir.is_dir():
            return _error(
                f"Working directory is not a directory: {working_directory}",
                "Specify a directory path, not a file path"
            )
        
        # Security checks for working directory
        if work_dir.is_symlink() and not is_safe_symlink(work_dir):
            return _error("Cannot use unsafe working directory symlink", "Use a regular directory path instead of a symlink")
        if not check_parent_symlinks(work_dir):
            return _error("Cannot use working directory with unsafe parent symlinks", "Use a directory path without symlinks in the parent chain")
    else:
        work_dir = Path(str(WORKSPACE_ROOT))

    # Security analysis
    if analyze_security:
        security_analysis = _analyze_command_security(command)
        
        # Check for dangerous commands if not explicitly allowed
        if not allow_dangerous:
            if security_analysis.command_category == CommandCategory.DANGEROUS:
                return _error(
                    f"Dangerous command detected: {', '.join(security_analysis.dangerous_patterns)}",
                    "Set allow_dangerous=True to override safety checks, or use a safer alternative command"
                )
            
            if security_analysis.security_score < 0.3:
                return _error(
                    f"Command security score too low ({security_analysis.security_score:.2f})",
                    "Set allow_dangerous=True to override, or modify the command to be safer"
                )

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------

    try:
        # Prepare environment
        exec_environment = _prepare_environment(environment)
        
        # Get platform info
        platform = _get_platform_type()
        
        # Execute command with monitoring
        result = _execute_command_safely(
            command=command,
            working_dir=work_dir,
            timeout=actual_timeout,
            environment=exec_environment,
            execution_mode=execution_mode,
            platform=platform,
        )

        # Build user-facing message
        if result.success:
            message = f"Command executed successfully (exit code {result.exit_code}, {result.resource_usage.execution_time:.1f}s, {result.resource_usage.peak_memory_mb:.1f}MB peak memory)"
        elif result.timeout_occurred:
            message = f"Command timed out after {actual_timeout}s ({result.resource_usage.peak_memory_mb:.1f}MB peak memory). Consider using a longer execution mode or optimizing the command"
        elif result.killed_by_signal:
            message = f"Command was forcibly terminated (exit code {result.exit_code}, {result.resource_usage.execution_time:.1f}s). Process consumed too many resources or was unresponsive"
        else:
            message = f"Command failed with exit code {result.exit_code} ({result.resource_usage.execution_time:.1f}s). Check stderr output for error details"

        # Add warnings indicator if any security issues
        if result.security_analysis.warnings:
            message += f" Note: {len(result.security_analysis.warnings)} security warning(s) detected"
        
        # Add resource limit warnings
        if result.resource_usage.memory_exceeded or result.resource_usage.cpu_exceeded:
            resource_warnings = []
            if result.resource_usage.memory_exceeded:
                resource_warnings.append("memory limit exceeded")
            if result.resource_usage.cpu_exceeded:
                resource_warnings.append("CPU limit exceeded")
            message += f" Warning: {', '.join(resource_warnings)} - consider using 'intensive' execution mode"

        # Build structured LLM content following unified standard
        # Focus on the most relevant information for LLM decision-making
        llm_content = {
            "operation": {
                "type": "shell_command",
                "command": command,
                "execution_mode": execution_mode.value,
                "working_directory": str(work_dir.relative_to(WORKSPACE_ROOT)) if str(work_dir).startswith(str(WORKSPACE_ROOT)) else str(work_dir),
                "timeout_occurred": result.timeout_occurred,
                "killed_by_signal": result.killed_by_signal
            },
            "result": {
                "exit_code": result.exit_code,
                "stdout": result.output.stdout,
                "stderr": result.output.stderr,
                "success": result.success,
                "execution_time": result.resource_usage.execution_time,
                "peak_memory_mb": result.resource_usage.peak_memory_mb
            },
            "summary": {
                "operation_type": "shell_command",
                "success": result.success,
                "execution_category": result.execution_category,
                "security_score": result.security_analysis.security_score,
                "has_warnings": len(result.security_analysis.warnings) > 0
            }
        }
        
        # Add interpretation hints for LLM
        if not result.success:
            llm_content["interpretation"] = {
                "likely_cause": "Command error" if result.exit_code != 0 else "Timeout or resource limit",
                "next_steps": "Check stderr for error details" if result.output.stderr else "Review command syntax and requirements"
            }
        
        # Add performance guidance for LLM
        if result.resource_usage.execution_time > 30:
            llm_content["performance_note"] = "Long execution time - consider optimization or using 'long' execution mode"
        elif result.resource_usage.peak_memory_mb > 500:
            llm_content["performance_note"] = "High memory usage - consider using 'intensive' execution mode for similar commands"
        
        # Add warnings only if they exist - prioritize most important ones
        if result.security_analysis.warnings:
            llm_content["warnings"] = {
                "count": len(result.security_analysis.warnings),
                "top_warnings": result.security_analysis.warnings[:3],  # Limit to first 3 warnings
                "security_advice": "Consider using safer alternatives or review command necessity"
            }
        
        # Add truncation info if output was truncated
        if result.output.stdout_truncated or result.output.stderr_truncated:
            llm_content["truncation_info"] = {
                "stdout_truncated": result.output.stdout_truncated,
                "stderr_truncated": result.output.stderr_truncated,
                "combined_size": result.output.combined_size,
                "note": "Full output available in detailed data section"
            }

        return _success(
            message,
            llm_content,
            **result.to_dict(),
        )

    except Exception as exc:
        return _error(
            f"Unexpected error during command execution: {exc}",
            "Check command syntax and ensure required dependencies are installed"
        )

# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_shell_command_tool(mcp: FastMCP):
    """Register the run_shell_command tool with proper tags and metadata."""
    common = dict(
        tags={"coding", "execution", "shell", "command", "system", "monitoring", "security"}, 
        annotations={
            "category": "coding", 
            "tags": ["coding", "execution", "shell", "command", "system", "monitoring", "security"],
            "primary_use": "Execute shell commands with comprehensive monitoring",
            "prompt_optimization": "Enhanced for LLM interaction with clear guidance and structured outputs"
        }
    )
    mcp.tool(**common)(run_shell_command) 