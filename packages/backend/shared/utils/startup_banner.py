"""
Startup banner and logging utilities for toyoura-nagisa
FastMCP-inspired beautiful terminal interface using Rich
"""

import os
from typing import Optional, List
from datetime import datetime

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align


# Nagisa ASCII art with gradient (matching CLI style)
# Particle cluster ears + cute expression
NAGISA_ASCII = (
    "\x1b[38;2;255;105;180m█\x1b[38;2;255;110;185m█\x1b[38;2;255;115;190m█\x1b[38;2;255;120;195m█\x1b[38;2;255;125;200m█\x1b[0m"
    "       "
    "\x1b[38;2;255;105;180m█\x1b[38;2;255;110;185m█\x1b[38;2;255;115;190m█\x1b[38;2;255;120;195m█\x1b[38;2;255;125;200m█\x1b[0m\n"
    "\x1b[38;2;255;105;180m█\x1b[38;2;255;110;185m█\x1b[38;2;255;115;190m█\x1b[38;2;255;120;195m█\x1b[38;2;255;125;200m█\x1b[0m"
    "       "
    "\x1b[38;2;255;105;180m█\x1b[38;2;255;110;185m█\x1b[38;2;255;115;190m█\x1b[38;2;255;120;195m█\x1b[38;2;255;125;200m█\x1b[0m\n"
    "\x1b[38;2;255;105;180m█\x1b[38;2;255;110;185m█\x1b[38;2;255;115;190m█\x1b[38;2;255;120;195m█\x1b[38;2;255;125;200m█\x1b[38;2;255;130;205m█\x1b[38;2;255;135;210m█\x1b[38;2;255;140;215m█\x1b[38;2;255;145;220m█\x1b[38;2;255;150;225m█\x1b[38;2;255;155;230m█\x1b[38;2;255;160;235m█\x1b[38;2;255;165;240m█\x1b[38;2;255;170;245m█\x1b[38;2;255;175;250m█\x1b[38;2;255;180;255m█\x1b[38;2;255;185;255m█\x1b[0m\n"
    " \x1b[38;2;255;120;195m█\x1b[38;2;255;125;200m█\x1b[38;2;255;130;205m█\x1b[38;2;255;135;210m█\x1b[38;2;255;140;215m█\x1b[38;2;255;145;220m█\x1b[38;2;255;150;225m█\x1b[38;2;255;155;230m█\x1b[38;2;255;160;235m█\x1b[38;2;255;165;240m█\x1b[38;2;255;170;245m█\x1b[38;2;255;175;250m█\x1b[38;2;255;180;255m█\x1b[38;2;255;185;255m█\x1b[38;2;255;190;255m█\x1b[0m\n"
    "\x1b[38;2;255;125;200m█\x1b[38;2;255;130;205m█\x1b[38;2;255;135;210m█\x1b[38;2;255;140;215m█\x1b[38;2;255;145;220m█\x1b[0m "
    "\x1b[38;2;255;150;225m█\x1b[38;2;255;155;230m█\x1b[38;2;255;160;235m█\x1b[38;2;255;165;240m█\x1b[38;2;255;170;245m█\x1b[0m "
    "\x1b[38;2;255;175;250m█\x1b[38;2;255;180;255m█\x1b[38;2;255;185;255m█\x1b[38;2;255;190;255m█\x1b[38;2;255;195;255m█\x1b[0m\n"
    "\x1b[38;2;255;130;205m█\x1b[38;2;255;135;210m█\x1b[38;2;255;140;215m█\x1b[38;2;255;145;220m█\x1b[38;2;255;150;225m█\x1b[38;2;255;155;230m█\x1b[38;2;255;160;235m█\x1b[38;2;255;165;240m█\x1b[38;2;255;170;245m█\x1b[38;2;255;175;250m█\x1b[38;2;255;180;255m█\x1b[38;2;255;185;255m█\x1b[38;2;255;190;255m█\x1b[38;2;255;195;255m█\x1b[38;2;255;200;255m█\x1b[38;2;255;205;255m█\x1b[38;2;255;210;255m█\x1b[0m\n"
    "\x1b[38;2;255;135;210m█\x1b[0m "
    "\x1b[38;2;255;140;215m█\x1b[38;2;255;145;220m█\x1b[38;2;255;150;225m█\x1b[38;2;255;155;230m█\x1b[38;2;255;160;235m█\x1b[38;2;255;165;240m█\x1b[38;2;255;170;245m█\x1b[38;2;255;175;250m█\x1b[38;2;255;180;255m█\x1b[38;2;255;185;255m█\x1b[38;2;255;190;255m█\x1b[38;2;255;195;255m█\x1b[38;2;255;200;255m█\x1b[0m "
    "\x1b[38;2;255;205;255m█\x1b[0m\n"
    "\x1b[38;2;255;145;220m█\x1b[38;2;255;150;225m█\x1b[38;2;255;155;230m█\x1b[38;2;255;160;235m█\x1b[38;2;255;165;240m█\x1b[38;2;255;170;245m█\x1b[38;2;255;175;250m█\x1b[38;2;255;180;255m█\x1b[38;2;255;185;255m█\x1b[38;2;255;190;255m█\x1b[38;2;255;195;255m█\x1b[38;2;255;200;255m█\x1b[38;2;255;205;255m█\x1b[38;2;255;210;255m█\x1b[38;2;255;215;255m█\x1b[38;2;255;220;255m█\x1b[38;2;255;225;255m█\x1b[0m\n"
    " \x1b[38;2;255;160;235m█\x1b[38;2;255;165;240m█\x1b[38;2;255;170;245m█\x1b[38;2;255;175;250m█\x1b[38;2;255;180;255m█\x1b[38;2;255;185;255m█\x1b[38;2;255;190;255m█\x1b[38;2;255;195;255m█\x1b[38;2;255;200;255m█\x1b[38;2;255;205;255m█\x1b[38;2;255;210;255m█\x1b[38;2;255;215;255m█\x1b[38;2;255;220;255m█\x1b[38;2;255;225;255m█\x1b[38;2;255;230;255m█\x1b[0m\n"
    "   \x1b[38;2;255;175;250m█\x1b[38;2;255;180;255m█\x1b[38;2;255;185;255m█\x1b[38;2;255;190;255m█\x1b[38;2;255;195;255m█\x1b[38;2;255;200;255m█\x1b[38;2;255;205;255m█\x1b[38;2;255;210;255m█\x1b[38;2;255;215;255m█\x1b[38;2;255;220;255m█\x1b[38;2;255;225;255m█\x1b[0m"
)


