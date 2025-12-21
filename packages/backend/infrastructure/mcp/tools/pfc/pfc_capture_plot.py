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
from typing import Dict, Any, Optional, List
from pydantic import Field
from backend.infrastructure.pfc import get_client
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.mcp.utils.path_normalization import normalize_path_separators
from .scripts import generate_plot_capture_script, DEFAULT_PLOT_NAME, DEFAULT_WALL_TRANSPARENCY, DEFAULT_IMAGE_SIZE


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
                "Absolute path for PNG file. Directory auto-created if not exists. "
                "Example: '/path/to/project/plots/model_state.png'"
            )
        ),
        size: Optional[List[int]] = Field(
            default=None,
            description="Image size [width, height] in pixels. Default: [1280, 720]."
        ),
        include_ball: bool = Field(
            default=True,
            description="Show particles (balls) in the plot."
        ),
        include_wall: bool = Field(
            default=True,
            description="Show boundary walls with transparency."
        ),
        include_axes: bool = Field(
            default=True,
            description="Show coordinate axes (X, Y, Z)."
        ),
        wall_transparency: int = Field(
            default=DEFAULT_WALL_TRANSPARENCY,
            ge=0,
            le=100,
            description="Wall transparency 0-100 (0=opaque, 100=invisible). Default: 70."
        ),
        center: Optional[List[float]] = Field(
            default=None,
            description="Camera look-at point [x, y, z]. Auto-fit if not specified."
        ),
        eye: Optional[List[float]] = Field(
            default=None,
            description="Camera position [x, y, z]. Isometric view if not specified."
        ),
        magnification: Optional[float] = Field(
            default=None,
            description="Zoom level (1.0 = normal, 2.0 = 2x closer)."
        ),
        projection: Optional[str] = Field(
            default=None,
            description="'perspective' (default) or 'parallel' (orthographic)."
        ),
    ) -> Dict[str, Any]:
        """
        Capture a diagnostic screenshot of PFC model state.

        Use this tool to visually inspect simulation state. After capture,
        use the 'read' tool on output_path for multimodal analysis to identify:
        - Particle clustering or irregular distributions
        - Boundary penetration issues
        - Stress concentration patterns
        - Model geometry problems
        """
        try:
            # Get session ID from MCP context
            session_id = getattr(context, 'client_id', None) if context else None
            if not session_id:
                return error_response("Session ID not available")

            # Validate list parameters have correct length
            if size is not None and len(size) != 2:
                return error_response("size must have exactly 2 elements [width, height]")
            if center is not None and len(center) != 3:
                return error_response("center must have exactly 3 elements [x, y, z]")
            if eye is not None and len(eye) != 3:
                return error_response("eye must have exactly 3 elements [x, y, z]")

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
                size = DEFAULT_IMAGE_SIZE

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

            # Execute script via diagnostic executor
            # This uses smart path selection on server side:
            # - If PFC idle: queue execution (fast)
            # - If cycle running: callback execution (between cycles)
            try:
                result = await client.execute_diagnostic(
                    script_path=normalized_script_path,
                    timeout_ms=30000  # 30 second timeout
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
            return success_response(
                message=f"Plot captured: {os.path.basename(output_path)}",
                llm_content={
                    "parts": [{
                        "type": "text",
                        "text": (
                            f"Plot captured: {output_path}\n\n"
                            f"To analyze, use: read(\"{output_path}\")"
                        )
                    }]
                },
                output_path=output_path
            )

        except ConnectionError as e:
            return error_response(f"Cannot connect to PFC server: {str(e)}")

        except Exception as e:
            return error_response(f"Plot capture error: {str(e)}")

    print(f"[DEBUG] Registered PFC plot capture tool: pfc_capture_plot")
