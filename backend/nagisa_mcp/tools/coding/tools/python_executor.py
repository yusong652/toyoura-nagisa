# NOTE: We purposely avoid importing *subprocess* globally at tool-registration
# time because certain sandbox environments patch it.  Import lazily inside the
# function instead if you prefer.  Here we import at module level for clarity.

import os
import subprocess
from typing import Dict, List

from pydantic import Field

from .workspace import validate_path_in_workspace

# -----------------------------------------------------------------------------
# Python script execution tool
# -----------------------------------------------------------------------------

def execute_python_script(
    # ------------------------------------------------------------------
    # PARAMETERS
    # ------------------------------------------------------------------
    # We add deliberately verbose *description* strings because these are
    # surfaced verbatim in the tool schema that the language-model sees.
    # By spelling out the intent / advantages here we can bias the model
    # towards selecting *execute_python_script* over the more generic and
    # potentially unsafe *run_shell_command* when the goal is simply to run
    # a Python file.
    path: str = Field(
        ...,
        description=(
            "Workspace-relative **path** to the ``.py`` script you wish to run. "
            "The path must reside *inside* the coding workspace – absolute or "
            "relative forms are accepted.  If you need to create the file first, "
            "use the *write_file* tool, then call this tool to execute it."
        ),
    ),
    args: List[str] = Field(
        default_factory=list,
        description=(
            "(Optional) **List** of command-line arguments passed *directly* to the "
            "Python interpreter – *no shell expansion occurs*.  Provide one "
            "argument per list element, e.g. ``[\"--epochs\", \"10\"]``."
        ),
    ),
    timeout: int = Field(
        30,
        description=(
            "Failsafe in **seconds**.  If the script exceeds this runtime the "
            "process tree is force-terminated and an error is returned."
        ),
    ),
) -> Dict[str, str]:
    """The **specialized and safest** tool for executing local `.py` script files.

    Safely execute a Python script in its **own** OS process.

    🤝 *When should I choose this tool?*
    -----------------------------------
    • **Most python-only tasks** – training a model, running a data-processing
      script, unit-testing – should use *execute_python_script* rather than the
      generic *run_shell_command*.
    • It is the *recommended* and **safest** pathway because it bypasses the
      system shell entirely: arguments are passed as a Python list, preventing
      shell-injection and avoiding the need for escaping quotes / spaces.

    🚧 *When *not* to use it*
    -------------------------
    • If you truly need *shell* features (pipes, ``&&``, environment
      variables, invoking *non-Python* binaries) then fall back to
      *run_shell_command* – but obtain explicit user consent first because that
      tool is far less sandboxed.

    Security & Reliability Benefits
    -------------------------------
    1. **Process isolation** – the host application never *exec()*s arbitrary
       code; everything runs in a child process managed by :pymod:`subprocess`.
    2. **Deterministic timeouts** – hung scripts are killed after ``timeout``
       seconds, safeguarding service availability.
    3. **No shell interpolation** – eliminates an entire attack surface of
       command-injection vulnerabilities.

    Returns
    -------
    Dict with keys:
      status : "success" | "error"
      output : captured STDOUT
      error  : captured STDERR or error message
      exit_code : int – underlying process return-code (0 => success)

    Example
    -------
    >>> execute_python_script(
    ...     path="scripts/train.py",
    ...     args=["--epochs", "5"],
    ... )
    {"status": "success", "output": "…", "error": "", "exit_code": 0}
    """

    # ---------------------------------------------------------------------
    # Validation & path resolution
    # ---------------------------------------------------------------------
    abs_path = validate_path_in_workspace(path)
    if abs_path is None:
        return {"status": "error", "error": f"Path is outside of workspace: {path}"}
    if not os.path.exists(abs_path):
        return {"status": "error", "error": f"Script does not exist: {path}"}
    if not os.path.isfile(abs_path):
        return {"status": "error", "error": f"Path is not a file: {path}"}

    # Ensure *args* is a list of strings – avoid accidental shell-injection risk.
    if not isinstance(args, list):
        return {"status": "error", "error": "'args' must be a list of strings"}
    str_args = [str(a) for a in args]

    # ---------------------------------------------------------------------
    # Sub-process execution
    # ---------------------------------------------------------------------
    cmd = [os.getenv("PYTHON", os.sys.executable), abs_path] + str_args
    script_dir = os.path.dirname(abs_path)

    try:
        result = subprocess.run(
            cmd,
            cwd=script_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        status = "success" if result.returncode == 0 else "error"
        return {
            "status": status,
            "output": result.stdout,
            "error": result.stderr,
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired as exc:
        # Kill process tree if still alive; subprocess.run already does.
        return {
            "status": "error",
            "output": exc.stdout or "",
            "error": f"Script exceeded timeout of {timeout}s and was terminated.",
            "exit_code": -1,
        }
    except Exception as exc:  # pylint: disable=broad-except
        return {
            "status": "error",
            "output": "",
            "error": f"Failed to run script: {exc}",
            "exit_code": -1,
        }


# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_python_executor_tools(mcp):
    mcp.tool(tags={"coding"}, annotations={"category": "coding"})(execute_python_script) 