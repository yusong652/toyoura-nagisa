from pathlib import Path
import sys

# Use pathlib for clean path handling
_CURRENT_FILE = Path(__file__)
_NAGISA_MCP_DIR = _CURRENT_FILE.parent     # nagisa_mcp directory
_BACKEND_DIR = _NAGISA_MCP_DIR.parent      # backend directory
_PROJECT_ROOT = _BACKEND_DIR.parent        # project root directory

# Add necessary paths to sys.path
sys.path.insert(0, str(_PROJECT_ROOT))
from fastmcp import FastMCP

mcp = FastMCP(
    "Smart MCP Server for Nagisa",
    instructions="""
    This is a Smart MCP Server for Nagisa with comprehensive tool support.
    The server provides various tool categories for different tasks including coding,
    communication, information retrieval, media generation, and utilities.
    """
)

print(f"[DEBUG] Smart MCP Server initialized")


# NOTE: Internal tools are now registered via the in-process registry loader.
# This MCP server is reserved for future external tool exposure.

# Start the server
if __name__ == "__main__":
    print("Starting Smart MCP Server with dynamic tool selection...")
    mcp.run()
