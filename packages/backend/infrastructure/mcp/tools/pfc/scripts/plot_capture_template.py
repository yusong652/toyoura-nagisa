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

from typing import Dict, Any, List, Literal, Tuple, Optional


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
WALL_COLOR_BY_SPECS = {
    # Vector attributes
    "position":      {"type": "vector", "attribute": "position"},
    "velocity":      {"type": "vector", "attribute": "velocity"},
    "displacement":  {"type": "vector", "attribute": "displacement"},
    "force-contact": {"type": "vector", "attribute": "force-contact"},
    # Text attributes - all use 'Any' piece off filter
    "name":          {"type": "text", "attribute": "name"},
    "group":         {"type": "text", "attribute": "group"},
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
            # 'Any' filter means show all values (escaped for Python string)
            color_by_part = f"color-by text-attribute \"{spec['attribute']}\" \\'Any\\'"
            color_options = "color-options named maximum-names 1000000 name-controls true"
        else:
            return ""
    else:
        # Unknown value: treat as custom property (set via ball.set_prop())
        color_by_part = f'color-by numeric-property "{color_by}"'
        color_options = "color-options scaled ramp rainbow minimum automatic maximum automatic"

    return f"{color_by_part} {color_options}"


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
        elif spec["type"] == "text":
            # Wall text attributes use 'Any' piece off filter (escaped for Python string)
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
            color_by_part = f'color-by text-attribute "{spec["attribute"]}"'
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
    ball_color_by: Optional[str] = None,
    ball_color_by_quantity: str = "mag",
    wall_color_by: Optional[str] = None,
    wall_color_by_quantity: str = "mag",
    contact_color_by: Optional[str] = "force",
    contact_color_by_quantity: str = "mag",
    contact_scale_by_force: bool = True,
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
        ball_color_by: Attribute for ball coloring
        ball_color_by_quantity: Ball vector component (mag/x/y/z)
        wall_color_by: Attribute for wall coloring
        wall_color_by_quantity: Wall vector component (mag/x/y/z)
        contact_color_by: Attribute for contact coloring (default: "force")
        contact_color_by_quantity: Contact vector component (mag/x/y/z)
        contact_scale_by_force: Scale contact cylinders by force magnitude

    Returns:
        Python script content as string
    """
    lines: List[str] = [
        '"""',
        'PFC Plot Capture Script',
        'Generated by pfc_capture_plot tool',
        '',
        'This script creates a temporary diagnostic plot, exports it as PNG,',
        'then deletes the temporary plot to avoid cluttering the workspace.',
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
        color_by_cmd = _build_ball_color_by_command(ball_color_by, ball_color_by_quantity)
        if color_by_cmd:
            # active on must come right after 'ball' to enable color-by
            # legend active on is added at the end of the item create command
            lines.append(f'itasca.command(\'plot item create ball active on {color_by_cmd} legend active on\')')
        else:
            lines.append('itasca.command(\'plot item create ball\')')

    if include_wall:
        wall_color_by_cmd = _build_wall_color_by_command(wall_color_by, wall_color_by_quantity)
        if wall_color_by_cmd:
            # legend active on is added at the end of the item create command
            lines.append(f'itasca.command(\'plot item create wall active on {wall_color_by_cmd} transparency {wall_transparency} legend active on\')')
        else:
            lines.append(f'itasca.command(\'plot item create wall transparency {wall_transparency}\')')

    if include_contact:
        contact_color_by_cmd = _build_contact_color_by_command(contact_color_by, contact_color_by_quantity)
        scale_by_force = "on" if contact_scale_by_force else "off"
        if contact_color_by_cmd:
            lines.append(f'itasca.command(\'plot item create contact active on {contact_color_by_cmd} scale-by-force {scale_by_force} legend active on\')')
        else:
            lines.append(f'itasca.command(\'plot item create contact scale-by-force {scale_by_force}\')')

    if include_axes:
        lines.append('itasca.command(\'plot item create axes\')')

    lines.append('')

    # Export section
    lines.extend([
        '# Export plot as PNG',
        f'itasca.command(f\'plot "{plot_name}" export bitmap filename "{{output_path}}" size {size[0]} {size[1]}\')',
        '',
        '# Wait for export to complete (export bitmap is async)',
        'import time',
        '_max_wait, _elapsed = 10, 0',
        'while not os.path.exists(output_path) and _elapsed < _max_wait:',
        '    time.sleep(0.1)',
        '    _elapsed += 0.1',
        '',
    ])

    # Cleanup section
    # Syntax: plot <name> delete (name before delete keyword)
    lines.extend([
        '# Delete temporary plot (after export completes)',
        f'itasca.command(\'plot "{plot_name}" delete\')',
        '',
        'print(f"Plot captured successfully: {output_path}")',
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