# Presentation Planning: Toyoura Nagisa
## 15-Minute Technical Presentation

**Date**: 2026-01-19 (后天)
**Duration**: 15 minutes
**Audience**: Technical/Academic
**Goal**: Demonstrate LLM-driven DEM simulation with context engineering methodology

---

## Demo Strategy Analysis

### Current Status
✅ **Completed Demos**:
1. **Documentation Query + Basic Syntax** (L1 level)
   - Demonstrates: Documentation-driven workflow eliminates hallucination
   - Shows: `pfc_query_*` → `pfc_browse_*` → `pfc_execute_task` pattern
   - Duration: ~2 minutes
   - Complexity: Low, easy to explain

2. **Multimodal Diagnostic Analysis** (Drum Mixer scenario)
   - Demonstrates: SubAgent delegation + visual analysis
   - Shows: `invoke_agent` with PFC Diagnostic SubAgent
   - Duration: ~3 minutes
   - Complexity: Medium, showcases advanced features

### Recommended 3rd Demo

**选择: L5-1 Friction Coefficient Calibration** ⭐

**理由**:
1. **体现核心创新**: 展示完整的 "Submit → Monitor → Analyze → Decide" 循环
2. **展示自主性**: Agent无需人工干预即可完成迭代优化
3. **技术难度适中**:
   - 基于已完成的 L3-2 (Angle of Repose) 基础
   - 添加迭代逻辑和参数调整策略
4. **视觉效果好**: 每次迭代的休止角变化可视化
5. **时间可控**: 可以提前运行并录制,或使用已完成的运行结果

**任务描述** (from experimental_tasks.md):
> Calibrate friction coefficient to match target angle of repose of 30°:
> 1. Start with μ = 0.3
> 2. Run angle of repose test
> 3. Measure resulting angle
> 4. Adjust friction based on difference
> 5. Iterate until measured angle within ±2° of target

**预期展示要点**:
- Iteration 1: μ=0.3 → angle=25° → increase friction
- Iteration 2: μ=0.5 → angle=32° → decrease friction
- Iteration 3: μ=0.45 → angle=29.5° → converged ✓
- 展示 `pfc_check_task_status` 实时监控
- 展示 Agent 自主决策逻辑

**准备工作**:
- [ ] 完成 L5-1 任务实现和测试
- [ ] 录制完整迭代过程(或准备实时演示)
- [ ] 准备每次迭代的可视化图片
- [ ] 测试整个流程耗时(目标<5分钟展示)

**备选方案**: 如果 L5-1 时间来不及,可以选择 **L3-4 Undrained Triaxial Test**
- 优势: 展示数据分析能力,从数值输出中推理物理行为
- 劣势: 迭代性不如 L5-1 明显,更像传统simulation

---

## Presentation Structure (15 min)

### 1. Introduction (2 min)

**Opening Hook** (30s):
> "Discrete Element Method simulations require expert knowledge: boundary conditions, material parameters, result interpretation. Large Language Models can generate code, but hallucinate syntax and misunderstand physics. We present Toyoura Nagisa: an LLM agent that navigates DEM documentation, writes verified scripts, and iterates autonomously."

**Problem Statement** (1min):
- DEM simulation complexity: scripting (FISH/Python), parameter calibration, debugging
- LLM challenges in professional domains:
  - Syntax hallucination (invented commands)
  - Physical misconceptions (wrong boundary conditions)
  - Lack of iterative capability

**Our Contribution** (30s):
- Context Engineering methodology for scientific computing
- AI-DEM integration architecture with task lifecycle management
- Autonomous iteration with multimodal diagnostics

---

### 2. System Architecture (3 min)

**Core Components** (Visual: Architecture diagram):

1. **Documentation-Driven Workflow** (1min)
   - 115 command docs + 1006 Python API docs
   - BM25 search: `pfc_query_*` (fast keyword match) → `pfc_browse_*` (syntax verification)
   - Pattern: Query for relevant paths → Browse for exact syntax → Execute verified script
   - **Key Innovation**: Forces LLM to check documentation before writing code

