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
import time
from fastmcp import FastMCP
from fastmcp.server.context import Context
from typing import Annotated, Dict, Any, Literal, Optional, List
from pydantic import Field
from backend.infrastructure.pfc import get_client
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response
from backend.infrastructure.mcp.utils.path_normalization import normalize_path_separators
from .scripts import (
    generate_plot_capture_script,
    DEFAULT_PLOT_NAME,
    DEFAULT_WALL_TRANSPARENCY,
    DEFAULT_IMAGE_SIZE,
    BallColorByType,
    VectorQuantityType,
)


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
            pattern=r"(?i).*\.png$",
            description="Absolute path for PNG file. Directory auto-created if not exists."
        ),
        size: Annotated[List[int], Field(min_length=2, max_length=2)] = Field(
            default=list(DEFAULT_IMAGE_SIZE),
            description="Image size [width, height] in pixels."
        ),
        include_ball: bool = Field(
            default=True,
            description="Show particles (balls) in the plot."
        ),
        ball_color_by: Optional[BallColorByType] = Field(
            default=None,
            description="Ball coloring attribute."
        ),
        ball_color_by_quantity: Optional[VectorQuantityType] = Field(
            default=None,
            description="Vector component filter (ignored for scalars)."
        ),
        include_wall: bool = Field(
            default=True,
            description="Show boundary walls with transparency."
        ),
        wall_transparency: int = Field(
            default=DEFAULT_WALL_TRANSPARENCY,
            ge=0,
            le=100,
            description="Wall transparency 0-100 (0=opaque, 100=invisible). Default: 70."
        ),
        center: Optional[Annotated[List[float], Field(min_length=3, max_length=3)]] = Field(
            default=None,
            description="Camera look-at point [x, y, z]. Auto-fit if not specified."
        ),
        eye: Optional[Annotated[List[float], Field(min_length=3, max_length=3)]] = Field(
            default=None,
            description="Camera position [x, y, z]. Isometric view if not specified."
        ),
        roll: float = Field(
            default=0.0,
            description="Camera roll angle in degrees (0 = level). Only applies when eye or center is specified."
        ),
        magnification: float = Field(
            default=1.0,
            description="Zoom level (1.0 = normal, 2.0 = 2x closer)."
        ),
        projection: Literal["perspective", "parallel"] = Field(
            default="perspective",
            description="Projection mode. parallel = orthographic view."
        ),
    ) -> Dict[str, Any]:
        """
        Capture a diagnostic screenshot of PFC model state.

        Use this tool to visually inspect simulation state:
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

            output_path = output_path.strip()

            # Normalize output path for cross-platform (Linux format for PFC server)
            normalized_output_path = normalize_path_separators(output_path, target_platform='linux')

            # Build view settings dict
            view_settings: Dict[str, Any] = {}
            if center is not None:
                view_settings["center"] = list(center)
            if eye is not None:
                view_settings["eye"] = list(eye)
            # Include roll when custom camera position is used
            if center is not None or eye is not None:
                view_settings["roll"] = roll
            # Include magnification only if not default
            if magnification != 1.0:
                view_settings["magnification"] = magnification
            # Include projection when custom view settings are used
            if view_settings:
                view_settings["projection"] = projection

            # Generate Python script for plot capture
            script_content = generate_plot_capture_script(
                output_path=normalized_output_path,
                plot_name=DEFAULT_PLOT_NAME,
                size=(size[0], size[1]),
                view_settings=view_settings,
                include_ball=include_ball,
                include_wall=include_wall,
                include_axes=True,
                wall_transparency=wall_transparency,
                ball_color_by=ball_color_by,
                ball_color_by_quantity=ball_color_by_quantity or "mag",
            )

            # Get PFC client and working directory
            client = await get_client()
            working_dir = await client.get_working_directory()

            if not working_dir:
                return error_response(
                    "Cannot determine PFC working directory. "
                    "Ensure PFC server is running with a project open."
                )

            # Create and execute temporary script
            script_path = _create_temp_script(working_dir, script_content)
            normalized_script_path = normalize_path_separators(script_path, target_platform='linux')

            try:
                result = await client.execute_diagnostic(
                    script_path=normalized_script_path,
                    timeout_ms=30000
                )
            finally:
                _cleanup_script(script_path)

            # Handle execution result
            status = result.get("status")

            if status == "error":
                error_msg = result.get("message", "Plot capture failed")
                return error_response(f"Plot capture failed: {error_msg}")

            # Verify file was created (PFC export bitmap may be async)
            max_wait, elapsed = 10, 0
            while not os.path.exists(output_path) and elapsed < max_wait:
                time.sleep(0.1)
                elapsed += 0.1

            if not os.path.exists(output_path):
                return error_response(
                    f"Export completed but file not found after {max_wait}s: {output_path}"
                )

            # Build success response
            return success_response(
                message=f"Plot captured: {os.path.basename(output_path)}",
                llm_content={
                    "parts": [{
                        "type": "text",
                        "text": f"Plot captured. To analyze, use: read(\"{output_path}\")"
                    }]
                },
                output_path=output_path
            )

        except ConnectionError as e:
            return error_response(f"Cannot connect to PFC server: {str(e)}")

        except Exception as e:
            return error_response(f"Plot capture error: {str(e)}")

    print(f"[DEBUG] Registered PFC plot capture tool: pfc_capture_plot")


def _create_temp_script(working_dir: str, content: str) -> str:
    """
    Create temporary script file in PFC workspace.

    Args:
        working_dir: PFC working directory
        content: Script content to write

    Returns:
        Absolute path to created script file
    """
    script_dir = os.path.join(working_dir, ".nagisa", "plot_scripts")
    os.makedirs(script_dir, exist_ok=True)
    script_filename = f"capture_plot_{int(time.time() * 1000)}.py"
    script_path = os.path.join(script_dir, script_filename)
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return script_path


def _cleanup_script(script_path: str) -> None:
    """Remove temporary script file, ignoring errors."""
    try:
        os.remove(script_path)
    except OSError:
        pass
