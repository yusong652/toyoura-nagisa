---
name: pfc-error-resolution
description: >
  Error diagnosis and resolution patterns for PFC script failures.
  Use when script execution fails, encounters syntax errors, or produces unexpected results.
---

# PFC Error Resolution

Systematic approach to diagnosing and fixing PFC script errors.

---

## Resolution Loop

```
Script fails with error
       ↓
Check task history for similar cases
       ↓
Browse documentation for problematic syntax
       ↓
Update script with corrected syntax
       ↓
Re-run test
```

---

## Learn from Task History

Every `pfc_execute_task` creates a git snapshot. Use this to learn from past successes and failures.

**Check similar tasks**:
```python
pfc_list_tasks()
# Look for: same entry_script, similar description, or related workflow
```

**Compare versions** (when same script has success and failure):
```
Task A (success): "Ball settling" | git_commit: abc123
Task B (failed):  "Ball settling" | git_commit: def456

# Compare what changed:
bash("git diff abc123 def456 -- scripts/settling.py")
```

**Leverage successful patterns**:
- Find a successful task with similar goal
- Checkout that version to see working code
- Identify what the current script is missing

---

## Escalation Order

1. **Check task history** (as above)

2. **Browse PFC documentation**
   ```python
   pfc_browse_commands(command="failed command")
   pfc_browse_python_api(api="failed.method")
   ```

3. **Search if path unclear**
   ```python
   pfc_query_command(query="keyword")
   pfc_query_python_api(query="keyword")
   ```

4. **Web search** (if documentation insufficient)
   ```python
   web_search("PFC itasca [error message]")
   ```

5. **Ask user** (after exhausting above)

---

## Common Error Patterns

### "Unknown parameter"
```python
# Error: "unknown parameter 'count'"
# Fix: Check exact parameter name
pfc_browse_commands(command="ball generate")
# → 'number' not 'count'
```

### "Command not found" for data access
```python
# Error: "ball get velocity" - no such command
# Insight: Commands CREATE/MODIFY, Python API READS
for ball in itasca.ball.list():
    vel = ball.vel()  # Use Python API
```

### Missing prerequisite
```python
# Check initialization order:
# model new → domain → large-strain → cmat → geometry → density
```

### State pollution
```python
# Unexpected objects from previous run
itasca.command('model new')  # Clean state first
```

---

## After Fixing

Re-run to verify:
```python
pfc_execute_task(
    entry_script=path,
    description="Re-test after fix",
    run_in_background=False
)
```

The new execution creates another git snapshot—useful for future debugging.
