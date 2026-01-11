"""
PFC Plot Capture Script Template

This module provides script generation for the pfc_capture_plot tool.
Scripts are generated dynamically based on parameters and executed in PFC.

Design Philosophy:
- Create temporary plot to avoid interfering with user's plots
- Include sensible defaults for ball, wall visualization
- Support customizable view settings
- Auto-cleanup temporary plot after export
"""

from typing import Dict, Any, List, Literal, Tuple, Optional, Annotated, Union
from pydantic import BaseModel, Field, BeforeValidator
import re


# Type definitions for tool parameters (keep in sync with SPECS below)
BallColorByType = Literal[
    # Vector attributes
    "position", "velocity", "displacement", "spin",
    "force-contact", "force-applied", "force-unbalanced",
    "moment-contact", "moment-applied", "moment-unbalanced",
    # Numeric (scalar) attributes
    "radius", "damp", "density", "mass",
    # Text attributes
    "id", "group",
]
WallColorByType = Literal[
    # Vector attributes
    "position", "velocity", "displacement", "force-contact",
    # Text attributes
    "name", "group",
]
ContactColorByType = Literal[
    # Vector attributes
    "force",
    # Text attributes
    "id", "group", "contact-type", "model-name",
    # Numeric properties
    "fric", "kn", "ks", "dp_nratio", "dp_sratio",
    "emod", "kratio", "rr_fric", "rr_kr", "rr_slip",
]
VectorQuantityType = Literal["mag", "x", "y", "z"]
BallShapeType = Literal["sphere", "arrow"]

# Pattern for extra-N attributes (e.g., extra-1, extra-2)
EXTRA_PATTERN = re.compile(r"^extra-\d+$", re.IGNORECASE)


def _validate_ball_color_by(value: Optional[str]) -> Optional[str]:
    """Validate ball_color_by accepts Literal values or extra-N pattern."""
    if value is None:
        return None
    v = value.lower()
    # Check if it's a known attribute
    if v in (
        "position", "velocity", "displacement", "spin",
        "force-contact", "force-applied", "force-unbalanced",
        "moment-contact", "moment-applied", "moment-unbalanced",
        "radius", "damp", "density", "mass", "id", "group",
    ):
        return value
    # Check extra-N pattern
    if EXTRA_PATTERN.match(v):
        return value
    raise ValueError(
        f"Invalid ball_color_by: '{value}'. "
        f"Valid: position, velocity, displacement, spin, force-contact, force-applied, "
        f"radius, damp, density, mass, id, group, extra-1, extra-2, ..."
    )


def _validate_wall_color_by(value: Optional[str]) -> Optional[str]:
    """Validate wall_color_by accepts Literal values or extra-N pattern."""
    if value is None:
        return None
    v = value.lower()
    if v in ("position", "velocity", "displacement", "force-contact", "name", "group"):
        return value
    if EXTRA_PATTERN.match(v):
        return value
    raise ValueError(
        f"Invalid wall_color_by: '{value}'. "
        f"Valid: position, velocity, displacement, force-contact, name, group, extra-1, extra-2, ..."
    )


def _validate_contact_color_by(value: Optional[str]) -> Optional[str]:
    """Validate contact_color_by accepts Literal values or extra-N pattern."""
    if value is None:
        return None
    v = value.lower()
    if v in (
        "force", "id", "group", "contact-type", "model-name",
        "fric", "kn", "ks", "dp_nratio", "dp_sratio",
        "emod", "kratio", "rr_fric", "rr_kr", "rr_slip",
    ):
        return value
    if EXTRA_PATTERN.match(v):
        return value
    raise ValueError(
        f"Invalid contact_color_by: '{value}'. "
        f"Valid: force, id, group, contact-type, model-name, fric, kn, ks, extra-1, extra-2, ..."
    )


