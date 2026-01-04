# PFC Skills Extraction Proposal

**Date**: 2025-01-05
**Status**: Draft
**Context**: Refactor pfc_expert_prompt.md (662 lines) into modular skills

---

## Goals

1. **Reduce base prompt size**: From ~662 lines to ~150 lines (75%+ reduction)
2. **On-demand loading**: Load workflow knowledge only when needed
3. **SubAgent compatibility**: Share relevant skills with pfc_explorer and pfc_diagnostic
4. **Maintainability**: Independent skill files are easier to update

---

## Architecture Overview

```
pfc_expert_prompt.md (Slim Base ~150 lines)
├── Core Principles (must know - safety)
├── Critical Prerequisites (must know - simulation basics)
├── Tool Quick Reference (syntax cheatsheet)
├── {env} placeholder
└── {available_skills} metadata

Skills (On-demand ~100-200 lines each)
├── pfc-workflow-standard     # Full 7-step workflow
├── pfc-scripting-patterns    # Modular architecture, data output
├── pfc-doc-navigation        # Query vs Browse, Commands vs API  [SHARED]
├── pfc-subagent-guide        # When/how to use Tama and Hoshi
└── pfc-debugging             # Error handling, escalation strategy
```

---

## Skill Definitions

### 1. `pfc-workflow-standard`

**Purpose**: Complete simulation workflow from init to production

**Triggers**: "new simulation", "start project", "create PFC script", "run simulation"

**Content** (~180 lines):
- Step 0: Session Initialization
- Step 1: Query Documentation
- Step 2: Script Creation Strategy (Decision Tree, Diff Analysis)
- Step 3: Write Test Script
- Step 6: Write Production Script
- Step 7: Production Execution

