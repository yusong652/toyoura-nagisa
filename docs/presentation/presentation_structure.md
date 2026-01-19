# Presentation Structure: Toyoura Nagisa
## 15-Minute Technical Presentation (2026-01-19)

---

## Confirmed Demos

### ✅ Demo 1: "Drop 50 particles into a box"
- **Level**: L1-L2 (Basic to Simple)
- **Starting point**: Fresh initialization
- **Demonstrates**:
  - Complete workflow from scratch
  - Documentation-driven syntax generation
  - `pfc_query_*` → `pfc_browse_*` → `pfc_execute_task` pattern
- **Duration**: ~2 minutes
- **Status**: ✅ Completed

### ✅ Demo 3: "Run this and delegate diagnostic multi-view analysis"
- **Task**: Drum mixer simulation
- **Demonstrates**:
  - SubAgent delegation (`invoke_agent`)
  - Multimodal visual analysis
  - Context isolation (SubAgent returns structured conclusions)
- **Duration**: ~3 minutes
- **Status**: ✅ Completed

---

## Demo Coverage Analysis

### What's Covered ✅
| Feature | Demo 1 | Demo 3 | Notes |
|---------|--------|--------|-------|
| Documentation Query | ✅ | - | pfc_query_*, pfc_browse_* |
| Verified Syntax | ✅ | - | Eliminates hallucination |
| Task Execution | ✅ | ✅ | pfc_execute_task |
| SubAgent Delegation | - | ✅ | invoke_agent |
| Multimodal Analysis | - | ✅ | Visual diagnostics |
| Context Isolation | - | ✅ | SubAgent memory |

### What's Missing ⚠️
| Feature | Importance | Workaround |
|---------|------------|------------|
| **Iterative Loop** | High | Mention in architecture, show in future work |
| **Autonomous Decision** | High | Demo 3 shows SubAgent autonomy partially |
| **Long-Running Monitor** | Medium | Explain with `pfc_check_task_status` in slides |
| **Parameter Adjustment** | Medium | Defer to paper experiments |

---

## Recommendation: 2 Demos vs 3 Demos

### Option A: Only 2 Demos (Recommended for time constraint) ⭐

**Pros**:
- 两个demo已经覆盖核心创新点
- 有更多时间深入讲解architecture
- 降低presentation风险（不需要赶工第三个demo）
- 可以在future work中提到迭代能力

**Cons**:
- 缺少完整的"Submit → Monitor → Analyze → Decide"循环展示
- 自主迭代能力只能口头描述

**Time allocation (15 min)**:
```
1. Introduction (2 min)
   - Hook + Problem + Contribution

2. Architecture Deep Dive (4 min) ← 增加时间
   - Documentation-Driven Workflow (1.5 min)
     - 115 commands + 1006 APIs
     - BM25 search + two-stage pattern
     - Code comparison: with vs without doc tools
   - Task Lifecycle Management (1.5 min)
     - Thread-safe execution
     - Background task + status monitoring
     - **Show code snippet of pfc_check_task_status usage**
   - SubAgent + Diagnostics (1 min)
     - Memory isolation design
     - Read-only tools vs MainAgent

3. Demo 1: Complete Workflow (2.5 min)
   - "Drop 50 particles into a box"
   - Highlight documentation queries
   - Show syntax verification

4. Demo 3: Multi-View Diagnostic (3 min)
   - "Run and delegate diagnostic analysis"
   - Show SubAgent invocation
   - Emphasize structured conclusions vs raw images

5. Experimental Design (2 min)
   - 16 tasks (L1-L5)
   - Ablation study + model comparison
   - Success metrics

6. Future Work + Conclusion (1.5 min)
   - Iterative calibration (L5 tasks) ← 提及但不演示
   - Generalization to other simulation software
   - Q&A
```

---

### Option B: Add Simplified 3rd Demo (If time permits)

**Only do this if**:
- 今天晚上能完成L5-1基础实现
- 明天能录制完成并测试

**Simplified L5-1 approach**:
- 只做2次迭代（不是3-5次）
- 使用固定调整策略: μ_new = μ + 0.1
- 预先测试确保收敛

**Risk**: 赶工可能导致demo不稳定，影响整个presentation

---

## Recommended Strategy: Option A (2 Demos)

### 关键策略：在Architecture部分补充迭代能力

**在"Task Lifecycle Management"部分加入**:

1. **展示代码片段**（非demo，而是slide上的代码）:
```python
# Iterative calibration example (from experimental tasks)
for iteration in range(max_iterations):
    # Submit task
    task_id = pfc_execute_task(friction=mu, run_in_background=True)

    # Monitor progress
    while not task_complete:
        status = pfc_check_task_status(task_id)
        # Agent sees real-time output

    # Analyze result
    angle = extract_angle_from_output()

    # Autonomous decision
    if abs(angle - target) < tolerance:
        break  # Converged
    else:
        mu = adjust_friction(mu, angle, target)  # Agent decides
```

2. **口头说明**:
> "This enables autonomous iteration. The agent submits a task, monitors its progress, analyzes results, and decides whether to continue or adjust parameters—without waiting for human approval at each step. This is exactly what our L5 experimental tasks will evaluate."

3. **视觉辅助**（diagram）:
```
Submit → Monitor → Analyze → Decide
   ↑                            ↓
   └────────── Iterate ─────────┘
```

---

## Presentation Flow (Option A - Recommended)

### Slide Deck (8 slides)

1. **Title Slide**
   - Toyoura Nagisa: LLM-Driven DEM Simulation with Context Engineering
   - Your name, affiliation, date

