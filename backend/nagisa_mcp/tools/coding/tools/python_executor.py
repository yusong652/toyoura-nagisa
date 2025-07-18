"""execute_python_script tool – secure Python script execution with enterprise-grade protection.

This tool provides atomic Python script execution functionality, focusing exclusively on 
running Python scripts with comprehensive monitoring and security controls. It does NOT 
create or modify files - use write_file for script creation.

Modeled after gemini-cli's execution capabilities for consistency and interoperability.
"""

import os
import sys
import subprocess
import time
import psutil
import signal
import json
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
from backend.nagisa_mcp.utils.tool_result import ToolResult
from .constants import (
    MAX_FILES_DEFAULT,
    TEXT_CHARSET_DEFAULT,
)

__all__ = ["execute_python_script", "register_python_executor_tools"]

# -----------------------------------------------------------------------------
# Constants and execution limits
# -----------------------------------------------------------------------------

# Timeout settings
DEFAULT_TIMEOUT = 30  # seconds
MIN_TIMEOUT = 1       # minimum allowed timeout
MAX_TIMEOUT = 600     # 10 minutes maximum for long-running scripts
KILL_TIMEOUT = 5      # seconds to wait for graceful shutdown

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
    "normal": {"timeout": 30, "memory_mb": 512},
    "long": {"timeout": 300, "memory_mb": 1024},
    "intensive": {"timeout": 600, "memory_mb": 2048},
}

# Safe Python modules (whitelist for security analysis)
SAFE_MODULES = {
    "os", "sys", "json", "math", "datetime", "time", "random", "re", "collections",
    "itertools", "functools", "operator", "pathlib", "typing", "dataclasses",
    "enum", "argparse", "logging", "unittest", "pytest", "numpy", "pandas",
    "matplotlib", "scipy", "sklearn", "requests", "urllib", "http", "hashlib",
}

# Potentially dangerous modules (for warnings)
DANGEROUS_MODULES = {
    "subprocess", "multiprocessing", "threading", "socket", "ftplib", "telnetlib",
    "smtplib", "poplib", "imaplib", "nntplib", "pickle", "marshal", "ctypes",
    "importlib", "runpy", "code", "codeop", "compile", "eval", "exec",
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

class ResourceLimitType(str, Enum):
    """Resource limit types."""
    MEMORY = "memory"
    CPU = "cpu"
    TIME = "time"
    FILES = "files"

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
class ExecutionOutput:
    """Execution output with metadata."""
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
    """Security analysis of the script."""
    dangerous_imports: List[str]
    safe_imports: List[str]
    unknown_imports: List[str]
    security_score: float  # 0.0 to 1.0, higher is safer
    warnings: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "dangerous_imports": self.dangerous_imports,
            "safe_imports": self.safe_imports,
            "unknown_imports": self.unknown_imports,
            "security_score": self.security_score,
            "warnings": self.warnings,
        }

class ExecutionResult:
    """Comprehensive execution result with rich metadata."""
    
    def __init__(
        self,
        exit_code: int,
        output: ExecutionOutput,
        resource_usage: ResourceUsage,
        security_analysis: SecurityAnalysis,
        script_path: str,
        working_directory: str,
        command: List[str],
        environment: Dict[str, str],
        execution_mode: ExecutionMode,
        timeout_occurred: bool = False,
        killed_by_signal: bool = False,
        error_message: Optional[str] = None,
    ):
        self.exit_code = exit_code
        self.output = output
        self.resource_usage = resource_usage
        self.security_analysis = security_analysis
        self.script_path = script_path
        self.working_directory = working_directory
        self.command = command
        self.environment = environment
        self.execution_mode = execution_mode
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
                "script_path": self.script_path,
                "working_directory": self.working_directory,
                "command": self.command,
                "environment": self.environment,
                "execution_mode": self.execution_mode.value,
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

def _get_python_executable() -> str:
    """Get the appropriate Python executable path."""
    # Priority: PYTHON env var > sys.executable > python3 > python
    candidates = [
        os.getenv("PYTHON"),
        sys.executable,
        "python3",
        "python",
    ]
    
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    
    return sys.executable  # Fallback

