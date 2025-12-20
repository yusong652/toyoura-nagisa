"""
PFC Plot Capture Tool - MCP tool for capturing PFC plot screenshots.

Provides multimodal diagnostic capability by capturing PFC GUI plot windows
for visual analysis. Engineers can visually diagnose simulation state
(particle distribution, stress patterns, boundary conditions) through
captured images.

Philosophy: "Qualitative is radar, quantitative is microscope"
- Visual scan (qualitative) → Trigger targeted queries (quantitative)
"""

import os
import tempfile
from fastmcp import FastMCP
from fastmcp.server.context import Context
from typing import Dict, Any, Optional, Tuple, List
from pydantic import Field
from backend.infrastructure.pfc import get_client
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.mcp.utils.path_normalization import normalize_path_separators


def register_pfc_capture_plot_tool(mcp: FastMCP):
    """
    Register PFC plot capture tool with the MCP server.

    Args:
        mcp: FastMCP server instance
    """

    @mcp.tool(
        tags={"pfc", "visualization", "multimodal", "diagnostic"},
        annotations={"category": "pfc", "tags": ["pfc", "visualization", "diagnostic"]}
    )
    async def pfc_capture_plot(
        context: Context,
        output_path: str = Field(
            ...,
            description=(
                "Absolute path for output image file (must end with .png). "
                "Parent directory will be created if not exists. "
                "Example: '/path/to/workspace/results/plots/stress_check.png'"
            )
        ),
        plot_name: str = Field(
            default="Plot01",
            description="Name of the plot window in PFC GUI (default: 'Plot01')"
        ),
        size: Optional[Tuple[int, int]] = Field(
            default=None,
            description="Image dimensions in pixels (width, height). Default: (1920, 1080)"
        ),
        center: Optional[Tuple[float, float, float]] = Field(
            default=None,
            description="Camera look-at point (x, y, z). If not specified, uses current view."
        ),
        eye: Optional[Tuple[float, float, float]] = Field(
            default=None,
            description="Camera position (x, y, z). If not specified, uses current view."
        ),
        distance: Optional[float] = Field(
            default=None,
            description="Distance from camera to center point."
        ),
        dip: Optional[float] = Field(
            default=None,
            description="View plane dip angle in degrees."
        ),
        dip_direction: Optional[float] = Field(
            default=None,
            description="View plane dip direction in degrees."
        ),
        roll: Optional[float] = Field(
            default=None,
            description="Camera roll angle in degrees."
        ),
        magnification: Optional[float] = Field(
            default=None,
            description="Zoom level (1.0 = normal)."
        ),
        projection: Optional[str] = Field(
            default=None,
            description="Projection mode: 'perspective' or 'parallel'."
        ),
    ) -> Dict[str, Any]:
        """
        Capture a screenshot of PFC plot window for visual diagnosis.

        Use this tool to visually inspect simulation state. The captured image
        can be read with the 'read' tool for multimodal analysis to identify:
        - Particle clustering or irregular distributions
        - Boundary penetration issues
        - Stress concentration patterns
        - Model geometry problems

        Workflow:
            1. Capture plot: result = pfc_capture_plot(output_path="...")
            2. Analyze image: read(result["data"]["output_path"])
            3. Take action based on visual findings

        Note: This tool generates a Python script and executes it synchronously.
        The script sets view parameters and exports the plot as PNG.
        """
        try:
            # Get session ID from MCP context
            session_id = getattr(context, 'client_id', None) if context else None
            if not session_id:
                return error_response("Session ID not available")

            # Validate output path
            if not output_path or not output_path.strip():
                return error_response(
                    "output_path is required. Provide absolute path ending with .png"
                )

            output_path = output_path.strip()

            # Check for .png extension
            if not output_path.lower().endswith('.png'):
                return error_response(
                    f"output_path must end with .png, got: {output_path}"
                )

            # Validate projection value
            if projection is not None and projection not in ('perspective', 'parallel'):
                return error_response(
                    f"projection must be 'perspective' or 'parallel', got: '{projection}'"
                )

            # Default size
            if size is None:
                size = (1920, 1080)

            # Normalize output path for cross-platform (Linux format for PFC server)
            normalized_output_path = normalize_path_separators(output_path, target_platform='linux')

            # Build view settings dict (only non-None values)
            view_settings: Dict[str, Any] = {}
            if center is not None:
                view_settings["center"] = list(center)
            if eye is not None:
                view_settings["eye"] = list(eye)
            if distance is not None:
                view_settings["distance"] = distance
            if dip is not None:
                view_settings["dip"] = dip
            if dip_direction is not None:
                view_settings["dip_direction"] = dip_direction
            if roll is not None:
                view_settings["roll"] = roll
            if magnification is not None:
                view_settings["magnification"] = magnification
            if projection is not None:
                view_settings["projection"] = projection

            # Generate Python script for plot capture
            script_content = _generate_plot_script(
                plot_name=plot_name,
                output_path=normalized_output_path,
                size=size,
                view_settings=view_settings
            )

            # Get PFC working directory for script storage
            client = await get_client()
            working_dir = await client.get_working_directory()

            if not working_dir:
                return error_response(
                    "Cannot determine PFC working directory. "
                    "Ensure PFC server is running with a project open."
                )

            # Create script file in PFC workspace
            script_dir = os.path.join(working_dir, ".nagisa", "plot_scripts")
            os.makedirs(script_dir, exist_ok=True)

            # Generate unique script filename
            import time
            script_filename = f"capture_plot_{int(time.time() * 1000)}.py"
            script_path = os.path.join(script_dir, script_filename)

            # Write script (use Linux path for cross-platform)
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(script_content)

            # Normalize script path for PFC server
            normalized_script_path = normalize_path_separators(script_path, target_platform='linux')

            # Execute script synchronously (blocking)
            # Use source="diagnostic" to mark as diagnostic operation
            # (filterable in pfc_list_tasks, no git snapshot)
            try:
                result = await client.execute_task(
                    script_path=normalized_script_path,
                    description=f"Capture plot: {plot_name}",
                    timeout_ms=30000,  # 30 second timeout
                    run_in_background=False,  # Synchronous execution
                    session_id=session_id,
                    source="diagnostic"
                )
            finally:
                # Always cleanup script file (success or failure)
                try:
                    os.remove(script_path)
                except OSError:
                    pass  # Ignore cleanup errors

            # Handle execution result
            status = result.get("status")
            data = result.get("data", {})

            if status == "error":
                error_msg = result.get("message", "Plot capture failed")
                return error_response(f"Plot capture failed: {error_msg}")

            # Build success response
            filename = os.path.basename(output_path)
            return success_response(
                message=f"Plot captured: {filename}",
                llm_content={
                    "parts": [{
                        "type": "text",
                        "text": (
                            f"Plot screenshot saved to: {output_path}\n\n"
                            f"To analyze the image, use the read tool:\n"
                            f"  read(\"{output_path}\")\n\n"
                            f"The image shows the current state of plot '{plot_name}' "
                            f"with the specified view settings."
                        )
                    }]
                },
                output_path=output_path,
                plot_name=plot_name,
                size=list(size),
                view_settings=view_settings if view_settings else None
            )

        except ConnectionError as e:
            return error_response(f"Cannot connect to PFC server: {str(e)}")

        except Exception as e:
            return error_response(f"Plot capture error: {str(e)}")

    print(f"[DEBUG] Registered PFC plot capture tool: pfc_capture_plot")