2. **Problem Statement**
   - DEM complexity: Scripting, parameters, debugging
   - LLM challenges: Hallucination, physics misconceptions
   - Our solution: Context Engineering

3. **Architecture Overview** (Diagram)
   - 3 components: Documentation + Lifecycle + SubAgent
   - Visual flow diagram

4. **Documentation-Driven Workflow** (Details)
   - Code comparison: with docs vs without docs
   - Two-stage Query-Browse pattern

5. **Task Lifecycle + Iterative Control** (Code + Diagram)
   - Background execution
   - Status monitoring
   - Autonomous iteration loop (code snippet)

6. **Demo Transition Slide**
   - "Two Live Demonstrations"
   - Demo 1: Documentation-driven basic workflow
   - Demo 3: SubAgent multi-view diagnostics

7. **Experimental Design**
   - 16 tasks (L1-L5 pyramid)
   - Ablation study table
   - Success metrics

8. **Conclusion + Future Work**
   - Key contributions
   - Generalization potential
   - Contact info

---

## Speaker Notes for Key Slides

### Slide 4: Documentation-Driven Workflow

**Without documentation tools (hallucination example)**:
```python
# LLM guesses syntax (WRONG)
ball.create(x=0, y=0, z=0, radius=0.5)  # No such method
model.add_balls(count=50)                # Invalid API
```

**With documentation tools (verified syntax)**:
```python
# LLM queries docs and gets verified syntax (CORRECT)
itasca.ball.create(pos=(0,0,0), radius=0.5, density=2650)
itasca.ball.create_cloud(...)  # Actual bulk generation method
```

**Narration**:
> "Without documentation tools, the LLM invents plausible-sounding but invalid syntax. With our documentation system, it queries 115 command docs and 1006 API references, retrieves verified patterns, and generates executable scripts. This is the core innovation."

---

### Slide 5: Task Lifecycle + Iterative Control

**Show the iteration code snippet + diagram**

**Narration**:
> "Our task lifecycle management enables autonomous iteration. The agent submits a simulation in the background, monitors its progress in real-time, analyzes the results, and autonomously decides the next action—whether to continue, interrupt, or restart with adjusted parameters. This eliminates the need for step-by-step human approval and enables true autonomous workflow."

**Connect to experiments**:
> "Our L5 experimental tasks, such as friction coefficient calibration, will evaluate this iterative capability quantitatively."

---

## Demo Presentation Tips

### Demo 1: "Drop 50 particles into a box"

**Setup narration**:
> "Let's see the complete workflow from initialization. I'll give the agent a simple prompt: 'Drop 50 particles into a box.'"

**During demo, highlight**:
1. First tool call: `pfc_query_python_api("ball create")`
   - "Agent doesn't know syntax, so it queries documentation"
2. Documentation response: Shows `itasca.ball.create` examples
   - "It receives verified syntax patterns"
3. Script execution: `pfc_execute_task`
   - "Generates and executes the script"
4. Result: 3D view of 50 balls in box
   - "No syntax errors, physically correct result"

**Closing**:
> "Without documentation tools, this would fail with hallucinated syntax. With our system, it works on the first try."

---

### Demo 3: "Run this and delegate diagnostic multi-view analysis"

**Setup narration**:
> "Now a more complex scenario: analyzing a rotating drum mixer. The MainAgent delegates this to a specialized PFC Diagnostic SubAgent."

**During demo, highlight**:
1. `invoke_agent` tool call with `pfc_diagnostic` profile
   - "MainAgent recognizes this needs visual analysis and delegates"
2. SubAgent captures multiple views
   - "Front view, cross-section, velocity field"
3. SubAgent returns structured report
   - "Instead of sending raw images back, it analyzes and returns conclusions"
4. MainAgent receives concise findings
   - "Segregation in radial direction, dead zone at center"

**Closing**:
> "This delegation prevents context exhaustion. The SubAgent performs deep visual exploration—up to 64 iterations—and returns only verified conclusions to the MainAgent. This is how we maintain context efficiency while enabling thorough diagnostics."

---

## Backup Plan

### If Live Demo Fails
- Switch immediately to pre-recorded video
- Don't apologize excessively
- Continue narration as planned

### If Running Over Time
**Priority cut order**:
1. Shorten Demo 1 to 1.5 min (cut waiting time)
2. Reduce Experimental Design to 1 min (show table only)
3. Shorten Introduction to 1.5 min

**Never cut**:
- Architecture explanation (core contribution)
- Demo 3 (most impressive feature)

---

## Final Checklist

### Before Tomorrow Night (Day -1)
- [ ] Review both demo recordings
- [ ] Create slide deck (8 slides)
- [ ] Write speaker notes for each slide
- [ ] Practice full presentation (aim for 14 min)
- [ ] Prepare architecture diagram
- [ ] Prepare code snippets for slides

### Presentation Day Morning
- [ ] Test PFC server connection
- [ ] Load demo videos as backup
- [ ] Test laptop display output
- [ ] Print speaker notes (backup)
- [ ] Arrive early for tech check

### During Presentation
- [ ] Start with confidence (strong opening hook)
- [ ] Watch time (have phone/watch visible)
- [ ] Engage audience (make eye contact)
- [ ] Handle questions gracefully (defer if needed)

---

## Post-Presentation Action Items

- [ ] Collect audience feedback
- [ ] Note questions for paper FAQ
- [ ] Identify which demo resonated most
- [ ] Update experimental_tasks.md if needed
- [ ] Consider adding successful demos as regression tests