# Validated types for tool parameters (supports Literal values + extra-N pattern)
ValidatedBallColorBy = Annotated[Optional[str], BeforeValidator(_validate_ball_color_by)]
ValidatedWallColorBy = Annotated[Optional[str], BeforeValidator(_validate_wall_color_by)]
ValidatedContactColorBy = Annotated[Optional[str], BeforeValidator(_validate_contact_color_by)]


class CutPlane(BaseModel):
    """Cut plane definition for clipping plot items."""
    origin: Annotated[List[float], Field(min_length=3, max_length=3, description="Cut plane origin [x, y, z]")]
    normal: Annotated[List[float], Field(min_length=3, max_length=3, description="Cut plane normal vector [nx, ny, nz]")]


# Default plot configuration
DEFAULT_PLOT_NAME = "NagisaDiagnostic"
DEFAULT_WALL_TRANSPARENCY = 70  # 0-100, 70 = 70% transparent
DEFAULT_IMAGE_SIZE = (720, 480)

# Valid quantity options for vector attributes
# Maps to PFC syntax: vector-attribute "name" quantity <value>
VECTOR_QUANTITY_OPTIONS = ("mag", "x", "y", "z")

# Ball color-by specifications
# Maps attribute keywords to PFC command syntax
BALL_COLOR_BY_SPECS = {
    # Vector attributes - use ball_color_by_quantity to select component (mag/x/y/z)
    "position":          {"type": "vector",  "attribute": "position"},
    "velocity":          {"type": "vector",  "attribute": "velocity"},
    "displacement":      {"type": "vector",  "attribute": "displacement"},
    "spin":              {"type": "vector",  "attribute": "spin"},
    "force-contact":     {"type": "vector",  "attribute": "force-contact"},
    "force-applied":     {"type": "vector",  "attribute": "force-applied"},
    "force-unbalanced":  {"type": "vector",  "attribute": "force-unbalanced"},
    "moment-contact":    {"type": "vector",  "attribute": "moment-contact"},
    "moment-applied":    {"type": "vector",  "attribute": "moment-applied"},
    "moment-unbalanced": {"type": "vector",  "attribute": "moment-unbalanced"},
    # Numeric (scalar) attributes - ball_color_by_quantity is ignored
    "radius":            {"type": "numeric", "attribute": "radius"},
    "damp":              {"type": "numeric", "attribute": "damp"},
    "density":           {"type": "numeric", "attribute": "density"},
    "mass":              {"type": "numeric", "attribute": "mass"},
    # Text attributes - ball_color_by_quantity is ignored, uses named color mapping
    "id":                {"type": "text", "attribute": "id"},
    "group":             {"type": "text", "attribute": "group"},
}

# Wall color-by specifications (subset of ball attributes applicable to walls)
# Text attribute syntax differs:
#   - "name": color-by text-attribute "name" (no filter)
#   - "group": color-by text-attribute "group" 'Any' piece off (requires filter)
WALL_COLOR_BY_SPECS = {
    # Vector attributes
    "position":      {"type": "vector", "attribute": "position"},
    "velocity":      {"type": "vector", "attribute": "velocity"},
    "displacement":  {"type": "vector", "attribute": "displacement"},
    "force-contact": {"type": "vector", "attribute": "force-contact"},
    # Text attributes - different filter requirements
    "name":          {"type": "text-name", "attribute": "name"},       # no filter needed
    "group":         {"type": "text-group", "attribute": "group"},     # requires 'Any' piece off
}

