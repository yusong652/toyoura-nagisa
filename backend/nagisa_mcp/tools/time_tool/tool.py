from fastmcp import FastMCP
from datetime import datetime


def register_time_tools(mcp: FastMCP):
    """Register time related utilities with proper tags synchronization."""

    @mcp.tool(
        tags={"time", "datetime", "utilities", "system", "clock"}, 
        annotations={"category": "utilities", "tags": ["time", "datetime", "utilities", "system", "clock"]}
    )
    def get_current_time() -> dict:
        """Return the current system time as a formatted string."""
        return {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")} 