# Paper: LLM-Driven DEM Simulation Agent

## Overview

This directory contains all materials for the academic paper on toyoura-nagisa's LLM-driven discrete element simulation capabilities.

**Target Journal**: Computers and Geotechnics / Granular Matter

**Core Contribution**: Context Engineering methodology for eliminating LLM hallucination in professional scientific computing

---

## Document Structure

```
docs/paper/
├── README.md                    # This file - overall planning
├── experimental_tasks.md        # Detailed task design (L1-L5, 16 tasks)
├── ablation_config.md          # [TODO] Ablation experiment configurations
├── todos/                      # Daily progress tracking
│   └── todo_YYYY-MM-DD.md      # Daily todo files
├── results/                    # [TODO] Experiment results and data
└── drafts/                     # [TODO] Paper drafts
```

---

## Paper Structure

### 1. Introduction
- DEM simulation complexity (scripting, parameter tuning, result interpretation)
- LLM challenges in professional domains: hallucination, lack of domain knowledge
- Our contribution: Context Engineering + AI-DEM integration architecture

### 2. Related Work
- LLM for Scientific Computing (code generation, experiment automation)
- AI-assisted DEM (limitations of existing work)
- Context Engineering vs RAG vs Fine-tuning

### 3. System Architecture
- **Documentation-Driven Workflow** (core innovation)
  - 115 command docs + 1006 Python API docs
  - BM25 search preventing hallucination
  - Two-stage Query-Browse pattern
- **Task Lifecycle Management**
  - Thread-safe main thread execution
  - Non-blocking long-running task management
  - Real-time progress visibility
- **SubAgent + Multimodal Diagnostics**
  - PFC Explorer: documentation validation
  - PFC Diagnostic: visual analysis

### 4. Methodology: Context Engineering for DEM
- Documentation system design (Command + Python API + References)
- BM25 vs Neural Search selection rationale
- Two-stage Query-Browse pattern details

### 5. Experimental Design
See [experimental_tasks.md](./experimental_tasks.md) for detailed task definitions.

**Experiment Types**:
1. **Ablation Study**: -Doc, -Lifecycle, -Diagnostic configurations
2. **Model Comparison**: GPT-4o, Claude, Gemini, Qwen (large/small)
3. **Complexity Gradient**: L1-L5 task levels (16 tasks total)
4. **Expert Evaluation**: 3-5 DEM experts qualitative assessment

**Success Metrics**:
| Metric | Definition | Weight |
|--------|------------|--------|
| Completion Rate | Task reaches expected end state | Required |
| Script Validity | Generated script executes without syntax error | High |
| Physical Validity | Results match physical expectations | High |
| Iteration Count | Human-agent interaction rounds needed | Medium |
| Autonomy Score | Percentage completed without human intervention | Medium |

### 6. Results & Analysis
[To be completed after experiments]

### 7. Discussion
- Limitations
- Generalization to other professional domains

### 8. Conclusion

---

## Key Innovation Points

### 1. Context Engineering for Scientific Computing
- First systematic application of context engineering to DEM domain
- Proves documentation-driven approach superior to direct prompting

### 2. AI-DEM Integration Architecture
- Solves PFC SDK main thread dependency challenge
- Implements non-blocking long simulation management

### 3. Multimodal Diagnostic Loop
- First integration of visual analysis into DEM simulation debugging
- SubAgent design decouples deep analysis from main task

---

## Ablation Experiment Design

| Config | Documentation | Lifecycle | Diagnostic | Implementation |
|--------|---------------|-----------|------------|----------------|
| Full System | ✓ | ✓ | ✓ | Default profile |
| -Doc | ✗ | ✓ | ✓ | Remove pfc_query/browse tools |
| -Lifecycle | ✓ | ✗ | ✓ | Disable background execution |
| -Diagnostic | ✓ | ✓ | ✗ | Remove pfc_capture_plot + Diagnostic SubAgent |
| Baseline | ✗ | ✗ | ✗ | Minimal tools only |

---

## Model Comparison Plan

| Model | Type | Vision | Expected Role |
|-------|------|--------|---------------|
| GPT-4o | Commercial | ✓ | High baseline |
| Claude Sonnet | Commercial | ✓ | High baseline |
| Gemini Pro | Commercial | ✓ | High baseline |
| GPT-4o-mini | Lightweight | ✓ | Cost-effectiveness |
| Qwen2.5-72B | Open-source large | ✓ | Open-source feasibility |
| Qwen2.5-7B | Open-source small | ✗ | Lower bound test |

**Key Comparisons**:
- Vision model vs text-only (control: disable pfc_capture_plot)
- Large model vs small model (verify if method compensates capability gap)

---

## Experimental Protocol

1. **Fresh session** for each task (no memory carryover)
2. **Record all data**:
   - Task ID, model, configuration
   - LLM call count, token consumption
   - Tool call sequence and results
   - Final status (success/failure/partial)
   - Execution time
   - Human intervention count and content

3. **Timeout limits**: L1=2min, L2=5min, L3=15min, L4=30min, L5=60min/iteration

4. **Success classification**:
   - **Full Success**: All validation criteria met autonomously
   - **Partial Success**: Completed with human intervention
   - **Failure**: Not completed or physically incorrect

---

## Persuasion Strategy for Traditional Experts

1. **Reproducibility**: All experiment scripts and configs open-sourced
2. **Physical Validation**: Results conform to known physical laws
3. **Expert Endorsement**: User study ratings from domain experts
4. **Cost Analysis**: Time comparison with traditional workflow

---

## Timeline & Next Steps

### Phase 1: Experiment Preparation
- [x] Design L1-L5 task prompts (16 tasks)
- [ ] Prepare ablation configurations in agent_profiles
- [ ] Configure multi-model test environment

### Phase 2: Experiment Execution
- [ ] Run ablation experiments (config × task × 3 repeats)
- [ ] Run model comparison experiments
- [ ] Conduct expert evaluation

### Phase 3: Paper Writing
- [ ] Analyze experiment data
- [ ] Write first draft
- [ ] Iterate and refine

---

## Open Questions

1. **Task language**: English (confirmed)
2. **Expert evaluation**: Need to identify available domain experts
3. **Open-source timing**: Before or after publication?
4. **Submission deadline**: TBD
