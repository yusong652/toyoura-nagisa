import os
import sys
import io
from typing import Dict
from pydantic import Field
from .workspace import validate_path_in_workspace

def execute_python_script(
    path: str = Field(..., description="Path to the Python script to execute."),
    args: list = Field([], description="Command line arguments to pass to the script."),
    timeout: int = Field(30, description="Maximum execution time in seconds.")
) -> Dict[str, str]:
    """
    Execute a Python script in the workspace.
    This tool can be used for: running Python scripts, executing code, testing Python programs, etc.
    Example user queries: "run this script", "execute this Python file", "run my code".

    Args:
        path (str): Path to the Python script to execute.
        args (list): Command line arguments to pass to the script.
        timeout (int): Maximum execution time in seconds.

    Returns:
        Dict[str, str]: A dictionary containing:
            - status: 'success' or 'error'
            - output: Script's stdout output
            - error: Script's stderr output (if any)
            - exit_code: Script's exit code
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
    
    # Save original stdout and stderr
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    try:
        # Redirect stdout and stderr
        sys.stdout = stdout_capture
        sys.stderr = stderr_capture
        
        # Change to the script's directory
        script_dir = os.path.dirname(abs_path)
        original_cwd = os.getcwd()
        os.chdir(script_dir)
        
        # Execute the script
        sys.argv = [abs_path] + args
        with open(abs_path, 'r', encoding='utf-8') as f:
            script_content = f.read()
        
        # Execute the script in a new namespace
        script_globals = {
            '__name__': '__main__',
            '__file__': abs_path,
            '__builtins__': __builtins__,
        }
        exec(script_content, script_globals)
        
        # Restore original working directory
        os.chdir(original_cwd)
        
        return {
            "status": "success",
            "output": stdout_capture.getvalue(),
            "error": stderr_capture.getvalue(),
            "exit_code": 0
        }
        
    except Exception as e:
        return {
            "status": "error",
            "output": stdout_capture.getvalue(),
            "error": f"{stderr_capture.getvalue()}\nExecution error: {str(e)}",
            "exit_code": 1
        }
    finally:
        # Restore original stdout and stderr
        sys.stdout = original_stdout
        sys.stderr = original_stderr

def register_python_executor_tools(mcp):
    mcp.tool()(execute_python_script) 