# Contact color-by specifications
CONTACT_COLOR_BY_SPECS = {
    # Vector attributes
    "force": {"type": "vector", "attribute": "force"},
    # Text attributes
    "id":           {"type": "text", "attribute": "id"},
    "group":        {"type": "text", "attribute": "group"},
    "contact-type": {"type": "text", "attribute": "contact type"},
    "model-name":   {"type": "text", "attribute": "model name"},
    # Numeric properties (uses numeric-property, not numeric-attribute)
    "fric":       {"type": "numeric-property", "property": "fric"},
    "kn":         {"type": "numeric-property", "property": "kn"},
    "ks":         {"type": "numeric-property", "property": "ks"},
    "dp_nratio":  {"type": "numeric-property", "property": "dp_nratio"},
    "dp_sratio":  {"type": "numeric-property", "property": "dp_sratio"},
    "emod":       {"type": "numeric-property", "property": "emod"},
    "kratio":     {"type": "numeric-property", "property": "kratio"},
    "rr_fric":    {"type": "numeric-property", "property": "rr_fric"},
    "rr_kr":      {"type": "numeric-property", "property": "rr_kr"},
    "rr_slip":    {"type": "numeric-property", "property": "rr_slip"},
}


def _build_ball_color_by_command(
    color_by: Optional[str],
    quantity: str = "mag",
) -> str:
    """
    Build PFC color-by command string from attribute and quantity.

    Encapsulates PFC syntax:
    - Vector: color-by vector-attribute "name" quantity <mag|x|y|z>
    - Numeric: color-by numeric-attribute "name" (quantity ignored)
    - Text: color-by text-attribute "name" (quantity ignored, uses named colors)

    Args:
        color_by: Attribute name (e.g., "velocity", "position", "radius", "id", "group")
        quantity: Component for vectors: "mag", "x", "y", "z". Default: "mag"

    Returns:
        PFC color-by command fragment, or empty string if invalid
    """
    if not color_by:
        return ""

    # Validate and normalize quantity for vectors
    qty = quantity.lower() if quantity else "mag"
    if qty not in VECTOR_QUANTITY_OPTIONS:
        qty = "mag"

    # Handle "extra-N" pattern (e.g., "extra-1" -> numeric-attribute "extra" 1)
    color_by_lower = color_by.lower()
    if color_by_lower.startswith("extra-"):
        try:
            extra_index = int(color_by_lower.split("-", 1)[1])
            color_by_part = f'color-by numeric-attribute "extra" {extra_index}'
            color_options = "color-options scaled ramp rainbow minimum automatic maximum automatic"
            return f"{color_by_part} {color_options}"
        except (IndexError, ValueError):
            pass  # Fall through to normal handling

    spec = BALL_COLOR_BY_SPECS.get(color_by_lower)

    # Build color-by command based on attribute type
    if spec:
        if spec["type"] == "vector":
            color_by_part = f'color-by vector-attribute "{spec["attribute"]}" quantity {qty}'
            color_options = "color-options scaled ramp rainbow minimum automatic maximum automatic"
        elif spec["type"] == "numeric":
            color_by_part = f'color-by numeric-attribute "{spec["attribute"]}"'
            color_options = "color-options scaled ramp rainbow minimum automatic maximum automatic"
        elif spec["type"] == "text":
            # Text attributes need 'Any' filter to show all values
            # Escape single quotes for embedding in itasca.command('...')
            color_by_part = f"color-by text-attribute \"{spec['attribute']}\" \\'Any\\'"
            color_options = "color-options named maximum-names 1000000 name-controls true"
        else:
            return ""
    else:
        # Unknown value: treat as custom property (set via ball.set_prop())
        color_by_part = f'color-by numeric-property "{color_by}"'
        color_options = "color-options scaled ramp rainbow minimum automatic maximum automatic"

    return f"{color_by_part} {color_options}"


