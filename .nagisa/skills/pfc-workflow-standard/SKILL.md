---
name: pfc-workflow-standard
description: >
  Complete 7-step PFC simulation workflow from initialization to production.
  Use when starting a new simulation, creating PFC scripts, or need guidance
  on the test-validate-production cycle.
---

# PFC Simulation Workflow

Complete workflow for developing and executing PFC simulations.

```
Step 0: Init → Step 1: Query Docs → Step 2: Script Strategy → Step 3: Test → Step 4-5: Fix → Step 6: Production → Step 7: Execute
```

---

## Step 0: Session Initialization (First Action)

Check workspace and PFC state before starting work:

```python
bash("cd {workspace_root} && git status && git log --oneline -5")
pfc_list_tasks()
```

**Decisions**:
- No git → `git init && git add -A && git commit -m 'Init'`
- Has `.sav` files → Ask user: "Found checkpoint X.sav, restore or fresh start?"
- Has running/failed tasks → Report status, consider resuming or learning from history

---

## Step 1: Query Documentation

**When to query**: First-time commands, errors, parameter uncertainty, new features

Per Core Principle #1: Browse documentation BEFORE using new commands.

---

## Step 2: Script Creation Strategy (CRITICAL)

**Default behavior**: Modify existing scripts using `edit` tool, NOT create new scripts with `write`.

### Decision Tree

```
Need to add/change functionality?
├── Existing script with similar purpose exists?
│   ├── YES → Use `edit` to modify existing script
│   │         (preserves all dependencies and validated syntax)
│   └── NO  → Create new script, but MUST follow Diff Analysis below
```

### When Creating New Scripts: Mandatory Diff Analysis

If you must create a new script (no suitable existing script), you MUST:

1. **Read reference scripts first**: `read` all related existing scripts
2. **List inherited commands**: Explicitly list which commands you're copying from reference
3. **List new commands**: Explicitly list NEW commands not in any reference script
4. **Query new commands**: Every new command MUST be queried with `pfc_browse_commands` before use
5. **Verify dependencies**: Check that all prerequisite commands are included

**Example output before writing new script**:
```
[Diff Analysis]
Reference: scripts/old_simulation.py

Inherited (validated):
- model new
- model large-strain on  ← Critical dependency
- ball generate number 100 radius 0.1

New (requires query):
- contact cmat default model linear  ← MUST query pfc_browse_commands first

Missing check:
- Does new script need 'model deterministic on'? → Check reference
```

**Key rule**: New syntax NOT in reference scripts = MUST query documentation first. Never assume.

---

## Step 3: Write Test Script

**Purpose**: Validate command syntax with small-scale test

**Pattern**: Import itasca → Use `itasca.command()` for PFC commands → Add verification prints

**Example**:
```python
import itasca

# Critical Prerequisites
itasca.command('model new')
itasca.command('model domain extent -1 1 -1 1 -1 1')
itasca.command('model large-strain on')

# Test command with small scale
itasca.command('ball generate number 10 radius 0.1')
print(f"[OK] Created {itasca.ball.count()} balls")
```

**Execute**:
```python
pfc_execute_task(
    entry_script=test_path,
    description="Test script",
    run_in_background=False,
    timeout=10000
)
```

---

## Step 4: Handle Errors with Documentation

**Error resolution pattern**:

```
Test script fails with error
   ↓
Browse full documentation: pfc_browse_commands(command="problematic command")
   ↓
Check Python Usage section for correct syntax
   ↓
Update test script with corrected command
   ↓
Re-run test
```

**Example**:

```python
# Error: "ball generate: unknown parameter 'count'"

# Step 1: Browse full documentation
pfc_browse_commands(command="ball generate")
# → Shows: Python Usage: itasca.command('ball generate number 100 radius 0.1')

# Step 2: Fix test script
itasca.command('ball generate number 100 radius 0.1')  # Use 'number' not 'count'

# Step 3: Re-test
pfc_execute_task(entry_script=..., description="Re-test", run_in_background=False)
```

---

## Step 5: Error Escalation Strategy (MANDATORY ORDER)

When test script fails, follow this EXACT order:

```
1. Browse PFC documentation: pfc_browse_commands(command="failed command")
   → Check full syntax and Python Usage examples
   → Verify parameter names

2. If command unclear: Search first, then browse
   pfc_query_command(query="keyword") → pfc_browse_commands(command="found path")

3. If Python SDK alternative exists: pfc_browse_python_api(api="itasca.ball.create")
   → Check if direct Python method available

4. If still unclear: Use web_search("PFC itasca ball generate error")
   → Search for community solutions

5. If all fail: Ask user for guidance
   → Explain what you tried
   → Show documentation you found
```

**Never skip steps in this escalation chain.**

---

## Step 6: Write Production Script

**After test passes**, scale up with same commands but larger parameters.

**Key elements**:
- Scale parameters (10 balls → 1000 balls)
- Add monitoring loop with print() for progress
- Save checkpoints with `model save`
- Export data to CSV/JSON

**Structure**: Initialize → Create assembly → Set properties → Run cycles with monitoring → Save state → Export results

---

## Step 7: Production Execution

```python
# 1. Always read script before executing
read("{workspace_root}/scripts/production_simulation.py")

# 2. Execute (run_in_background=True for long runs)
pfc_execute_task(
    entry_script="{workspace_root}/scripts/production_simulation.py",
    description="Production simulation",
    run_in_background=True
)

# 3. Monitor with pfc_check_task_status(task_id)
```

**Termination strategies**:
- **Equilibrium**: `model solve ratio 1e-5` - built-in, stops when converged
- **Fixed cycles**: `model cycle 10000` - predictable duration
- **Time-based**: `model solve time 10.0` - run for specified time

---

## Script is Context: Git Snapshot Tracing

Every `pfc_execute_task` creates a **git snapshot** (`git_commit`) of the workspace.

**Implications**:
- Current script files may differ from what was executed
- Use `git_commit` to trace exact code version for any task
- Compare successful vs failed runs by checking their `git_commit` snapshots

**Learning from task history**:
```
pfc_list_tasks()
→ Shows: task_id | status | description | git_commit

If you see similar tasks:
- Task A (success): "Ball settling with 1000 balls" | git_commit: abc123
- Task B (failed):  "Ball settling with 2000 balls" | git_commit: def456

→ Compare scripts: git diff abc123 def456 -- scripts/settling.py
```
