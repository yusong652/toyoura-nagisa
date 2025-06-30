import os
import sys
import io
from typing import Dict
from pydantic import Field

from .workspace import validate_path_in_workspace

# -----------------------------------------------------------------------------
# Python script execution tool
# -----------------------------------------------------------------------------

def execute_python_script(
    path: str = Field(..., description="Path to the Python script to execute."),
    args: list = Field([], description="Command line arguments to pass to the script."),
    timeout: int = Field(30, description="Maximum execution time in seconds."),
) -> Dict[str, str]:
    """Run a Python script located inside the coding workspace.

    This tool can be used for running scripts, testing code, etc.
    """
    abs_path = validate_path_in_workspace(path)
    if abs_path is None:
        return {"error": f"Path is outside of workspace: {path}"}
    if not os.path.exists(abs_path):
        return {"error": f"Script does not exist: {path}"}
    if not os.path.isfile(abs_path):
        return {"error": f"Path is not a file: {path}"}

    # Capture stdout and stderr
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    # Preserve originals
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    try:
        sys.stdout = stdout_capture
        sys.stderr = stderr_capture

        # Change working directory to script dir
        original_cwd = os.getcwd()
        script_dir = os.path.dirname(abs_path)
        os.chdir(script_dir)

        # Prepare argv
        sys.argv = [abs_path] + args

        # Execute script in isolated globals
        with open(abs_path, "r", encoding="utf-8") as fh:
            script_code = fh.read()
        exec(
            script_code,
            {
                "__name__": "__main__",
                "__file__": abs_path,
                "__builtins__": __builtins__,
            },
        )

        os.chdir(original_cwd)
        return {
            "status": "success",
            "output": stdout_capture.getvalue(),
            "error": stderr_capture.getvalue(),
            "exit_code": 0,
        }
    except Exception as exc:  # pylint: disable=broad-except
        return {
            "status": "error",
            "output": stdout_capture.getvalue(),
            "error": f"{stderr_capture.getvalue()}\nExecution error: {exc}",
            "exit_code": 1,
        }
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr


# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_python_executor_tools(mcp):
    mcp.tool(tags={"coding"}, annotations={"category": "coding"})(execute_python_script) 