def _build_ball_arrow_command(
    color_by: str,
    quantity: str = "mag",
) -> str:
    """
    Build PFC ball arrow shape command for vector visualization.

    Arrow mode displays vectors as directional arrows with color indicating magnitude.
    Only valid for vector attributes (velocity, displacement, force-contact, etc.).

    PFC syntax:
        plot item create ball active on
            shape arrow scale automatic arrow-quality 8
            color-by vector-attribute "velocity" quantity mag
            color-options scaled ramp rainbow minimum automatic maximum automatic
            scale-by-magnitude off
            [cut ...]
            legend active on

    Note: legend is added separately after cut command in the caller.

    Args:
        color_by: Vector attribute name (e.g., "velocity", "displacement")
        quantity: Vector component: "mag", "x", "y", "z". Default: "mag"

    Returns:
        PFC command fragment for arrow visualization (without legend)
    """
    # Validate and normalize quantity
    qty = quantity.lower() if quantity else "mag"
    if qty not in VECTOR_QUANTITY_OPTIONS:
        qty = "mag"

    return (
        f'shape arrow scale automatic arrow-quality 8 '
        f'color-by vector-attribute "{color_by}" quantity {qty} '
        f'color-options scaled ramp rainbow minimum automatic maximum automatic '
        f'scale-by-magnitude off'
    )


def _build_wall_color_by_command(
    color_by: Optional[str],
    quantity: str = "mag",
) -> str:
    """
    Build PFC wall color-by command string from attribute and quantity.

    Encapsulates PFC syntax:
    - Vector: color-by vector-attribute "name" quantity <mag|x|y|z>
    - Text: color-by text-attribute "name" (quantity ignored, uses named colors)
    - Custom: Unknown values treated as numeric-property (for wall.set_prop())

    Args:
        color_by: Attribute name (e.g., "velocity", "position", "name", or custom property)
        quantity: Component for vectors: "mag", "x", "y", "z". Default: "mag"

    Returns:
        PFC color-by command fragment, or empty string if invalid
    """
    if not color_by:
        return ""

    # Validate and normalize quantity for vectors
    qty = quantity.lower() if quantity else "mag"
    if qty not in VECTOR_QUANTITY_OPTIONS:
        qty = "mag"

    # Handle "extra-N" pattern (e.g., "extra-1" -> numeric-attribute "extra" 1)
    color_by_lower = color_by.lower()
    if color_by_lower.startswith("extra-"):
        try:
            extra_index = int(color_by_lower.split("-", 1)[1])
            color_by_part = f'color-by numeric-attribute "extra" {extra_index}'
            color_options = "color-options scaled ramp rainbow minimum automatic maximum automatic"
            return f"{color_by_part} {color_options}"
        except (IndexError, ValueError):
            pass  # Fall through to normal handling

    spec = WALL_COLOR_BY_SPECS.get(color_by_lower)

    # Build color-by command based on attribute type
    if spec:
        if spec["type"] == "vector":
            color_by_part = f'color-by vector-attribute "{spec["attribute"]}" quantity {qty}'
            color_options = "color-options scaled ramp rainbow minimum automatic maximum automatic"
        elif spec["type"] == "text-name":
            # Wall "name" attribute - no filter needed
            color_by_part = f'color-by text-attribute "{spec["attribute"]}"'
            color_options = "color-options named maximum-names 1000000 name-controls true"
        elif spec["type"] == "text-group":
            # Wall "group" attribute - requires 'Any' piece off filter
            # Escape single quotes for embedding in itasca.command('...')
            color_by_part = f"color-by text-attribute \"{spec['attribute']}\" \\'Any\\' piece off"
            color_options = "color-options named maximum-names 1000000 name-controls true"
        else:
            return ""
    else:
        # Unknown value: treat as custom property (set via wall.set_prop())
        color_by_part = f'color-by numeric-property "{color_by}"'
        color_options = "color-options scaled ramp rainbow minimum automatic maximum automatic"

    return f"{color_by_part} {color_options}"


