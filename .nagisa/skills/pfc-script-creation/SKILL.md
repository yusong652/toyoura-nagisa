---
name: pfc-script-creation
description: >
  Script creation patterns: when to edit vs create, diff analysis for new scripts,
  test script templates. Use when writing new PFC scripts or adding functionality.
---

# PFC Script Creation

Patterns for creating and modifying PFC simulation scripts.

---

## Decision: Edit or Create?

**Default**: Modify existing scripts with `edit` tool.

```
Need to add/change functionality?
├── Similar script exists? → Edit existing (preserves validated syntax)
└── No similar script?     → Create new, but follow Diff Analysis below
```

---

## Diff Analysis (Required for New Scripts)

When creating a new script, you MUST:

1. **Read reference scripts first** - Find related existing scripts
2. **List inherited syntax** - Commands/APIs copied from reference (already validated)
3. **List new syntax** - Commands/APIs NOT in any reference
4. **Query unfamiliar syntax** - Before using anything not in reference:
   - Commands: `pfc_browse_commands(command="...")`
   - Python API: `pfc_browse_python_api(api="...")`
   - Unsure which? Search first with `pfc_query_command` or `pfc_query_python_api`

**Example output before writing**:
```
[Diff Analysis]
Reference: scripts/old_simulation.py

Inherited (validated):
- model new
- model large-strain on
- itasca.ball.count()

New (requires query):
- contact cmat default model linear  ← pfc_browse_commands
- ball.vel()                         ← pfc_browse_python_api
```

**Rule**: Unfamiliar syntax = query documentation first.

---

## Test Script Pattern

**Purpose**: Validate syntax at small scale before production.

```python
import itasca

# 1. Clean state
itasca.command('model new')

# 2. Required settings
itasca.command('model domain extent -1 1 -1 1 -1 1')
itasca.command('model large-strain on')

# 3. Test with small scale
itasca.command('ball generate number 10 radius 0.1')  # 10, not 1000

# 4. Verification
print(f"[OK] Created {itasca.ball.count()} balls")
```

**Execute test**:
```python
pfc_execute_task(
    entry_script=path,
    description="Test script",
    run_in_background=False,
    timeout=10000
)
```

---

## Modular Architecture (Complex Scripts)

For multi-phase simulations:

```
project/scripts/
├── main.py           ← entry_script
├── geometry.py       ← Ball/wall creation
├── material.py       ← Contact model setup
└── monitoring.py     ← Data export
```

**When to use**: Production simulations, reusable configurations, complex logic.

**When single script is fine**: Quick tests (< 50 lines), one-off scripts.
