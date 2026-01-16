# Ablation Experiment Configurations

## Overview

This document defines the ablation configurations for evaluating each component's contribution to the LLM-DEM Agent system.

---

## Configuration Summary

| Config | Documentation | Lifecycle | Diagnostic | SubAgent | Profile Name |
|--------|---------------|-----------|------------|----------|--------------|
| Full System | ✓ | ✓ | ✓ | ✓ | `pfc` |
| -Doc | ✗ | ✓ | ✓ | ✓ (Explorer disabled) | `pfc_ablation_no_doc` |
| -Diagnostic | ✓ | ✓ | ✗ | ✓ (Diagnostic disabled) | `pfc_ablation_no_diagnostic` |
| -Lifecycle | ✓ | ✗ | ✓ | ✓ | `pfc_ablation_no_lifecycle` |
| Baseline | ✗ | ✗ | ✗ | ✗ | `pfc_ablation_baseline` |

---

## Detailed Tool Lists

### Full System (`pfc` profile - current)

```python
PFC_TOOLS = [
    # File operations
    "write", "read", "edit",
    # System commands
    "bash", "bash_output", "kill_shell", "glob", "grep",
    # Search and planning
    "web_search", "web_fetch", "todo_write",
    # PFC Documentation - Browse (directory listing)
    "pfc_browse_commands",      # 115 commands
    "pfc_browse_python_api",    # 1006 API modules
    "pfc_browse_reference",     # Reference materials
    # PFC Documentation - Query (detailed lookup)
    "pfc_query_python_api",     # BM25 search over Python docs
    "pfc_query_command",        # BM25 search over command docs
    # PFC Execution (script-only workflow)
    "pfc_execute_task",         # Execute Python scripts
    "pfc_check_task_status",    # Query task progress
    "pfc_list_tasks",           # List all tasks
    "pfc_interrupt_task",       # Interrupt running task
    # PFC Diagnostic (multimodal visual analysis)
    "pfc_capture_plot",         # Capture visualization
    # SubAgent delegation
    "invoke_agent",             # Delegate to pfc_explorer, pfc_diagnostic
    # Skills
    "trigger_skill",
]
```

### -Doc Ablation (`pfc_ablation_no_doc`)

**Removed**: All documentation query and browse tools

```python
PFC_ABLATION_NO_DOC_TOOLS = [
    # File operations
    "write", "read", "edit",
    # System commands
    "bash", "bash_output", "kill_shell", "glob", "grep",
    # Search and planning
    "web_search", "web_fetch", "todo_write",
    # PFC Execution (script-only workflow)
    "pfc_execute_task",
    "pfc_check_task_status",
    "pfc_list_tasks",
    "pfc_interrupt_task",
    # PFC Diagnostic
    "pfc_capture_plot",
    # SubAgent - NOTE: pfc_explorer becomes useless without docs
    "invoke_agent",  # Only pfc_diagnostic available
    "trigger_skill",
]
# Constraint: invoke_agent should only allow "pfc_diagnostic"
```

**Purpose**: Test if LLM can rely on training knowledge alone for PFC syntax.

**Expected Impact**:
- High failure rate on syntax-related tasks (L1)
- Hallucinated commands that don't exist
- Incorrect parameter names and values

### -Diagnostic Ablation (`pfc_ablation_no_diagnostic`)

**Removed**: `pfc_capture_plot` and `pfc_diagnostic` SubAgent access

```python
PFC_ABLATION_NO_DIAGNOSTIC_TOOLS = [
    # File operations
    "write", "read", "edit",
    # System commands
    "bash", "bash_output", "kill_shell", "glob", "grep",
    # Search and planning
    "web_search", "web_fetch", "todo_write",
    # PFC Documentation - Browse
    "pfc_browse_commands",
    "pfc_browse_python_api",
    "pfc_browse_reference",
    # PFC Documentation - Query
    "pfc_query_python_api",
    "pfc_query_command",
    # PFC Execution
    "pfc_execute_task",
    "pfc_check_task_status",
    "pfc_list_tasks",
    "pfc_interrupt_task",
    # SubAgent - only pfc_explorer available
    "invoke_agent",
    "trigger_skill",
]
# Constraint: invoke_agent should only allow "pfc_explorer"
```

**Purpose**: Test the value of visual analysis in simulation debugging.

**Expected Impact**:
- Reduced ability to diagnose geometric issues
- More iterations needed to identify problems from text output only
- Particularly affects L3-L5 tasks requiring result interpretation

### -Lifecycle Ablation (`pfc_ablation_no_lifecycle`)

**Changed**: Disable `run_in_background` option in `pfc_execute_task`

```python
PFC_ABLATION_NO_LIFECYCLE_TOOLS = [
    # Same as PFC_TOOLS
    # ...
]
# Runtime constraint: pfc_execute_task always runs in foreground
# max_execution_time: 60 seconds (prevent long-running blocks)
```

**Implementation Options**:

1. **Profile Setting** (Recommended):
   ```python
   ProfileConfig(
       ...
       enable_background_execution=False,  # New field
   )
   ```

2. **Tool Parameter Override**:
   - Ignore `run_in_background` parameter in tool execution
   - Add timeout to prevent long-running blocks

**Purpose**: Test the value of non-blocking task management.

