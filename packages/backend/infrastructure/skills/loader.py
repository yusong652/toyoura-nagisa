"""
Skills loader for scanning and loading skill definitions.
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from .models import SkillMetadata

logger = logging.getLogger(__name__)

# Default skills directory relative to project root
DEFAULT_SKILLS_DIR = ".nagisa/skills"

# Singleton instance
_skills_loader: Optional["SkillsLoader"] = None


class SkillsLoader:
    """
    Loader for skill definitions from .nagisa/skills/ directory.

    Implements the Skills pattern from Claude Code:
    - Scans for SKILL.md files in subdirectories
    - Extracts YAML frontmatter for metadata
    - Generates XML for system prompt injection
    - Provides full content for trigger_skill tool
    """

    def __init__(self, skills_dir: Path):
        """
        Initialize the SkillsLoader and scan for skills.

        Args:
            skills_dir: Path to the skills directory (e.g., .nagisa/skills/)
        """
        self.skills_dir = skills_dir
        self._skills: Dict[str, SkillMetadata] = {}
        self._scan_skills()

    def _scan_skills(self) -> None:
        """Scan the skills directory and load all SKILL.md files."""
        self._skills.clear()

        if not self.skills_dir.exists():
            logger.debug(f"Skills directory does not exist: {self.skills_dir}")
            return

        # Scan for SKILL.md files in subdirectories
        for skill_path in self.skills_dir.glob("**/SKILL.md"):
            try:
                metadata = self._parse_skill_file(skill_path)
                if metadata:
                    if metadata.name in self._skills:
                        logger.warning(
                            f"Duplicate skill name '{metadata.name}' found. "
                            f"Keeping: {self._skills[metadata.name].path}, "
                            f"Ignoring: {skill_path}"
                        )
                    else:
                        self._skills[metadata.name] = metadata
                        logger.debug(f"Loaded skill: {metadata.name} from {skill_path}")
            except Exception as e:
                logger.error(f"Failed to parse skill file {skill_path}: {e}")

        logger.info(f"Loaded {len(self._skills)} skills from {self.skills_dir}")

    def _parse_skill_file(self, path: Path) -> Optional[SkillMetadata]:
        """
        Parse a SKILL.md file and extract metadata from YAML frontmatter.

        Args:
            path: Path to the SKILL.md file

        Returns:
            SkillMetadata if parsing succeeds, None otherwise
        """
        content = path.read_text(encoding="utf-8")

        # Extract YAML frontmatter (between --- markers)
        frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if not frontmatter_match:
            logger.warning(f"No YAML frontmatter found in {path}")
            return None

        try:
            frontmatter = yaml.safe_load(frontmatter_match.group(1))
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in {path}: {e}")
            return None

        # Validate required fields
        name = frontmatter.get("name")
        description = frontmatter.get("description")

        if not name:
            logger.warning(f"Missing 'name' field in {path}")
            return None
        if not description:
            logger.warning(f"Missing 'description' field in {path}")
            return None

        return SkillMetadata(
            name=name,
            description=description,
            path=path,
            base_dir=path.parent,
        )

    def get_available_skills_xml(self, allowed_skills: Optional[List[str]] = None) -> str:
        """
        Generate XML representation of available skills for system prompt.

        Args:
            allowed_skills: Optional list of skill names to include. If None, include all.

        Returns:
            XML string with <available_skills> wrapper containing skill metadata
        """
        # Determine which skills to include
        if allowed_skills is not None:
            skills_to_include = [
                self._skills[name] for name in allowed_skills
                if name in self._skills
            ]
            # Warn about missing skills
            for name in allowed_skills:
                if name not in self._skills:
                    logger.warning(f"Configured skill '{name}' not found in .nagisa/skills/")
        else:
            skills_to_include = list(self._skills.values())

        if not skills_to_include:
            return "<available_skills>\n  <!-- No skills available -->\n</available_skills>"

        skills_xml = "<available_skills>\n"
        for skill in sorted(skills_to_include, key=lambda s: s.name):
            skill_xml = skill.to_xml()
            indented = "\n".join(f"  {line}" for line in skill_xml.split("\n"))
            skills_xml += indented + "\n"
        skills_xml += "</available_skills>"

        return skills_xml

    def get_skill(self, skill_name: str) -> Optional[SkillMetadata]:
        """
        Get metadata for a specific skill by name.

        Args:
            skill_name: Name of the skill to retrieve

        Returns:
            SkillMetadata if found, None otherwise
        """
        return self._skills.get(skill_name)

    def get_skill_content(self, skill_name: str) -> Optional[str]:
        """
        Load the full SKILL.md content for a skill.

        This is used by the trigger_skill tool to inject skill instructions
        into the conversation context.

        Args:
            skill_name: Name of the skill to load

        Returns:
            Full content of SKILL.md including base directory info, None if not found
        """
        skill = self.get_skill(skill_name)
        if not skill:
            return None

        content = skill.path.read_text(encoding="utf-8")

        # Prepend base directory info for resource resolution
        return f"Base directory: {skill.base_dir}\n\n{content}"

    def list_skills(self) -> List[str]:
        """
        List all available skill names.

        Returns:
            List of skill names
        """
        return sorted(self._skills.keys())

    def reload(self) -> List[SkillMetadata]:
        """
        Reload all skills from disk.

        Returns:
            List of SkillMetadata for all discovered skills
        """
        self._scan_skills()
        return list(self._skills.values())


def get_skills_loader() -> SkillsLoader:
    """
    Get the singleton SkillsLoader instance.

    Returns:
        SkillsLoader instance
    """
    global _skills_loader

    if _skills_loader is None:
        # Use current working directory as project root
        project_root = Path.cwd()
        skills_dir = project_root / DEFAULT_SKILLS_DIR
        _skills_loader = SkillsLoader(skills_dir)

    return _skills_loader


def reset_skills_loader() -> None:
    """Reset the singleton loader (useful for testing)."""
    global _skills_loader
    _skills_loader = None
