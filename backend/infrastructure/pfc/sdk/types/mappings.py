"""Type system mappings for PFC SDK.

This module defines mappings between PFC object classes and their
parent modules, used for generating official API paths.
"""

# Object class to module mapping
# Maps class names to their parent module names in PFC Python SDK
# Format: "ClassName" -> "module_name"
# Official API path structure: itasca.{module}.{Class}.{method}
#
# Examples:
#   Ball -> ball module -> itasca.ball.Ball.vel()
#   Facet -> wall module -> itasca.wall.Facet.vel()
#   Pebble -> clump module -> itasca.clump.Pebble.vel()
CLASS_TO_MODULE = {
    "Ball": "ball",
    "Clump": "clump",
    "Contact": "contact",  # Generic contact interface
    "Measure": "measure",
    "Wall": "wall",
    "Facet": "wall",       # Facet is under wall module
    "Pebble": "clump",     # Pebble is under clump module
}
