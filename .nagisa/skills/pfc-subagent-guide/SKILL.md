---
name: pfc-subagent-guide
description: >
  Guide for delegating tasks to PFC SubAgents (Tama and Hoshi).
  Use when deciding whether to delegate documentation exploration or
  visual diagnosis, or when composing prompts for SubAgents.
---

# PFC SubAgent Delegation Guide

When and how to delegate specialized tasks to SubAgents.

---

## Overview

| SubAgent | Name | Specialty | Key Capability |
|----------|------|-----------|----------------|
| `pfc_explorer` | Tama | Documentation exploration | Deep multi-step searches |
| `pfc_diagnostic` | Hoshi | Visual diagnosis | Multimodal image analysis |

**Core benefit**: SubAgents have dedicated context windows - their exploration doesn't consume your context budget.

---

## Tama (PFC Explorer)

**Invoke**: `invoke_agent(subagent_type="pfc_explorer")`

### Strengths

- **Dedicated context window**: Exploration doesn't consume your context budget
- **Deep multi-step searches**: Can explore hierarchies, try alternatives, cross-reference
- **Domain knowledge**: Understands CMAT, property inheritance, high-level vs low-level approaches
- **Autonomous exploration**: Explores boundaries, tries alternative keywords, reports ALL options

### When to Delegate

- Open-ended exploration: "What commands are available for X?"
- Feature boundary discovery: "Can PFC do cylindrical confining pressure?"
- Multiple alternatives needed: "Find all ways to control boundary conditions"
- Documentation exploration requires >3 consecutive browse calls

### When NOT to Delegate

- Single known query: `pfc_browse_commands(command="ball generate")` - do it yourself
- You already know the exact command path
- Quick syntax lookup

### Usage Pattern

```python
invoke_agent(
    subagent_type="pfc_explorer",
    description="Explore servo commands",  # Short 3-5 word label
    prompt="""
Find all available servo control commands in PFC documentation.
For each command, provide:
1. Full command path and syntax
2. Python usage example
3. Limitations or constraints

If servo commands are insufficient for cylindrical boundary control,
explore alternative approaches (wall vertex, manual force control).

Report ALL relevant options with pros/cons.
    """
)
```

### Prompt Tips

- Be specific about what information to return (syntax, examples, limitations)
- Request alternatives if primary approach may be insufficient
- SubAgent returns once → your prompt must be self-contained

---

## Hoshi (PFC Diagnostic)

**Invoke**: `invoke_agent(subagent_type="pfc_diagnostic")`

### Strengths

- **Multimodal analysis**: Captures and analyzes plot images using vision capabilities
- **Multi-perspective diagnosis**: Multiple angles, cut planes, color-by modes
- **Task output correlation**: Reviews executed task status for numerical context
- **Structured reports**: Returns diagnosis with confidence level and recommendations

### When to Delegate

- Visual inspection of simulation state (geometry, stress, contacts)
- Diagnosing unexpected behavior ("particles are clustering")
- Verifying simulation correctness before production runs
- Comparing visual patterns across simulation stages

### When NOT to Delegate

- Quick single capture: use `pfc_capture_plot` + `read` yourself
- You need to execute scripts (diagnostic SubAgent cannot execute tasks)
- Simple geometry check with known view angle

### Usage Pattern

```python
invoke_agent(
    subagent_type="pfc_diagnostic",
    description="Diagnose particle settling",
    prompt="""
Diagnose the current simulation state after gravity settling.

Existing captures to analyze:
- {workspace_root}/results/plots/settling_overview.png

Check for:
1. Particle distribution uniformity
2. Wall penetration issues
3. Contact force distribution

Save new captures to: {workspace_root}/diagnostic/
    """
)
```

### Prompt Tips

- Describe the problem context: what you observed, what you suspect, what needs investigation
- Include absolute paths to existing images if available
- Specify output directory for new captures
- State what aspects to focus on

---

## Decision Matrix

| Situation | Action |
|-----------|--------|
| Know exact command, need syntax | Do it yourself: `pfc_browse_commands()` |
| Open-ended "what's available?" | Delegate to Tama |
| Need >3 doc searches | Delegate to Tama |
| Quick visual check, known angle | Do it yourself: `pfc_capture_plot()` + `read()` |
| Complex visual diagnosis | Delegate to Hoshi |
| Need to execute scripts | Do it yourself (SubAgents are read-only) |
