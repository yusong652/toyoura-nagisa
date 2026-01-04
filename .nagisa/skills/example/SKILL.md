---
name: example
description: An example skill demonstrating the skill system structure and usage patterns.
---

# Example Skill

This is a demonstration skill showing the structure and patterns for creating skills in toyoura-nagisa.

## Purpose

This skill serves as a template and reference for creating new skills. It demonstrates:
- YAML frontmatter format for metadata
- Markdown content structure
- How skills are loaded and triggered

## Instructions

When this skill is triggered, you should:

1. Acknowledge that this is an example skill
2. Explain the skill system to the user if they ask
3. Guide them on how to create their own skills

## Skill File Structure

Skills are stored in `.nagisa/skills/` with the following structure:

```
.nagisa/skills/
├── skill-name/
│   └── SKILL.md          # Required: Skill definition
│   └── resources/        # Optional: Additional files
└── another-skill/
    └── SKILL.md
```

## YAML Frontmatter

Every SKILL.md must have a YAML frontmatter with:
- `name`: Unique identifier (used to trigger the skill)
- `description`: Short description (shown in system prompt)

## Creating New Skills

1. Create a directory under `.nagisa/skills/`
2. Create a `SKILL.md` file with YAML frontmatter
3. Add instructions and guidance in the markdown body
4. The skill will be automatically discovered on next startup

## Examples

```bash
# Trigger this skill
/example

# Or with arguments
/example show me how to create a skill
```