def _build_contact_color_by_command(
    color_by: Optional[str],
    quantity: str = "mag",
) -> str:
    """
    Build PFC contact color-by command string from attribute and quantity.

    Encapsulates PFC syntax:
    - Vector: color-by vector-attribute "force" quantity <mag|x|y|z>
    - Text: color-by text-attribute "model name" (quantity ignored, uses named colors)
    - Numeric: color-by numeric-property "fric" (known contact properties)
    - Custom: Unknown values treated as numeric-property (for contact.set_prop())

    Args:
        color_by: Attribute name (e.g., "force", "model-name", "fric", or custom property)
        quantity: Component for vectors: "mag", "x", "y", "z". Default: "mag"

    Returns:
        PFC color-by command fragment, or empty string if invalid
    """
    if not color_by:
        return ""

    # Validate and normalize quantity for vectors
    qty = quantity.lower() if quantity else "mag"
    if qty not in VECTOR_QUANTITY_OPTIONS:
        qty = "mag"

    # Handle "extra-N" pattern (e.g., "extra-1" -> numeric-attribute "extra" 1)
    color_by_lower = color_by.lower()
    if color_by_lower.startswith("extra-"):
        try:
            extra_index = int(color_by_lower.split("-", 1)[1])
            color_by_part = f'color-by numeric-attribute "extra" {extra_index}'
            color_options = "color-options scaled ramp rainbow minimum automatic maximum automatic"
            return f"{color_by_part} {color_options}"
        except (IndexError, ValueError):
            pass  # Fall through to normal handling

    spec = CONTACT_COLOR_BY_SPECS.get(color_by_lower)

    # Build color-by command based on attribute type
    if spec:
        if spec["type"] == "vector":
            color_by_part = f'color-by vector-attribute "{spec["attribute"]}" quantity {qty}'
            color_options = "color-options scaled ramp rainbow minimum automatic maximum automatic"
        elif spec["type"] == "text":
            # Contact text attributes need 'Any' filter to show all values
            # Escape single quotes for embedding in itasca.command('...')
            color_by_part = f"color-by text-attribute \"{spec['attribute']}\" \\'Any\\'"
            color_options = "color-options named maximum-names 1000000 name-controls true"
        elif spec["type"] == "numeric-property":
            color_by_part = f'color-by numeric-property "{spec["property"]}"'
            color_options = "color-options scaled ramp rainbow minimum automatic maximum automatic"
        else:
            return ""
    else:
        # Unknown value: treat as custom property (set via contact.set_prop())
        color_by_part = f'color-by numeric-property "{color_by}"'
        color_options = "color-options scaled ramp rainbow minimum automatic maximum automatic"

    return f"{color_by_part} {color_options}"


def _build_cut_command(cut: Optional["CutPlane"]) -> str:
    """
    Build PFC cut command string from CutPlane object.

    PFC syntax:
        cut active on type plane surface on front on back off origin (x,y,z) normal (nx,ny,nz)

    Args:
        cut: CutPlane with origin and normal vectors

    Returns:
        PFC cut command fragment, or empty string if cut is None
    """
    if not cut:
        return ""

    o = cut.origin
    n = cut.normal
    return f"cut active on type plane surface on front on back off origin ({o[0]},{o[1]},{o[2]}) normal ({n[0]},{n[1]},{n[2]})"