def _analyze_script_security(script_path: Path) -> SecurityAnalysis:
    """Analyze script for security risks."""
    dangerous_imports = []
    safe_imports = []
    unknown_imports = []
    warnings = []
    
    try:
        with script_path.open('r', encoding=TEXT_CHARSET_DEFAULT, errors='ignore') as f:
            content = f.read()
        
        # Simple import analysis using regex
        import re
        import_pattern = r'(?:^|\n)\s*(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        imports = re.findall(import_pattern, content)
        
        for module in set(imports):
            if module in DANGEROUS_MODULES:
                dangerous_imports.append(module)
                warnings.append(f"Potentially dangerous import: {module}")
            elif module in SAFE_MODULES:
                safe_imports.append(module)
            else:
                unknown_imports.append(module)
        
        # Calculate security score
        total_imports = len(imports) if imports else 1
        dangerous_count = len(dangerous_imports)
        security_score = max(0.0, 1.0 - (dangerous_count * 0.3 / total_imports))
        
        # Additional warnings
        if 'eval(' in content or 'exec(' in content:
            warnings.append("Script contains eval() or exec() - potential security risk")
            security_score *= 0.7
        
        if '__import__' in content:
            warnings.append("Script uses dynamic imports - potential security risk")
            security_score *= 0.8
        
    except Exception as e:
        warnings.append(f"Could not analyze script security: {e}")
        security_score = 0.5  # Unknown risk
    
    return SecurityAnalysis(
        dangerous_imports=dangerous_imports,
        safe_imports=safe_imports,
        unknown_imports=unknown_imports,
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
    env.setdefault('PYTHONPATH', '')
    env.setdefault('PYTHONIOENCODING', 'utf-8')
    env.setdefault('PYTHONUNBUFFERED', '1')
    
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

def _execute_script_safely(
    script_path: Path,
    args: List[str],
    working_dir: Path,
    timeout: int,
    environment: Dict[str, str],
    execution_mode: ExecutionMode,
) -> ExecutionResult:
    """Execute script with comprehensive monitoring and safety checks."""
    
    # Prepare command
    python_executable = _get_python_executable()
    command = [python_executable, str(script_path)] + args
    
    # Security analysis
    security_analysis = _analyze_script_security(script_path)
    
    # Initialize result tracking
    start_time = time.time()
    exit_code = -1
    timeout_occurred = False
    killed_by_signal = False
    error_message = None
    
    try:
        # Start process
        process = subprocess.Popen(
            command,
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
            
            error_message = f"Script execution timed out after {timeout} seconds"
            
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
        output = ExecutionOutput(
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
        output = ExecutionOutput(
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
        script_path=str(script_path),
        working_directory=str(working_dir),
        command=command,
        environment=environment,
        execution_mode=execution_mode,
        timeout_occurred=timeout_occurred,
        killed_by_signal=killed_by_signal,
        error_message=error_message,
    )

# -----------------------------------------------------------------------------
# Main implementation
# -----------------------------------------------------------------------------

def execute_python_script(
    path: str = Field(
        ...,
        description="Workspace-relative path to the Python script (.py) to execute.",
    ),
    args: Optional[List[str]] = Field(
        None,
        description="Command-line arguments to pass to the script (e.g., ['--file', 'data.csv', '--retries', '3']).",
    ),
    execution_mode: ExecutionMode = Field(
        ExecutionMode.NORMAL,
        description="Execution mode: 'quick' (10s, 256MB), 'normal' (30s, 512MB), 'long' (300s, 1GB), 'intensive' (600s, 2GB), 'custom'.",
    ),
    timeout: Optional[int] = Field(
        None,
        description="Custom timeout in seconds (1-600). Only used with 'custom' execution mode.",
    ),
    memory_limit_mb: Optional[int] = Field(
        None,
        description="Custom memory limit in MB (1-2048). Only used with 'custom' execution mode.",
    ),
    working_directory: Optional[str] = Field(
        None,
        description="Working directory for script execution (workspace-relative). Defaults to script's directory.",
    ),
    environment: Optional[Dict[str, str]] = Field(
        None,
        description="Additional environment variables to set for the script execution.",
    ),
    capture_output: bool = Field(
        True,
        description="Whether to capture stdout/stderr. WARNING: Setting to False makes LLM 'blind' to script execution - use only for long-running scripts where output is not needed.",
    ),
    analyze_security: bool = Field(
        True,
        description="Whether to perform security analysis of the script before execution.",
    ),
) -> Dict[str, Any]:
    """Execute Python scripts with comprehensive monitoring, security analysis, and resource management.
    
    Returns execution results with stdout/stderr, resource usage, and security analysis.
    Use for running Python scripts with enterprise-grade controls and monitoring.
    """

    # ------------------------------------------------------------------
    # Parameter validation and normalization
    # ------------------------------------------------------------------

    # Handle Pydantic FieldInfo objects when invoked programmatically
    if isinstance(args, FieldInfo):
        args = None
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
    if isinstance(capture_output, FieldInfo):
        capture_output = True
    if isinstance(analyze_security, FieldInfo):
        analyze_security = True

    # Helper shortcuts for consistent results
    def _error(message: str) -> Dict[str, Any]:
        return ToolResult(status="error", message=message, error=message).model_dump()

    def _success(message: str, llm_content: Any, **data: Any) -> Dict[str, Any]:
        return ToolResult(
            status="success",
            message=message,
            llm_content=llm_content,
            data=data,
        ).model_dump()

    # Validate and normalize arguments
    args = args or []
    if not isinstance(args, list):
        return _error("args must be a list of strings")
    
    args = [str(arg) for arg in args]

    # Validate execution mode and set resource limits
    if execution_mode == ExecutionMode.CUSTOM:
        if timeout is None or memory_limit_mb is None:
            return _error("timeout and memory_limit_mb must be specified for custom execution mode")
        
        if not (MIN_TIMEOUT <= timeout <= MAX_TIMEOUT):
            return _error(f"timeout must be between {MIN_TIMEOUT} and {MAX_TIMEOUT} seconds")
        
        if not (1 <= memory_limit_mb <= 2048):
            return _error("memory_limit_mb must be between 1 and 2048 MB")
        
        actual_timeout = timeout
        # actual_memory_limit = memory_limit_mb  # Not used in current implementation
    else:
        limits = EXECUTION_CATEGORIES[execution_mode.value]
        actual_timeout = limits["timeout"]
        # actual_memory_limit = limits["memory_mb"]  # Not used in current implementation

    # Validate workspace access
    if not validate_path_in_workspace("."):
        return _error("Cannot access workspace directory")

    # ------------------------------------------------------------------
    # Path validation and security checks
    # ------------------------------------------------------------------

    # Validate script path
    abs_script_path = validate_path_in_workspace(path)
    if abs_script_path is None:
        return _error(f"Script path is outside workspace: {path}")

    try:
        script_path = Path(abs_script_path)
        
        # Check script existence and type
        if not script_path.exists():
            return _error(f"Script does not exist: {path}")
        
        if not script_path.is_file():
            return _error(f"Path is not a file: {path}")
        
        if not script_path.suffix.lower() in {'.py', '.pyw'}:
            return _error(f"File is not a Python script (.py/.pyw): {path}")
        
        # Security checks
        if script_path.is_symlink() and not is_safe_symlink(script_path):
            return _error("Cannot execute unsafe symlink pointing outside workspace")
        
        if not check_parent_symlinks(script_path):
            return _error("Cannot execute script with unsafe parent symlinks")

        # Validate working directory
        if working_directory:
            abs_workdir = validate_path_in_workspace(working_directory)
            if abs_workdir is None:
                return _error(f"Working directory is outside workspace: {working_directory}")
            
            work_dir = Path(abs_workdir)
            if not work_dir.exists():
                return _error(f"Working directory does not exist: {working_directory}")
            if not work_dir.is_dir():
                return _error(f"Working directory is not a directory: {working_directory}")
            
            # Security checks for working directory
            if work_dir.is_symlink() and not is_safe_symlink(work_dir):
                return _error("Cannot use unsafe working directory symlink")
            if not check_parent_symlinks(work_dir):
                return _error("Cannot use working directory with unsafe parent symlinks")
        else:
            work_dir = script_path.parent

        # ------------------------------------------------------------------
        # Script execution
        # ------------------------------------------------------------------

        # Prepare environment
        exec_environment = _prepare_environment(environment)
        
        # Execute script with monitoring
        result = _execute_script_safely(
            script_path=script_path,
            args=args,
            working_dir=work_dir,
            timeout=actual_timeout,
            environment=exec_environment,
            execution_mode=execution_mode,
        )

        # Build user-facing message
        if result.success:
            message = f"Success (exit code {result.exit_code}, {result.resource_usage.execution_time:.1f}s, {result.resource_usage.peak_memory_mb:.1f}MB peak memory, security score {result.security_analysis.security_score:.1f})"
        elif result.timeout_occurred:
            message = f"Timeout (killed after {actual_timeout}s, {result.resource_usage.peak_memory_mb:.1f}MB peak memory). Script was terminated"
        elif result.killed_by_signal:
            message = f"Killed (exit code {result.exit_code}, {result.resource_usage.execution_time:.1f}s, signal termination). Process was forcibly stopped"
        else:
            message = f"Failure (exit code {result.exit_code}, {result.resource_usage.execution_time:.1f}s). Stderr may have details"

        # Add warnings indicator if any security issues
        if result.security_analysis.warnings:
            message += f" - {len(result.security_analysis.warnings)} security warning(s)"
        
        # Add resource limit warnings
        if result.resource_usage.memory_exceeded or result.resource_usage.cpu_exceeded:
            warnings = []
            if result.resource_usage.memory_exceeded:
                warnings.append("memory limit exceeded")
            if result.resource_usage.cpu_exceeded:
                warnings.append("CPU limit exceeded")
            message += f" - {', '.join(warnings)}"

        # Build structured LLM content following unified standard
        rel_script_path = script_path.relative_to(WORKSPACE_ROOT) if str(script_path).startswith(str(WORKSPACE_ROOT)) else Path(path)
        rel_work_dir = work_dir.relative_to(WORKSPACE_ROOT) if str(work_dir).startswith(str(WORKSPACE_ROOT)) else work_dir
        
        llm_content = {
            "operation": {
                "type": "python_executor",
                "script_path": str(rel_script_path),
                "execution_mode": execution_mode.value,
                "args": args,
                "working_directory": str(rel_work_dir),
                "timeout_occurred": result.timeout_occurred,
                "killed_by_signal": result.killed_by_signal
            },
            "result": {
                "exit_code": result.exit_code,
                "stdout": result.output.stdout,
                "stderr": result.output.stderr,
                "success": result.success,
                "execution_time": result.resource_usage.execution_time,
                "peak_memory_mb": result.resource_usage.peak_memory_mb,
                "output_size": result.output.combined_size
            },
            "summary": {
                "operation_type": "python_executor",
                "success": result.success,
                "execution_category": result.execution_category,
                "security_score": result.security_analysis.security_score,
                "has_warnings": len(result.security_analysis.warnings) > 0
            }
        }
        
        # Add warnings only if they exist
        if result.security_analysis.warnings:
            llm_content["warnings"] = result.security_analysis.warnings[:3]  # Limit to first 3 warnings
        
        # Add resource limit warnings if exceeded
        if result.resource_usage.memory_exceeded or result.resource_usage.cpu_exceeded:
            resource_warnings = []
            if result.resource_usage.memory_exceeded:
                resource_warnings.append("memory limit exceeded")
            if result.resource_usage.cpu_exceeded:
                resource_warnings.append("CPU limit exceeded")
            llm_content["resource_limits"] = {
                "exceeded": True,
                "types": resource_warnings
            }

        return _success(
            message,
            llm_content,
            **result.to_dict(),
        )

    except Exception as exc:
        return _error(f"Unexpected error during script execution: {exc}")

# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_python_executor_tools(mcp: FastMCP):
    """Register the execute_python_script tool with proper tags synchronization."""
    common = dict(
        tags={"coding", "execution", "python", "script", "runtime", "monitoring", "security"}, 
        annotations={"category": "coding", "tags": ["coding", "execution", "python", "script", "runtime", "monitoring", "security"]}
    )
    mcp.tool(**common)(execute_python_script) 