**Expected Impact**:
- Timeouts on L3-L5 tasks (simulations > 60s)
- Loss of progress monitoring capability
- Agent unable to manage long-running simulations

### Baseline (`pfc_ablation_baseline`)

**Removed**: All documentation, diagnostic, and SubAgent tools

```python
PFC_ABLATION_BASELINE_TOOLS = [
    # File operations
    "write", "read", "edit",
    # System commands
    "bash", "bash_output", "kill_shell", "glob", "grep",
    # Search and planning (web only, no domain docs)
    "web_search", "web_fetch", "todo_write",
    # PFC Execution (minimal - foreground only)
    "pfc_execute_task",
    "pfc_check_task_status",
    "pfc_list_tasks",
    # No diagnostic tools
    # No SubAgent delegation
    "trigger_skill",
]
# Runtime constraint: pfc_execute_task foreground only, 60s timeout
```

**Purpose**: Establish lower bound - pure LLM coding ability with minimal PFC tooling.

**Expected Impact**:
- Baseline performance for all task levels
- High hallucination rate on PFC commands
- Unable to handle long simulations
- Limited debugging capability

---

## Implementation Plan

### Phase 1: Tool List Definitions

Add to `agent_profiles.py`:

```python
# Ablation tool lists
PFC_ABLATION_NO_DOC_TOOLS: List[str] = [...]
PFC_ABLATION_NO_DIAGNOSTIC_TOOLS: List[str] = [...]
PFC_ABLATION_NO_LIFECYCLE_TOOLS: List[str] = [...]  # Same as PFC_TOOLS
PFC_ABLATION_BASELINE_TOOLS: List[str] = [...]
```

### Phase 2: Profile Configurations

Add new profiles to `PROFILE_CONFIGS`:

```python
# Add to AgentProfile enum
class AgentProfile(Enum):
    ...
    PFC_ABLATION_NO_DOC = "pfc_ablation_no_doc"
    PFC_ABLATION_NO_DIAGNOSTIC = "pfc_ablation_no_diagnostic"
    PFC_ABLATION_NO_LIFECYCLE = "pfc_ablation_no_lifecycle"
    PFC_ABLATION_BASELINE = "pfc_ablation_baseline"
```

### Phase 3: SubAgent Access Control

Add `allowed_subagents` field to ProfileConfig:

```python
@dataclass(frozen=True)
class ProfileConfig:
    ...
    allowed_subagents: tuple = ("pfc_explorer", "pfc_diagnostic")  # Default: all
```

Configurations:
- `pfc`: `("pfc_explorer", "pfc_diagnostic")`
- `pfc_ablation_no_doc`: `("pfc_diagnostic",)` - Explorer useless without docs
- `pfc_ablation_no_diagnostic`: `("pfc_explorer",)` - No Diagnostic
- `pfc_ablation_no_lifecycle`: `("pfc_explorer", "pfc_diagnostic")` - Both available
- `pfc_ablation_baseline`: `()` - No SubAgents

### Phase 4: Lifecycle Control

Add `enable_background_execution` field:

```python
@dataclass(frozen=True)
class ProfileConfig:
    ...
    enable_background_execution: bool = True  # Default: enabled
```

Modify `pfc_execute_task` tool to check this setting.

---

## Experiment Matrix

| Task Level | Full | -Doc | -Diagnostic | -Lifecycle | Baseline |
|------------|------|------|-------------|------------|----------|
| L1 (3) | ✓ | ✓ | ✓ | ✓ | ✓ |
| L2 (3) | ✓ | ✓ | ✓ | ✓ | ✓ |
| L3 (4) | ✓ | ✓ | ✓ | ✓* | ✓* |
| L4 (3) | ✓ | ✓ | ✓ | ✗ | ✗ |
| L5 (3) | ✓ | ✓ | ✓ | ✗ | ✗ |

*L3 tasks may timeout in -Lifecycle/Baseline configurations

**Total Runs**: 16 tasks × 5 configs × 3 repeats = 240 experiments

---

## Data Collection

For each experiment run, record:

1. **Metadata**: task_id, config, model, timestamp
2. **Tool Usage**: tool call sequence, parameters, results
3. **Token Usage**: prompt tokens, completion tokens, total cost
4. **Timing**: start time, end time, total duration
5. **Outcome**: success/partial/failure, validation results
6. **Human Intervention**: count, content, timestamps

---

## Success Metrics by Configuration

| Metric | Full | -Doc | -Diagnostic | -Lifecycle | Baseline |
|--------|------|------|-------------|------------|----------|
| L1 Completion | >90% | <30% | >90% | >90% | <30% |
| L2 Completion | >80% | <20% | >80% | >80% | <20% |
| L3 Completion | >70% | <15% | >60% | <50%* | <10% |
| L4 Completion | >60% | <10% | >50% | N/A | N/A |
| L5 Completion | >50% | <10% | >40% | N/A | N/A |

*Timeouts expected

---

## Next Steps

1. [ ] Implement tool list definitions in `agent_profiles.py`
2. [ ] Add ablation profile configurations
3. [ ] Implement SubAgent access control (`allowed_subagents`)
4. [ ] Implement lifecycle control (`enable_background_execution`)
5. [ ] Create experiment runner script
6. [ ] Run pilot experiment with L2-1 task
