from .run_pfc import register_run_pfc_tool

__all__ = [
    "register_pfc_tools",
]

def register_pfc_tools(mcp):
    """Aggregate registration of all Itasca PFC tools."""
    register_run_pfc_tool(mcp)
    print(f"[DEBUG] All PFC tools registered.")