def generate_plot_capture_script(
    output_path: str,
    plot_name: str = DEFAULT_PLOT_NAME,
    size: Tuple[int, int] = DEFAULT_IMAGE_SIZE,
    view_settings: Optional[Dict[str, Any]] = None,
    include_ball: bool = True,
    include_wall: bool = True,
    include_contact: bool = False,
    include_axes: bool = True,
    wall_transparency: int = DEFAULT_WALL_TRANSPARENCY,
    ball_shape: str = "sphere",
    ball_color_by: Optional[str] = None,
    ball_color_by_quantity: str = "mag",
    wall_color_by: Optional[str] = None,
    wall_color_by_quantity: str = "mag",
    contact_color_by: Optional[str] = "force",
    contact_color_by_quantity: str = "mag",
    contact_scale_by_force: bool = True,
    ball_cut: Optional["CutPlane"] = None,
    wall_cut: Optional["CutPlane"] = None,
    contact_cut: Optional["CutPlane"] = None,
) -> str:
    """
    Generate Python script for PFC plot capture.

    Creates a temporary plot, adds visualization items, exports as PNG,
    then deletes the temporary plot.

    Args:
        output_path: Absolute path for output PNG file (forward slashes)
        plot_name: Name for temporary plot (default: "NagisaDiagnostic")
        size: Image dimensions (width, height)
        view_settings: Optional view parameters dict
        include_ball: Add ball visualization item
        include_wall: Add wall visualization item
        include_contact: Add contact force visualization item
        include_axes: Add coordinate axes
        wall_transparency: Wall transparency 0-100 (default: 70)
        ball_shape: Ball shape "sphere" or "arrow" (arrow only for vector attributes)
        ball_color_by: Attribute for ball coloring
        ball_color_by_quantity: Ball vector component (mag/x/y/z)
        wall_color_by: Attribute for wall coloring
        wall_color_by_quantity: Wall vector component (mag/x/y/z)
        contact_color_by: Attribute for contact coloring (default: "force")
        contact_color_by_quantity: Contact vector component (mag/x/y/z)
        contact_scale_by_force: Scale contact cylinders by force magnitude
        ball_cut: Optional cut plane for balls
        wall_cut: Optional cut plane for walls
        contact_cut: Optional cut plane for contacts

    Returns:
        Python script content as string
    """
    lines: List[str] = [
        '"""',
        'PFC Plot Capture Script',
        'Generated by pfc_capture_plot tool',
        '',
        'Uses fixed plot name - plot create auto-clears items if plot exists.',
        'No delete needed, next capture will reset the plot.',
        '"""',
        '',
        'import itasca',
        'import os',
        '',
        '# Configuration',
        f'output_path = r"{output_path}"',
        f'plot_name = "{plot_name}"',
        '',
        '# Ensure output directory exists and disable Windows thumbnails',
        'output_dir = os.path.dirname(output_path)',
        'os.makedirs(output_dir, exist_ok=True)',
        '',
        '# Create desktop.ini to disable Windows thumbnail generation (reduces folder lag)',
        'desktop_ini_path = os.path.join(output_dir, "desktop.ini")',
        'if not os.path.exists(desktop_ini_path):',
        '    with open(desktop_ini_path, "w") as f:',
        '        f.write("[ViewState]\\nFolderType=Generic\\n")',
        '    # Set hidden and system attributes (Windows, hide cmd window)',
        '    import subprocess',
        '    subprocess.run(["attrib", "+H", "+S", desktop_ini_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=0x08000000)',
        '',
    ]

    # Create plot section
    lines.extend([
        '# Create temporary diagnostic plot',
        f'itasca.command(\'plot create "{plot_name}"\')',
        f'itasca.command(\'plot background "white"\')',
        '',
    ])

    # View settings section
    lines.append('# Set view')
    view_cmd_parts = _build_view_command(view_settings)
    if view_cmd_parts:
        # Apply custom view settings
        lines.append(f'itasca.command(\'plot view {view_cmd_parts}\')')
    else:
        # Default: isometric view (standard engineering visualization)
        lines.append('itasca.command(\'plot view isometric\')')
    lines.append('')

    # Add plot items section
    lines.append('# Add visualization items')

    if include_ball:
        cut_cmd = _build_cut_command(ball_cut)

        # Check if arrow mode is valid (requires vector attribute)
        use_arrow = False
        if ball_shape == "arrow" and ball_color_by:
            spec = BALL_COLOR_BY_SPECS.get(ball_color_by.lower())
            if spec and spec["type"] == "vector":
                use_arrow = True

        if use_arrow:
            # Arrow mode: vector visualization with directional arrows
            # ball_color_by is guaranteed non-None here (checked in use_arrow condition)
            arrow_cmd = _build_ball_arrow_command(ball_color_by, ball_color_by_quantity)  # type: ignore[arg-type]
            cmd_parts = ["plot item create ball active on", arrow_cmd]
            if cut_cmd:
                cmd_parts.append(cut_cmd)
            cmd_parts.append("legend active on")
            lines.append(f"itasca.command('{' '.join(cmd_parts)}')")
        else:
            # Sphere mode: standard ball visualization
            color_by_cmd = _build_ball_color_by_command(ball_color_by, ball_color_by_quantity)
            cmd_parts = ["plot item create ball active on"]
            if color_by_cmd:
                cmd_parts.append(color_by_cmd)
            if cut_cmd:
                cmd_parts.append(cut_cmd)
            if color_by_cmd or cut_cmd:
                cmd_parts.append("legend active on")
            lines.append(f"itasca.command('{' '.join(cmd_parts)}')")

    if include_wall:
        wall_color_by_cmd = _build_wall_color_by_command(wall_color_by, wall_color_by_quantity)
        cut_cmd = _build_cut_command(wall_cut)
        cmd_parts = ["plot item create wall active on"]
        if wall_color_by_cmd:
            cmd_parts.append(wall_color_by_cmd)
        cmd_parts.append(f"transparency {wall_transparency}")
        if cut_cmd:
            cmd_parts.append(cut_cmd)
        if wall_color_by_cmd or cut_cmd:
            cmd_parts.append("legend active on")
        lines.append(f"itasca.command('{' '.join(cmd_parts)}')")

    if include_contact:
        contact_color_by_cmd = _build_contact_color_by_command(contact_color_by, contact_color_by_quantity)
        cut_cmd = _build_cut_command(contact_cut)
        scale_by_force = "on" if contact_scale_by_force else "off"
        cmd_parts = ["plot item create contact active on"]
        if contact_color_by_cmd:
            cmd_parts.append(contact_color_by_cmd)
        cmd_parts.append(f"scale-by-force {scale_by_force}")
        if cut_cmd:
            cmd_parts.append(cut_cmd)
        if contact_color_by_cmd or cut_cmd:
            cmd_parts.append("legend active on")
        lines.append(f"itasca.command('{' '.join(cmd_parts)}')")

    if include_axes:
        lines.append('itasca.command(\'plot item create axes\')')

    lines.append('')

    # Export section
    # NOTE: export bitmap is async - file verification is done by pfc-server
    # using non-blocking async wait. No delete needed - next capture resets plot.
    lines.extend([
        '# Export plot as PNG (async operation)',
        '# File verification handled by pfc-server, no delete needed',
        f'itasca.command(f\'plot "{plot_name}" export bitmap filename "{{output_path}}" size {size[0]} {size[1]}\')',
        '',
        '# Return output path for file verification',
        'result = {"output_path": output_path}',
        '',
        'print(f"Plot export initiated: {output_path}")',
    ])

    return '\n'.join(lines)


def _build_view_command(view_settings: Optional[Dict[str, Any]]) -> str:
    """
    Build view command string from settings dict.

    Args:
        view_settings: Dict with view parameters (center, eye, distance, etc.)

    Returns:
        View command parameters string, or empty string if no settings
    """
    if not view_settings:
        return ""

    parts: List[str] = []

    # Projection mode (always provided by tool layer)
    parts.append(f"projection {view_settings['projection']}")

    # Camera position
    if "center" in view_settings:
        c = view_settings["center"]
        parts.append(f"center ({c[0]},{c[1]},{c[2]})")

    if "eye" in view_settings:
        e = view_settings["eye"]
        parts.append(f"eye ({e[0]},{e[1]},{e[2]})")

    # View parameters
    if "distance" in view_settings:
        parts.append(f"distance {view_settings['distance']}")

    if "magnification" in view_settings:
        parts.append(f"magnification {view_settings['magnification']}")

    if "dip" in view_settings:
        parts.append(f"dip {view_settings['dip']}")

    if "dip_direction" in view_settings:
        parts.append(f"dip-direction {view_settings['dip_direction']}")

    if "roll" in view_settings:
        parts.append(f"roll {view_settings['roll']}")

    return " ".join(parts)