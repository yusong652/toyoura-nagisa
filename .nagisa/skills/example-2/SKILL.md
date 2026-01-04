---
name: example-2
description: A second example skill for testing multi-skill scenarios.
---

# Example Skill 2

This is a secondary demonstration skill used for testing the skill system with multiple skills.

## Purpose

This skill exists to ensure the skill system correctly handles multiple skills:
- Proper `enum` generation in tool schema (vs `const` for single skill)
- Skill list display in system prompt
- Independent skill triggering

## Instructions

When this skill is triggered:

1. Acknowledge this is a test/example skill
2. Confirm the skill system is working with multiple skills
3. You may explain how having multiple skills affects the tool schema

## Technical Details

With multiple skills:
- The `skill` parameter uses `Literal["example", "example-2"]`
- This produces `enum` in JSON Schema (Gemini-compatible)
- Single skill would produce `const` which Gemini doesn't support

## Usage

```bash
# Trigger this skill
/example-2
```
