# Long-Running Task Data Flow Pattern

**Date**: 2025-10-10
**Context**: PFC simulation tool design
**Core Insight**: Long-running tasks require different data flow patterns than short-lived operations

---

## The Problem with Return Values

Traditional function paradigm:
```python
result = execute_task()  # Wait for return value
process(result)          # Use returned data
```

This breaks down for long-running simulations:
- ❌ Blocks agent for hours waiting for return
- ❌ No visibility into progress/stability
- ❌ Return values disappear after task completes
- ❌ Large datasets can't be efficiently returned via JSON

---

## The Three-Channel Pattern

For long-running tasks, separate data flow into three channels:

### Channel 1: Real-Time Monitoring (Ephemeral)

**Purpose**: Track progress, detect issues, understand current state

**Implementation**:
- Script uses `print()` statements
- Agent queries with `pfc_check_task_status(task_id)`
- Output captured in StringIO buffer

**Example**:
```python
# In simulation script
print(f"Cycle 1000: max_vel={max_velocity:.3f}")
print(f"Cycle 2000: equilibrium_ratio={ratio:.3f}")
print(f"Cycle 3000: WARNING - large displacement detected")
```

**Agent workflow**:
```python
# Check progress periodically
status = pfc_check_task_status(task_id)
# Sees real-time print output, can detect issues early
```

**Characteristics**:
- ✅ Real-time visibility
- ✅ Lightweight (text only)
- ❌ Ephemeral (lost after task completes)
- ❌ Not for analysis (no structured data)

---

### Channel 2: Checkpoint Persistence (Complete State)

**Purpose**: Save complete simulation state for resumption or detailed inspection

**Implementation**:
- Use `itasca.command("model save 'checkpoint_name'")`
- Saves entire model state (geometry, contacts, properties)
- Agent can later load and inspect

**Example**:
```python
# In simulation script - save important states
itasca.command("model save 'initial_state'")

# Run simulation...
itasca.command("model cycle 50000")

itasca.command("model save 'settled_state'")
itasca.command("model save 'final_state'")
```

**Agent workflow**:
```python
# Later, agent can inspect saved states
# (requires loading into PFC environment)
```

**Characteristics**:
- ✅ Complete state preservation
- ✅ Can resume simulation
- ❌ Large file sizes
- ❌ Binary format (PFC-specific)

---

### Channel 3: Analysis Data Export (Structured Results)

**Purpose**: Extract specific analysis results for agent processing

**Implementation**:
- Export structured data to CSV/JSON
- Use file system as shared storage
- Agent uses standard file tools to analyze

**Example**:
```python
# In simulation script - export analysis results
import csv

# Extract ball positions
positions = [(b.pos().x(), b.pos().y(), b.pos().z())
             for b in itasca.ball.list()]

# Save to CSV
with open('/workspace/results/ball_positions.csv', 'w') as f:
    writer = csv.writer(f)
    writer.writerow(['x', 'y', 'z'])
    writer.writerows(positions)

# Export summary statistics
import json
summary = {
    'total_balls': itasca.ball.count(),
    'avg_velocity': float(itasca.ball.list().velocity().mean()),
    'kinetic_energy': calculate_ke()
}

with open('/workspace/results/summary.json', 'w') as f:
    json.dump(summary, f, indent=2)

print(f"Results saved to workspace/results/")
```

**Agent workflow**:
```python
# After task completes
status = pfc_check_task_status(task_id)
# Sees: "Results saved to workspace/results/"

# Read metadata (small, semantic)
summary = read("workspace/results/summary.json")

# For data files (CSV): Write analysis scripts, don't read directly
write("workspace/analysis/plot_positions.py", """
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('workspace/results/ball_positions.csv')
plt.scatter(df['x'], df['z'])
plt.savefig('workspace/plots/settlement.png')
print(f"Analyzed {len(df)} positions")
""")

bash("python workspace/analysis/plot_positions.py")

# Or use bash tools for quick inspection
bash("head -20 workspace/results/ball_positions.csv")
bash("wc -l workspace/results/ball_positions.csv")
```

**Characteristics**:
- ✅ Structured, portable formats
- ✅ Agent writes analysis scripts to process data
- ✅ Persistent and shareable
- ✅ Space-efficient (only relevant data)

**Important**: The `read` tool is for semantic files (code, docs), not data files. For CSV data, agent should write analysis scripts or use bash tools, not read the entire CSV into context.

---

## Architecture Principles

### 1. Never Block on Long Tasks

