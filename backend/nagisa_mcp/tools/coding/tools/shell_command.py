"""run_shell_command tool – execute a shell command inside the coding workspace.

Features & **Security Considerations**
-------------------------------------
* Mirrors gemini-cli's ``ShellTool`` design, implemented in Python for FastMCP.
* Executes the *exact* **command string** via:

  • ``bash -c <command>`` on POSIX platforms (falls back to ``sh -c`` if
    *bash* is not available).
  • ``cmd.exe /c <command>`` on Windows.

* The command runs in its own subprocess and can therefore read / modify files
  inside the **coding workspace** and spawn further processes.  **It does not
  run in a sandbox.**  Malicious commands (e.g. ``rm -rf``, ``curl | sh``)
  will execute with the same privileges as the hosting process.

* The tool performs minimal validation (rejects empty commands, ensures target
  directory is inside the workspace) but **does not** escape or sanitise shell
  metacharacters such as ``|``, ``&&``.  *Callers MUST obtain explicit user
  confirmation* before executing any untrusted command.

Use responsibly.  If you need stronger isolation consider disabling this tool
or executing commands inside a container / VM.
"""

import os
import subprocess
import shutil
from typing import Dict, Any, List, Optional

from pydantic import Field
from fastmcp import FastMCP  # type: ignore

from pathlib import Path

from .config import get_tools_config, ToolsConfig

__all__ = ["run_shell_command", "register_shell_command_tool"]


# ---------------------------------------------------------------------------
# Tool implementation
# ---------------------------------------------------------------------------


def run_shell_command(
    # ------------------------------------------------------------------
    # PARAMETERS
    # ------------------------------------------------------------------
    command: str = Field(
        ...,
        description=(
            "The **complete** shell command string (bash syntax by default) to "
            "execute – include any pipes `|`, redirects `>`, logical operators "
            "(`&&`, `||`), subshells, etc.  Example: ``ls -l | grep .py > out.txt``."
        ),
    ),
    directory: Optional[str] = Field(
        None,
        description="Optional relative directory (under workspace root) where the command is executed",
    ),
    timeout: int = Field(60, gt=0, description="Maximum run time in seconds before termination"),
) -> Dict[str, Any]:
    """The **general-purpose and powerful** tool for executing any shell command, especially those with pipes or redirects.

    Run an **arbitrary** shell command inside the coding workspace.

    🛠️ *When to use this tool*
    --------------------------
    • Executing **complex shell constructs** such as pipes, redirects, command
      chaining, environment variable expansion, or invoking multiple programs
      in one line – e.g. ``ls -l | grep .py``, ``cat file.txt | wc -l``.
    • Installing packages or other system-level tasks that inherently rely on
      shell semantics – e.g. ``pip install -r requirements.txt``.
    • Creating or manipulating files via shell utilities – e.g. ``echo 'hi' > a.txt``.

    ⚠️ *When NOT to use it*
    -----------------------
    • If the goal is simply to **run a Python script**, prefer the dedicated
      and safer :pyfunc:`execute_python_script` tool which bypasses the shell
      and offers tighter isolation.
    • Avoid for single binary invocations where a more specific tool exists –
      always choose the *least-privileged* option available.

    🔐 Security Warning
    ------------------
    This tool launches the given string through ``bash -c`` (or ``cmd.exe /c``
    on Windows).  The shell will interpret all metacharacters – a malicious
    command like ``rm -rf /`` will run with the same privileges as the host
    process.  **Obtain explicit user confirmation** before executing commands
    sourced from untrusted input.

    Returns
    -------
    Dict with keys:
      status     : "success" | "error"
      output     : captured STDOUT
      error      : captured STDERR or error message
      exit_code  : int | None (``None`` if killed by signal)
      signal     : int | None – POSIX signal number that terminated the process

    Example
    -------
    >>> run_shell_command(command="echo 'Hello, World!'")
    {"status": "success", "output": "Hello, World!\n", "error": "", "exit_code": 0}
    """

    # ----------------------------
    # Parameter validation
    # ----------------------------
    if not command.strip():
        return {"status": "error", "error": "command cannot be empty"}

    # Resolve execution directory
    root_dir = get_tools_config().root_dir
    exec_dir_path = root_dir
    if directory:
        candidate = (root_dir / directory).resolve()
        try:
            candidate.relative_to(root_dir)
        except ValueError:
            return {"status": "error", "error": "directory must be inside workspace"}
        exec_dir_path = candidate

    exec_dir = str(exec_dir_path)

    # ----------------------------
    # Spawn subprocess
    # ----------------------------
    shell_exe: List[str]
    if os.name == "nt":
        shell_exe = ["cmd.exe", "/c", command]
    else:
        # Prefer bash if available else fallback to sh
        bash_path = shutil.which("bash")  # type: ignore[name-defined]
        if bash_path:
            shell_exe = [bash_path, "-c", command]
        else:
            shell_exe = ["sh", "-c", command]

    try:
        proc = subprocess.run(
            shell_exe,
            cwd=exec_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        base = {
            "status": "success" if proc.returncode == 0 else "error",
            "output": proc.stdout,
            "error": proc.stderr,
            "exit_code": proc.returncode,
            "signal": None,
        }
        # Compose llm_content / return_display à la gemini-cli
        llm_content = (
            f"Command: {command}\nDirectory: {directory or '(root)'}\n"
            f"Stdout: {proc.stdout or '(empty)'}\nStderr: {proc.stderr or '(empty)'}\n"
            f"Exit Code: {proc.returncode}"
        )
        return_display = llm_content if get_tools_config().debug_mode else (proc.stdout or proc.stderr)
        base.update({"llm_content": llm_content, "return_display": return_display})
        return base
    except subprocess.TimeoutExpired as exc:
        llm_content = f"Command timed out after {timeout}s"
        return {
            "status": "error",
            "output": exc.stdout or "",
            "error": f"command timed out after {timeout}s",
            "exit_code": None,
            "signal": None,
            "llm_content": llm_content,
            "return_display": llm_content,
        }
    except Exception as exc:  # pylint: disable=broad-except
        llm_content = str(exc)
        return {
            "status": "error",
            "output": "",
            "error": str(exc),
            "exit_code": None,
            "signal": None,
            "llm_content": llm_content,
            "return_display": llm_content,
        }


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------

def register_shell_command_tool(mcp: FastMCP):
    common = dict(tags={"shell", "coding"}, annotations={"category": "coding"})
    mcp.tool(**common)(run_shell_command) 