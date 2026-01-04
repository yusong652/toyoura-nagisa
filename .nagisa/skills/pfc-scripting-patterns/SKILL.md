---
name: pfc-scripting-patterns
description: >
  PFC script organization patterns and data handling strategies.
  Use when organizing complex simulations into modules, choosing data
  output methods, or working with PFC and UV Python environments.
---

# PFC Scripting Patterns

Best practices for organizing PFC scripts and handling data flow.

---

## Modular Script Architecture

**`entry_script` is just an entry point** - complex tasks should use multiple scripts.

```
project/
├── scripts/
│   ├── main.py              ← entry_script (assembles modules)
│   ├── geometry.py          ← Validated: ball/wall creation
│   ├── material.py          ← Validated: contact model setup
│   ├── loading.py           ← Validated: boundary conditions
│   └── monitoring.py        ← Validated: data export functions
```

### Assembly Pattern

```python
# main.py - entry_script
import itasca
from geometry import create_sample
from material import setup_contacts
from loading import apply_compression
from monitoring import export_results

# Each module already validated independently
create_sample(num_balls=1000, radius=0.1)
setup_contacts(model="linear", kn=1e8)
apply_compression(strain_rate=0.01)
export_results(output_dir="results/")
```

### Benefits

- Each module validated independently before integration
- Reusable across different simulations
- Easier debugging (isolate which module failed)
- Clear responsibility separation

### When to Use

| Approach | Use When |
|----------|----------|
| **Modular** | Production simulations with multiple phases |
| **Modular** | Reusable geometry or loading configurations |
| **Modular** | Complex monitoring/export logic |
| **Single script** | Quick tests (< 50 lines) |
| **Single script** | One-off exploratory scripts |
| **Single script** | Simple parameter sweeps |

---

## Data Output Strategies

PFC scripts output data through three channels:

### Channel 1: Real-Time Monitoring (print)

```python
current_time = itasca.mech_age()  # Get simulation time
print(f"Time {current_time:.3f}s: avg_velocity={avg_vel:.3f} m/s")
print(f"Equilibrium ratio: {ratio:.2%}")
print("[OK] Checkpoint saved")
```

- **View with**: `pfc_check_task_status(task_id)`
- **Use for**: Progress tracking, issue detection

### Channel 2: Checkpoint Persistence (model save)

```python
itasca.command("model save '{workspace_root}/checkpoints/initial.sav'")
itasca.command(f"model save '{workspace_root}/checkpoints/strain_{strain:.3f}.sav'")
```

- **Preserves**: Complete simulation state
- **Use for**: Resumption, critical stages

### Channel 3: Analysis Data (file export)

```python
import csv, json

# Large datasets → CSV
with open('{workspace_root}/results/positions.csv', 'w') as f:
    writer = csv.writer(f)
    writer.writerow(['id', 'pos_x', 'pos_y', 'pos_z'])
    for ball in itasca.ball.list():
        writer.writerow([ball.id(), ball.pos_x(), ball.pos_y(), ball.pos_z()])

# Small metadata → JSON
with open('{workspace_root}/results/summary.json', 'w') as f:
    json.dump({'total_balls': itasca.ball.count()}, f)
```

- **CSV**: Large datasets, analyze with local Python
- **JSON**: Small metadata, direct reading OK

---

## Two Python Environments

| Environment | Tool | Packages | Use For |
|-------------|------|----------|---------|
| **PFC Python** | `pfc_execute_task` | `itasca` SDK + numpy/scipy (Python 3.6) | Simulation |
| **UV Workspace** | `bash` | Python 3.10+ ecosystem | Post-processing |

### Why Separate?

- **PFC Python**: Runs inside PFC process with `itasca` SDK access. Required for simulation. Supports numpy, scipy, pandas, matplotlib (Python 3.6 compatible).
- **UV Python**: Independent environment. No `itasca` SDK, but simpler to manage, doesn't require PFC running.

### Analysis Workflow

```python
# 1. PFC script exports CSV (runs in PFC Python)
pfc_execute_task(entry_script="export_data.py", ...)

# 2. Analysis script processes CSV (runs in UV Python)
bash("cd {workspace_root} && uv run python analysis/plot.py")

# 3. Missing packages? Install on-demand
bash("cd {workspace_root} && uv pip install pandas matplotlib")
```

---

## Quick Reference: Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    PFC Python Environment                    │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   print()   │    │ model save  │    │ CSV/JSON    │     │
│  │  Channel 1  │    │  Channel 2  │    │  Channel 3  │     │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘     │
└─────────┼──────────────────┼──────────────────┼─────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
   pfc_check_task      .sav files         .csv/.json
      (live)           (restore)          (analysis)
                                               │
                                               ▼
                                    ┌─────────────────────┐
                                    │  UV Python (bash)   │
                                    │  pandas, matplotlib │
                                    └─────────────────────┘
```