```python
# ❌ Anti-pattern
result = long_task()  # Agent blocked for hours

# ✅ Correct pattern
task_id = submit_long_task()
# Agent continues other work
# Later: check status and analyze results
```

### 2. Print for Visibility, Files for Analysis

```python
# ❌ Anti-pattern: Return large dataset
result = {
    'positions': [[x, y, z] for 10000 balls],  # Huge JSON
    'velocities': [...],
    'contacts': [...]
}

# ✅ Correct pattern: Print progress, file for data
print(f"Processing 10000 balls...")  # Visibility
export_to_csv('/workspace/data.csv')  # Analysis
print(f"✓ Results saved")             # Confirmation
```

### 3. Tool Usage: Semantic vs Data Files

```python
# ❌ Anti-pattern: Read tool for data analysis
positions = read("workspace/results/positions.csv")  # Wrong! This loads thousands of rows into context

# ✅ Correct pattern: Write analysis scripts
write("workspace/analysis/analyze.py", """
import pandas as pd
df = pd.read_csv('workspace/results/positions.csv')
# Perform analysis...
""")
bash("python workspace/analysis/analyze.py")

# ✅ Also correct: Bash tools for quick inspection
bash("head -20 workspace/results/positions.csv")  # Preview
bash("wc -l workspace/results/positions.csv")     # Count
```

**Rule**: The `read` tool is for **semantic files** (code, documentation, configs), not **data files** (CSV, large JSON arrays). For data processing, write analysis scripts.

### 3. Separate Ephemeral from Persistent

**Ephemeral** (print/stdout):
- Progress indicators
- Warnings and diagnostics
- Current state snapshots

**Persistent** (files):
- Analysis results
- Complete state checkpoints
- Structured datasets

### 4. Read Tool is for Semantics, Not Data

**Critical distinction**:

```python
# ✅ Read tool for semantic files
script_code = read("workspace/scripts/simulation.py")   # Code
readme = read("workspace/docs/README.md")              # Documentation
config = read("workspace/config/settings.json")        # Config

# ❌ Read tool NOT for data analysis
data = read("workspace/results/positions.csv")  # Wrong! Thousands of rows
```

**Why this matters**:
- Read tool loads content into LLM context (expensive, limited)
- Data files can be megabytes, thousands of rows
- Agent should write analysis scripts, not read data directly
- Bash tools (`head`, `wc`, `grep`) for quick inspection

**Correct data handling**:
```python
# Quick inspection
bash("head -n 20 workspace/results/data.csv")
bash("wc -l workspace/results/data.csv")

# Full analysis
write("workspace/analysis/analyze.py", """
import pandas as pd
df = pd.read_csv('workspace/results/data.csv')
# Perform complex analysis...
""")
bash("python workspace/analysis/analyze.py")
```

### 5. Design for Resumption

Long tasks may fail or need adjustment:

```python
# Good pattern: Checkpoint + Resume
if os.path.exists('workspace/checkpoint.sav'):
    itasca.command("model restore 'workspace/checkpoint.sav'")
    print("Resumed from checkpoint")
else:
    # Initialize from scratch
    setup_model()

# Run next phase
itasca.command("model cycle 50000")
itasca.command("model save 'workspace/checkpoint.sav'")
```

---

## Tool Design Implications

### Script Tool Documentation

Should emphasize:
1. ✅ Use `print()` for real-time monitoring
2. ✅ Save checkpoints with `model save`
3. ✅ Export analysis data to CSV/JSON
4. ❌ Don't rely on `result` variable for large datasets

### Status Tool Documentation

Should emphasize:
1. ✅ Check `output` field for print statements
2. ✅ Monitor progress and detect issues
3. ❌ Not for retrieving analysis data

### System Prompt Guidance

Should teach:
1. Three-channel pattern
2. When to use each channel
3. File-based result handling workflow

---

## Example Workflow: Complete Simulation

### Phase 1: Script Design

