from fastmcp import FastMCP, Tool, tool

@tool
def run_pfc_simulation(command: str) -> str:
    """
    Runs an Itasca PFC simulation.
    For the MCP, this is a placeholder and does not run a real simulation.

    :param command: The PFC command or file to execute.
    :return: A string indicating the simulation has started.
    """
    print(f"Received PFC command: {command}")
    return f"Itasca PFC simulation successfully started with command: '{command}'"

def register_run_pfc_tool(mcp: FastMCP):
    """Registers the PFC simulation tool."""
    mcp.register_tool(run_pfc_simulation)
    print(f"[DEBUG] Registered PFC tool: run_pfc_simulation")
