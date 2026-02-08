"""Utilities for working with raw MCPClientManager results."""


def extract_mcp_text(result: dict) -> str:
    """Extract text from raw MCPClientManager.call_tool() result."""
    content = result.get("content", [])
    return "\n".join(p["text"] for p in content if p.get("type") == "text")
