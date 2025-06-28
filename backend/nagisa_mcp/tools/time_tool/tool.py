from fastmcp import FastMCP
from datetime import datetime


def register_time_tools(mcp: FastMCP):
    """Register time related utilities."""

    @mcp.tool(tags={"time"}, annotations={"category": "utilities"})
    def get_current_time() -> dict:
        """Return the current system time as a formatted string."""
        return {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")} 