def print_banner(
    environment: str,
    host: str,
    port: int,
    llm_client: str,
    secondary_llm_client: Optional[str] = None,
    cors_origins: Optional[List[str]] = None,
    mcp_port: int = 9000,
    version: str = "0.1.0"
):
    """
    Print FastMCP-inspired startup banner using Rich.

    Args:
        environment: Environment name (development/staging/production)
        host: Server host
        port: Server port
        llm_client: Primary LLM client name
        secondary_llm_client: Secondary LLM client name (optional)
        cors_origins: List of allowed CORS origins (optional)
        mcp_port: MCP server port
        version: Application version
    """
    console = Console(stderr=True)

    # Create Nagisa logo with ANSI colors
    logo_text = Text.from_ansi(NAGISA_ASCII, no_wrap=True)

    # Main title
    title_text = Text(f"toyoura-nagisa {version}", style="bold magenta")

    # Tagline
    tagline_text = Text("AI Agent Platform for PFC Scientific Computing", style="dim cyan")

    # Server URL
    protocol = "http"
    server_url = f"{protocol}://{host}:{port}"
    mcp_url = f"{protocol}://{host}:{mcp_port}/sse"

    # Extract provider name from LLM client (e.g., "GoogleLLMClient" -> "Google Gemini")
    provider_name = llm_client.replace("LLMClient", "").replace("Google", "Google Gemini")

    # Create information table (minimal, essential info only)
    info_table = Table.grid(padding=(0, 1))
    info_table.add_column(style="bold", justify="center")  # Emoji column
    info_table.add_column(style="white", justify="left")  # Value column

    info_table.add_row("🔗", Text(server_url, style="white"))
    info_table.add_row("🤖", Text(provider_name, style="white"))
    info_table.add_row("📚", Text("github.com/yusong652/toyoura-nagisa", style="dim cyan"))

    # Create panel content with Group
    panel_content = Group(
        "",
        Align.center(logo_text),
        "",
        "",
        Align.center(title_text),
        Align.center(tagline_text),
        "",
        Align.center(info_table),
    )

    # Create the main panel
    panel = Panel(
        panel_content,
        border_style="dim",
        padding=(1, 4),
        width=80,
    )

    # Build output
    output_elements = ["\n", Align.center(panel), "\n"]

    console.print(Group(*output_elements))


def print_shutdown_message():
    """Print shutdown message (Rich style)."""
    console = Console(stderr=True)
    shutdown_text = Text("⚡ Shutting down gracefully...", style="bold yellow")
    console.print(f"\n  {shutdown_text}")


def print_shutdown_complete():
    """Print shutdown complete message."""
    console = Console(stderr=True)
    complete_text = Text("✓ Shutdown complete", style="bold green")
    goodbye_text = Text("(◕ω◕) See you next time~", style="dim")
    console.print(f"  {complete_text}")
    console.print(f"  {goodbye_text}\n")


# Minimal logging functions for progress messages
def log_init(message: str):
    """Log initialization step (minimal, for loading sequence)."""
    console = Console(stderr=True)
    console.print(f"[dim]  ⋯ {message}[/dim]", end="\r")


def log_success(message: str):
    """Log success step."""
    console = Console(stderr=True)
    console.print(f"[green]  ✓ {message}[/green]")


def log_error(message: str):
    """Log error message."""
    console = Console(stderr=True)
    console.print(f"[bold red]  ✗ {message}[/bold red]")


def log_warning(message: str):
    """Log warning message."""
    console = Console(stderr=True)
    console.print(f"[bold yellow]  ⚠ {message}[/bold yellow]")