2. **Task Lifecycle Management** (1min)
   - Main thread executor: Queue-based execution (PFC SDK requirement)
   - Non-blocking task tracking: `pfc_execute_task` (background) → `pfc_check_task_status`
   - Real-time progress visibility: Output capture during long simulations

3. **SubAgent + Multimodal Diagnostics** (1min)
   - PFC Explorer: Documentation validation (20 iterations max, read-only)
   - PFC Diagnostic: Visual analysis across angles/quantities (64 iterations max)
   - Memory isolation: SubAgent todos in-memory, MainAgent todos persistent
   - **Key Innovation**: Delegates deep exploration without exhausting main context

---

### 3. Live Demonstrations (8 min)

#### Demo 1: Documentation-Driven Basic Syntax (2 min)

**Task**: Create 50 balls in a box (L1 level)

**Narration**:
1. "User prompt: 'Create 50 balls randomly distributed in a 1m × 1m × 2m box'"
2. "Agent queries documentation: `pfc_query_python_api('ball create')`"
3. "Retrieves verified syntax: `itasca.ball.create(...)`"
4. "Executes script: 50 balls generated, no syntax errors"
5. **Key Point**: "Without documentation tools, LLM would hallucinate `ball.create()` or `model.add_balls()`—invalid PFC syntax"

**Visual**:
- Screen recording: Tool calls → Documentation results → Script execution → 3D view of balls

---

#### Demo 2: Iterative Calibration Workflow (3 min)

**Task**: Calibrate friction coefficient to match angle of repose 30° (L5-1)

**Narration**:
1. "User prompt: 'Calibrate friction to achieve 30° angle of repose'"
2. "Iteration 1: Agent starts with μ=0.3"
   - Runs simulation in background: `pfc_execute_task(run_in_background=True)`
   - Monitors progress: `pfc_check_task_status()`
   - Measures angle: 25° (too low)
3. "Iteration 2: Agent increases friction to μ=0.5"
   - Measures angle: 32° (too high)
4. "Iteration 3: Agent adjusts to μ=0.45"
   - Measures angle: 29.5° → Converged ✓
5. **Key Point**: "Agent autonomously decided when to interrupt, when to restart, and how to adjust parameters—no step-by-step human approval needed"

**Visual**:
- Split screen: Left (chat logs + tool calls), Right (angle of repose evolution)
- Show task status updates during simulation
- Highlight autonomous decision points

---

#### Demo 3: Multimodal Diagnostic Analysis (3 min)

**Task**: Analyze drum mixer simulation using PFC Diagnostic SubAgent

**Narration**:
1. "User prompt: 'Analyze mixing efficiency in the rotating drum'"
2. "MainAgent delegates to PFC Diagnostic SubAgent"
3. "SubAgent captures multi-view plots:"
   - Front view: Particle distribution
   - Cross-section: Mixing layers
   - Velocity field: Flow pattern
4. "SubAgent analyzes visual data and returns structured findings:"
   - "Mixing pattern: Segregation observed in radial direction"
   - "Velocity anomaly: Dead zone at drum center"
5. **Key Point**: "SubAgent isolates visual exploration—MainAgent receives concise conclusions, not raw images. This prevents context exhaustion."

**Visual**:
- Show invoke_agent tool call
- Display captured plots (multi-angle views)
- Show SubAgent's structured report returned to MainAgent

---

### 4. Key Results Preview (1.5 min)

**Experimental Design**:
- 16 tasks across 5 complexity levels (L1-L5)
- Ablation study: -Doc, -Lifecycle, -Diagnostic configurations
- Model comparison: GPT-4o, Claude, Gemini, Qwen (large/small)

**Preliminary Observations** (if available):
- Documentation tools reduce syntax errors by X%
- Task lifecycle management enables autonomous iteration
- SubAgent delegation maintains context efficiency

