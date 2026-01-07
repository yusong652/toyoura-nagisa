# Skills Design Lessons: Workflow Guidance vs General Capability

**Date**: 2025-01-07
**Context**: Implementing skills feature for toyoura-nagisa PFC agent

---

## The Detour

Initially, we considered skills as another form of capability extension, similar to tools. This led to confusion about:
- When to use skills vs tools
- What content should go into skills
- How to present skills in the system prompt

## The Insight

**Skills are not general capabilities — they are workflow guidance for specific situations.**

| Aspect | Tools | Skills |
|--------|-------|--------|
| **Nature** | Actions the agent can perform | Decision guidance for specific scenarios |
| **Loading** | Always available via API schemas | On-demand injection via `trigger_skill` |
| **Content** | Execute operations | Reference workflows |
| **Token cost** | Schema always consumed | Only when triggered |
| **Analogy** | Hands and eyes | Reference manual |

## The Correct Mental Model

```
Tools = "What can I do?"
Skills = "How should I approach this situation?"
```

### Example: PFC Skills

| Skill | Not a capability, but... |
|-------|-------------------------|
| `pfc-server-setup` | Step-by-step guide when PFC server connection fails |
| `pfc-package-management` | Workflow for installing packages in PFC's embedded Python |
| `pfc-error-resolution` | Decision tree for diagnosing different error types |

These are **experiential knowledge**, not **new abilities**.

## Implementation Pattern

```
User request
    ↓
Agent judges: "Does this match a known workflow pattern?"
    ↓ Yes
trigger_skill("skill-name")
    ↓
SKILL.md content injected into context
    ↓
Agent follows workflow guidance
```

**Key**: `trigger_skill` is "consulting a manual", not "acquiring a new skill".

## Context Engineering Lesson

This experience clarified a core context engineering question:

**What should be pre-loaded vs on-demand loaded?**

| Pre-load (System Prompt) | On-demand (Skills) |
|--------------------------|-------------------|
| Core principles | Detailed workflows |
| Decision matrices | Step-by-step procedures |
| Tool usage patterns | Edge case handling |
| High-level strategy | Specific scenario guides |

**Rule of thumb**:
- If it guides *every* interaction → system prompt
- If it guides *specific situations* → skill

## System Prompt Integration

Instead of listing all skill contents, provide:
1. Available skills list with brief descriptions
2. Trigger mechanism: `trigger_skill(skill="name")`
3. Let the agent decide when to consult

```markdown
## Skills

Skills provide validated workflows for common tasks.
Before acting on a request, check if a skill matches the task.

{available_skills}

To use: `trigger_skill(skill="skill-name")`
```

## Outcome

The current implementation correctly treats skills as:
- **Modular**: Each skill is an independent SKILL.md file
- **Profile-specific**: PFC profile has PFC-related skills
- **On-demand**: Only loaded when explicitly triggered
- **Guidance-focused**: Contains workflows, not capabilities

This design achieves token efficiency while preserving access to detailed workflow knowledge when needed.
