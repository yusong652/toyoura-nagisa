"""
PFC Plot Capture Tool - MCP tool for capturing PFC plot screenshots.

Provides multimodal diagnostic capability by capturing PFC GUI plot windows
for visual analysis. Engineers can visually diagnose simulation state
(particle distribution, stress patterns, boundary conditions) through
captured images.

Philosophy: "Qualitative is radar, quantitative is microscope"
- Visual scan (qualitative) → Trigger targeted queries (quantitative)

Design:
- Creates temporary diagnostic plot to avoid interfering with user's plots
- Includes sensible defaults (ball, wall with transparency, axes)
- Auto-cleanup: deletes temporary plot after export
"""

import os
from fastmcp import FastMCP
from fastmcp.server.context import Context
from typing import Dict, Any, Optional, Tuple
from pydantic import Field
from backend.infrastructure.pfc import get_client
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.mcp.utils.path_normalization import normalize_path_separators
from .scripts import generate_plot_capture_script, DEFAULT_PLOT_NAME, DEFAULT_WALL_TRANSPARENCY


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
        size: Optional[Tuple[int, int]] = Field(
            default=None,
            description="Image dimensions in pixels (width, height). Default: (1920, 1080)"
        ),
        include_ball: bool = Field(
            default=True,
            description="Include ball visualization item"
        ),
        include_wall: bool = Field(
            default=True,
            description="Include wall visualization item (with transparency)"
        ),
        include_axes: bool = Field(
            default=True,
            description="Include coordinate axes for reference"
        ),
        wall_transparency: int = Field(
            default=DEFAULT_WALL_TRANSPARENCY,
            ge=0,
            le=100,
            description="Wall transparency 0-100 (0=opaque, 100=invisible). Default: 70"
        ),
        center: Optional[Tuple[float, float, float]] = Field(
            default=None,
            description="Camera look-at point (x, y, z). If not specified, auto-fit."
        ),
        eye: Optional[Tuple[float, float, float]] = Field(
            default=None,
            description="Camera position (x, y, z). If not specified, uses default isometric view."
        ),
        magnification: Optional[float] = Field(
            default=None,
            description="Zoom level (1.0 = normal)."
        ),
        projection: Optional[str] = Field(
            default=None,
            description="Projection mode: 'perspective' or 'parallel'. Default: 'perspective'"
        ),
    ) -> Dict[str, Any]:
        """
        Capture a diagnostic screenshot of PFC model state.

        Creates a temporary plot with ball/wall/axes visualization, exports it
        as PNG, then deletes the temporary plot. This avoids interfering with
        any plots the user may have open.

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

        Note: This creates a temporary diagnostic plot named "NagisaDiagnostic"
        which is automatically deleted after the screenshot is captured.
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
            if magnification is not None:
                view_settings["magnification"] = magnification
            if projection is not None:
                view_settings["projection"] = projection

            # Generate Python script for plot capture
            script_content = generate_plot_capture_script(
                output_path=normalized_output_path,
                plot_name=DEFAULT_PLOT_NAME,
                size=size,
                view_settings=view_settings if view_settings else None,
                include_ball=include_ball,
                include_wall=include_wall,
                include_axes=include_axes,
                wall_transparency=wall_transparency,
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

            # Write script
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
                    description=f"Capture diagnostic plot",
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

            if status == "error":
                error_msg = result.get("message", "Plot capture failed")
                return error_response(f"Plot capture failed: {error_msg}")

            # Build success response
            filename = os.path.basename(output_path)
            items_included = []
            if include_ball:
                items_included.append("ball")
            if include_wall:
                items_included.append(f"wall (transparency: {wall_transparency}%)")
            if include_axes:
                items_included.append("axes")

            return success_response(
                message=f"Plot captured: {filename}",
                llm_content={
                    "parts": [{
                        "type": "text",
                        "text": (
                            f"Diagnostic plot captured: {output_path}\n\n"
                            f"Items included: {', '.join(items_included)}\n\n"
                            f"To analyze the image, use the read tool:\n"
                            f"  read(\"{output_path}\")"
                        )
                    }]
                },
                output_path=output_path,
                size=list(size),
                items=items_included,
                view_settings=view_settings if view_settings else None
            )

        except ConnectionError as e:
            return error_response(f"Cannot connect to PFC server: {str(e)}")

        except Exception as e:
            return error_response(f"Plot capture error: {str(e)}")

    print(f"[DEBUG] Registered PFC plot capture tool: pfc_capture_plot")
