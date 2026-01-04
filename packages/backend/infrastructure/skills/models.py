"""
Skill metadata models.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class SkillMetadata:
    """
    Metadata for a skill, extracted from SKILL.md YAML frontmatter.

    Attributes:
        name: Unique identifier for the skill (e.g., 'commit', 'test')
        description: Short description for system prompt metadata
        path: Absolute path to the SKILL.md file
        base_dir: Directory containing the skill (for resource resolution)
    """

    name: str
    description: str
    path: Path
    base_dir: Path

    def to_xml(self) -> str:
        """Generate XML representation for system prompt injection."""
        return f"""<skill>
  <name>{self.name}</name>
  <description>{self.description}</description>
</skill>"""
