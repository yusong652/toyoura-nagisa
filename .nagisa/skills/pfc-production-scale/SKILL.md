---
name: pfc-production-scale
description: >
  Scale tested scripts to production: parameter expansion, progress monitoring,
  checkpoint saving. Use after test script passes and ready for full-scale run.
---

# PFC Production Scale

Patterns for scaling validated test scripts to production simulations.

---

## Prerequisites

Before scaling to production:
- Test script has passed with small parameters
- All syntax validated through test execution
- No errors in test output

---

## Scaling Checklist

1. **Scale parameters**
   ```python
   # Test:       ball generate number 10
   # Production: ball generate number 10000
   ```

2. **Add progress monitoring**
   ```python
   for i in range(cycles // checkpoint_interval):
       itasca.command(f'model cycle {checkpoint_interval}')
       print(f"[Progress] {(i+1) * checkpoint_interval} / {cycles} cycles")
       print(f"  Equilibrium ratio: {get_ratio():.2e}")
   ```

3. **Add checkpoints**
   ```python
   itasca.command(f"model save '{workspace}/checkpoints/step_{i}.sav'")
   ```

4. **Export results**
   ```python
   # CSV for large datasets
   with open(f'{workspace}/results/positions.csv', 'w') as f:
       writer = csv.writer(f)
       for ball in itasca.ball.list():
           writer.writerow([ball.id(), ball.pos_x(), ball.pos_y()])
   ```

---

## Data Flow

Production scripts output through three channels:

| Channel | Method | Access | Purpose |
|---------|--------|--------|---------|
| Real-time | `print()` | `pfc_check_task_status` | Progress monitoring |
| Checkpoint | `model save` | `model restore` | State recovery |
| Analysis | CSV/JSON | UV Python (`bash`) | Post-processing |

---

## Production Execution

**Always read script before executing**:
```python
read("{workspace_root}/scripts/production.py")
```

**Execute with background mode**:
```python
pfc_execute_task(
    entry_script="{workspace_root}/scripts/production.py",
    description="Production simulation - 10000 balls, 1M cycles",
    run_in_background=True  # Non-blocking for long runs
)
```

**Monitor progress**:
```python
pfc_check_task_status(task_id="...")
# View real-time print() output from script
```

---

## Termination Strategies

| Strategy | Command | Use Case |
|----------|---------|----------|
| Equilibrium | `model solve ratio 1e-5` | Converge to static state |
| Fixed cycles | `model cycle 100000` | Predictable duration |
| Time-based | `model solve time 10.0` | Run for simulation time |

---

## Git Snapshot Tracing

Each production run creates a git snapshot (`git_commit` in task info).

**Why this matters**:
- Current script files may differ from executed version
- Compare runs: `git diff <commit_a> <commit_b> -- script.py`
- Reproduce exact conditions by checking out the commit

**View task history**:
```python
pfc_list_tasks()
# Shows: task_id | status | description | git_commit
```
