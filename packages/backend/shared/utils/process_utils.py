"""Process management utilities for system-level operations."""

import sys
import subprocess


def kill_process_on_port(port: int) -> bool:
    """Kill any process occupying the specified port (Windows only).

    Args:
        port: The port number to check and clear.

    Returns:
        True if a process was killed, False otherwise.
    """
    if sys.platform != "win32":
        return False

    try:
        # Find PID using netstat
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            timeout=5
        )

        for line in result.stdout.split("\n"):
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                if parts:
                    pid = parts[-1]
                    try:
                        subprocess.run(
                            ["taskkill", "/F", "/PID", pid],
                            capture_output=True,
                            timeout=5
                        )
                        print(f"[INIT] Killed stale process {pid} on port {port}")
                        return True
                    except Exception:
                        pass
    except Exception as e:
        print(f"[INIT] Port cleanup check failed: {e}")

    return False