**SubAgent Compatibility**: MainAgent only (SubAgents don't execute scripts)

---

### 2. `pfc-scripting-patterns`

**Purpose**: Script organization and data handling patterns

**Triggers**: "organize scripts", "export data", "modular", "post-processing"

**Content** (~100 lines):
- Modular Script Architecture (entry_script pattern)
- Data Output Strategies (3 channels)
- Two Python Environments (PFC vs UV)
- Stateful Execution model

**SubAgent Compatibility**: MainAgent only

---

### 3. `pfc-doc-navigation` [SHARED]

**Purpose**: How to effectively search PFC documentation

**Triggers**: "find command", "search documentation", "browse API", "query PFC"

**Content** (~120 lines):
- Query vs Browse tools decision tree
- Commands vs Python API fundamental division
- Search strategy priority order
- High-level vs low-level alternatives

**SubAgent Compatibility**:
- MainAgent: Yes
- pfc_explorer: Yes (core competency)
- pfc_diagnostic: Partial (for reference lookup)

**Implementation Note**: This skill content is already embedded in `pfc_explorer.md`. For MainAgent, load via skill. For pfc_explorer, keep inline (it's their core expertise).

---

### 4. `pfc-subagent-guide`

**Purpose**: When and how to delegate to SubAgents

**Triggers**: "delegate", "explore documentation", "visual diagnosis", "use Tama", "use Hoshi"

**Content** (~100 lines):
- Tama (pfc_explorer): Strengths, when to delegate, usage pattern
- Hoshi (pfc_diagnostic): Strengths, when to delegate, usage pattern
- Prompt tips for each SubAgent

**SubAgent Compatibility**: MainAgent only (SubAgents don't invoke SubAgents)

---

### 5. `pfc-debugging`

**Purpose**: Error handling and troubleshooting workflow

**Triggers**: "error", "failed", "debug", "troubleshoot", "fix script"

**Content** (~80 lines):
- Step 4: Handle Errors with Documentation
- Step 5: Error Escalation Strategy (mandatory order)
- Common error patterns and fixes

**SubAgent Compatibility**:
- MainAgent: Yes
- pfc_explorer: Partial (error context helps search)

---

## Slim Base Prompt Design (~150 lines)

```markdown
# PFC Simulation Expert System Prompt

You are **Nagisa Toyoura (豊浦凪沙)**, a PFC simulation expert.

---

## Core Principles

1. **Browse documentation first** - ALWAYS before new commands
2. **Test scripts validate** - Small scale, quick feedback
3. **Production scripts scale** - Tested workflows only
4. **Errors trigger browsing** - Documentation → Web → User
5. **State persists** - Use `model new` for clean state
6. **Script is context** - Git snapshots track execution versions
7. **Read before execute** - Always examine scripts first

---

## Critical Prerequisites

[Keep full content - safety critical]

---

## Environment

**Working directory**: `{workspace_root}`

{env}

**Path format**: Always use absolute paths with `{workspace_root}` prefix.

---

## Tool Quick Reference

### Documentation
- `pfc_query_command(query="...")` / `pfc_query_python_api(query="...")` - Search
- `pfc_browse_commands(command="...")` / `pfc_browse_python_api(api="...")` - Navigate
- `pfc_browse_reference(topic="...")` - Contact models, range elements

### Execution
- `pfc_execute_task(entry_script, description, run_in_background, timeout)`
- `pfc_check_task_status(task_id)` / `pfc_list_tasks()` / `pfc_interrupt_task(task_id)`

### Diagnostic
- `pfc_capture_plot(...)` - Visual diagnostic (non-blocking)

### SubAgents
- `invoke_agent(subagent_type="pfc_explorer")` - Documentation exploration
- `invoke_agent(subagent_type="pfc_diagnostic")` - Visual diagnosis

---

## Available Skills

Use `trigger_skill(skill="skill-name")` to load specialized workflow instructions.

{available_skills}
```

---

## SubAgent Compatibility Matrix

| Skill | MainAgent | pfc_explorer | pfc_diagnostic |
|-------|-----------|--------------|----------------|
| `pfc-workflow-standard` | ✅ | ❌ | ❌ |
| `pfc-scripting-patterns` | ✅ | ❌ | ❌ |
| `pfc-doc-navigation` | ✅ | ✅ (inline) | ⚠️ (optional) |
| `pfc-subagent-guide` | ✅ | ❌ | ❌ |
| `pfc-debugging` | ✅ | ⚠️ (context) | ❌ |

**Legend**: ✅ Full support | ⚠️ Partial/optional | ❌ Not applicable

---

## Implementation Strategy

### Phase 1: Create Skills (No Breaking Changes)

1. Create skill files in `.claude/skills/` or project skills directory
2. Test each skill independently
3. Verify skill triggers work correctly

### Phase 2: Slim Down Base Prompt

1. Create slim `pfc_expert_prompt_slim.md`
2. A/B test: slim + skills vs original monolithic
3. Measure token savings and task success rate

### Phase 3: SubAgent Integration

1. Update `pfc_explorer.md` to reference shared skills
2. Consider if `pfc-doc-navigation` should be a shared resource file

---

## Token Budget Estimation

| Component | Current | After Skills |
|-----------|---------|--------------|
| Base Prompt | ~5000 tokens | ~1200 tokens |
| Skills (avg) | N/A | ~800 tokens each |
| Typical Task | ~5000 tokens | ~2000-2800 tokens |

**Savings**: 40-60% for typical tasks (only relevant skills loaded)

---

## Open Questions

1. **Skill Storage Location**: `.claude/skills/` vs `packages/backend/skills/`?
2. **Shared Resources**: Should `pfc-doc-navigation` be a skill or shared reference file?
3. **SubAgent Skills**: Should SubAgents also use `trigger_skill` or keep inline?
4. **Gradual Rollout**: Test with one skill first or all at once?

---

## Next Steps

- [ ] Decide on skill storage location
- [ ] Create first skill (`pfc-workflow-standard`) as POC
- [ ] Test skill triggering with real PFC tasks
- [ ] Iterate based on testing results
- [ ] Document skill authoring guidelines for future expansion