**Success Metrics**:
- Completion Rate (task reaches expected end state)
- Script Validity (no syntax errors)
- Physical Validity (results match physics)
- Iteration Count (efficiency)
- Autonomy Score (% completed without human intervention)

---

### 5. Conclusion (0.5 min)

**Key Takeaways**:
1. Context Engineering eliminates LLM hallucination in professional domains
2. Documentation-driven workflow > Direct prompting
3. Autonomous iteration with multimodal diagnostics enables real-world DEM workflows

**Future Work**:
- Extend to other simulation software (FLAC, COMSOL)
- Multi-agent collaboration for complex projects
- Expert user study and deployment

**Q&A Ready**

---

## Time Allocation Summary

| Section | Duration | Key Activities |
|---------|----------|----------------|
| Introduction | 2 min | Hook, problem, contribution |
| Architecture | 3 min | 3 core components explanation |
| Demo 1 | 2 min | Documentation-driven syntax |
| Demo 2 | 3 min | Iterative calibration (L5-1) |
| Demo 3 | 3 min | Multimodal diagnostics |
| Results Preview | 1.5 min | Experiment design, metrics |
| Conclusion | 0.5 min | Takeaways, future work |
| **Total** | **15 min** | |

---

## Presentation Checklist

### Pre-Presentation
- [ ] Complete L5-1 (Friction Calibration) implementation
- [ ] Record all 3 demos (backup if live demo fails)
- [ ] Prepare architecture diagram (Documentation + Lifecycle + SubAgent)
- [ ] Test demo timing (aim for 7min total, leaving 1min buffer)
- [ ] Prepare slides (max 8-10 slides)

### Demo Assets
- [ ] Demo 1 recording: Ball generation with tool call highlights
- [ ] Demo 2 recording: L5-1 iterative calibration (3 iterations)
- [ ] Demo 3 recording: Drum mixer diagnostic analysis
- [ ] Backup: Static screenshots if live demo fails

### Technical Setup
- [ ] Ensure PFC server is running before presentation
- [ ] Test WebSocket connection stability
- [ ] Prepare fallback: Pre-recorded videos if live demo fails
- [ ] Have example scripts ready to show if needed

### Slides Outline
1. Title slide
2. Problem statement (DEM + LLM challenges)
3. Architecture overview (3 components)
4. Demo 1 intro slide
5. Demo 2 intro slide
6. Demo 3 intro slide
7. Experiment design + metrics
8. Conclusion + future work

---

## Risk Mitigation

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Live demo fails | Medium | Pre-record all demos as backup |
| Time overrun | Medium | Practice timing, cut Demo 1 to 1.5min if needed |
| L5-1 not ready | Low | Use L3-4 (Undrained Triaxial) as fallback |
| Audience questions interrupt | Low | Hold Q&A until end, politely defer |

---

## Speaker Notes

### Key Messages to Emphasize
1. "Documentation tools eliminate hallucination—this is the core innovation"
2. "Autonomous iteration without step-by-step approval—agent decides when to interrupt and restart"
3. "SubAgent delegation prevents context exhaustion—returns conclusions, not raw data"

### Anticipated Questions
**Q: How does this compare to RAG or fine-tuning?**
A: RAG retrieves general knowledge; we retrieve verified syntax. Fine-tuning is data-hungry and rigid; documentation is explicit and updatable.

**Q: What if documentation is incomplete?**
A: Agent discovers capability boundaries through browsing—where built-ins end, innovation begins.

**Q: Can this generalize beyond PFC?**
A: Yes—any simulation software with structured documentation (FLAC, COMSOL, ANSYS). Core pattern: Query → Browse → Execute.

**Q: How do you handle long simulation times?**
A: Task lifecycle management—background execution with status polling. Agent checks progress periodically and decides next action.

---

## Post-Presentation TODO

- [ ] Gather feedback on demo effectiveness
- [ ] Note questions for FAQ section in paper
- [ ] Update experimental_tasks.md based on demo experience
- [ ] Consider adding presentation demos as standard test cases