def _generate_plot_script(
    plot_name: str,
    output_path: str,
    size: Tuple[int, int],
    view_settings: Dict[str, Any]
) -> str:
    """
    Generate Python script for PFC plot capture.

    The script uses itasca.command() to execute PFC plot commands:
    1. Set view parameters (if specified)
    2. Export plot as PNG

    Args:
        plot_name: Name of the plot window (e.g., "Plot01")
        output_path: Absolute path for output PNG file
        size: Image dimensions (width, height)
        view_settings: View parameters (center, eye, distance, dip, etc.)

    Returns:
        Python script content as string
    """
    lines: List[str] = [
        '"""',
        'PFC Plot Capture Script',
        'Generated by pfc_capture_plot tool',
        '"""',
        '',
        'import itasca',
        'import os',
        '',
        '# Ensure output directory exists',
        f'output_path = r"{output_path}"',
        'os.makedirs(os.path.dirname(output_path), exist_ok=True)',
        '',
        f'plot_name = "{plot_name}"',
        '',
    ]

    # Add view setting commands if any specified
    if view_settings:
        lines.append('# Set view parameters')

        # Build view command parts
        view_parts: List[str] = []

        if "center" in view_settings:
            c = view_settings["center"]
            view_parts.append(f"center ({c[0]},{c[1]},{c[2]})")

        if "eye" in view_settings:
            e = view_settings["eye"]
            view_parts.append(f"eye ({e[0]},{e[1]},{e[2]})")

        if "distance" in view_settings:
            view_parts.append(f"distance {view_settings['distance']}")

        if "dip" in view_settings:
            view_parts.append(f"dip {view_settings['dip']}")

        if "dip_direction" in view_settings:
            view_parts.append(f"dip-direction {view_settings['dip_direction']}")

        if "roll" in view_settings:
            view_parts.append(f"roll {view_settings['roll']}")

        if "magnification" in view_settings:
            view_parts.append(f"magnification {view_settings['magnification']}")

        if "projection" in view_settings:
            view_parts.append(f"projection {view_settings['projection']}")

        # Generate view command
        if view_parts:
            view_params = " ".join(view_parts)
            lines.append(f'itasca.command(\'plot "{plot_name}" view {view_params}\')')
            lines.append('')

    # Add export command
    # Use f-string in generated script to insert output_path variable
    lines.extend([
        '# Export plot as PNG',
        f'itasca.command(f\'plot "{plot_name}" export bitmap filename "{{output_path}}" size {size[0]} {size[1]}\')',
        '',
        'print(f"Plot captured successfully: {output_path}")',
    ])

    return '\n'.join(lines)