```python
# workspace/scripts/settling_simulation.py
import itasca
import csv
import json

print("=== Settling Simulation Started ===")

# Initialize
itasca.command("model new")
itasca.command("model domain extent -10 10")
print("✓ Model initialized")

# Create assembly
itasca.command("ball generate number 5000 radius 0.1")
print(f"✓ Created {itasca.ball.count()} balls")

# Save initial state
itasca.command("model save 'workspace/checkpoints/initial.sav'")
print("✓ Initial state saved")

# Set physics
itasca.command("model gravity (0, 0, -9.81)")
itasca.command("contact cmat default model linear")
print("✓ Physics configured")

# Run simulation with monitoring
for i in range(10):
    itasca.command("model cycle 5000")

    # Monitor progress
    avg_vel = itasca.ball.list().velocity().mean()
    print(f"Cycle {(i+1)*5000}: avg_velocity={avg_vel:.6f} m/s")

    if avg_vel < 0.001:
        print(f"✓ Equilibrium reached at cycle {(i+1)*5000}")
        break

# Save final state
itasca.command("model save 'workspace/checkpoints/settled.sav'")
print("✓ Final state saved")

# Export analysis data
positions = [(b.pos().x(), b.pos().y(), b.pos().z())
             for b in itasca.ball.list()]

with open('workspace/results/final_positions.csv', 'w') as f:
    writer = csv.writer(f)
    writer.writerow(['x', 'y', 'z'])
    writer.writerows(positions)

summary = {
    'total_balls': itasca.ball.count(),
    'final_avg_velocity': float(avg_vel),
    'cycles_to_equilibrium': (i+1)*5000
}

with open('workspace/results/summary.json', 'w') as f:
    json.dump(summary, f, indent=2)

print("✓ Results exported to workspace/results/")
print("=== Simulation Complete ===")

# Don't return large data - it's already saved
result = "success"
```

### Phase 2: Agent Execution

```python
# 1. Submit task
result = pfc_execute_script("workspace/scripts/settling_simulation.py")
task_id = result["data"]["task_id"]

# 2. Monitor progress (can do other work between checks)
status = pfc_check_task_status(task_id)
# Sees: "Cycle 5000: avg_velocity=0.532000 m/s"

# ... later ...
status = pfc_check_task_status(task_id)
# Sees: "✓ Equilibrium reached at cycle 25000"
# Sees: "✓ Results exported to workspace/results/"

# 3. Read metadata (after completion)
summary = read("workspace/results/summary.json")

# 4. Generate plots and analyze data files
write("workspace/analysis/plot_script.py", """
import pandas as pd
import matplotlib.pyplot as plt

# Read data file
df = pd.read_csv('workspace/results/final_positions.csv')

# Generate plot
plt.scatter(df['x'], df['z'])
plt.xlabel('X Position')
plt.ylabel('Z Position')
plt.title('Final Ball Settlement')
plt.savefig('workspace/plots/settlement_profile.png')

# Calculate statistics
print(f"Total points: {len(df)}")
print(f"Z range: {df['z'].min():.3f} to {df['z'].max():.3f}")
""")

bash("python workspace/analysis/plot_script.py")
```

---

## Benefits of This Pattern

1. **Non-blocking**: Agent not frozen during long simulations
2. **Visibility**: Real-time progress monitoring via print
3. **Persistence**: Results available after task completion
4. **Portability**: Standard file formats (CSV/JSON)
5. **Resumable**: Checkpoint-based recovery from failures
6. **Efficient**: Only relevant data exported, not entire state
7. **Tool-agnostic**: Standard file tools work on results

---

## Future Enhancements

### Streaming Output (Future)

Instead of polling with `check_task_status`, could implement:
```python
# WebSocket streaming of print output
async for line in pfc_stream_output(task_id):
    # Agent sees output in real-time
    process_progress_line(line)
```

### Structured Progress Events (Future)

Instead of parsing print strings:
```python
# In script
emit_progress(cycle=5000, velocity=0.532, status="running")

# Agent receives
{"cycle": 5000, "velocity": 0.532, "status": "running"}
```

### Result Metadata Registry (Future)

Track what files were created:
```python
# Script declares outputs
register_output("positions", "workspace/results/positions.csv")
register_output("summary", "workspace/results/summary.json")

# Agent discovers outputs
outputs = pfc_get_task_outputs(task_id)
# Returns: {
#   "positions": "workspace/results/positions.csv",
#   "summary": "workspace/results/summary.json"
# }
```

---

## Conclusion

Long-running tasks require rethinking the traditional "call and return" paradigm:

- ❌ **Synchronous blocking**: `result = task()`
- ✅ **Async with three channels**:
  - Print for monitoring
  - Files for analysis
  - Checkpoints for state

This pattern enables:
- Agent autonomy during long tasks
- Real-time visibility into progress
- Persistent, portable analysis results
- Graceful handling of failures

**Key principle**: The file system is the durable communication channel between long-running tasks and the agent.

---

**Related**: Task management tools (`pfc_check_task_status`, `pfc_list_tasks`) implement the monitoring channel. Standard file tools (`read`, `write`, `bash`) handle the analysis channel. This separation of concerns is fundamental to scalable agent architectures.
