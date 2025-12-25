"""
PFC Script Templates

This package contains script generation templates for PFC tools.
Scripts are generated dynamically and executed in the PFC environment.
"""

from .plot_capture_template import (
    generate_plot_capture_script,
    DEFAULT_PLOT_NAME,
    DEFAULT_WALL_TRANSPARENCY,
    DEFAULT_IMAGE_SIZE,
    BALL_COLOR_BY_SPECS,
    WALL_COLOR_BY_SPECS,
    CONTACT_COLOR_BY_SPECS,
    VECTOR_QUANTITY_OPTIONS,
    BallColorByType,
    BallShapeType,
    WallColorByType,
    ContactColorByType,
    VectorQuantityType,
    CutPlane,
)

__all__ = [
    "generate_plot_capture_script",
    "DEFAULT_PLOT_NAME",
    "DEFAULT_WALL_TRANSPARENCY",
    "DEFAULT_IMAGE_SIZE",
    "BALL_COLOR_BY_SPECS",
    "WALL_COLOR_BY_SPECS",
    "CONTACT_COLOR_BY_SPECS",
    "VECTOR_QUANTITY_OPTIONS",
    "BallColorByType",
    "BallShapeType",
    "WallColorByType",
    "ContactColorByType",
    "VectorQuantityType",
    "CutPlane",
]
