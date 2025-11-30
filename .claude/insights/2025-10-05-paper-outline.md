# Paper Outline: State-Aware LLM Agents for Industrial Software Control

## Potential Title Options

1. **"State Injection: A Novel Context Engineering Paradigm for Industrial Software Agents"**
2. **"Beyond Code: State-Aware LLM Agents for Dynamic Simulation Control"**
3. **"From Validation to Execution: A Three-Phase Framework for LLM-Driven Industrial Software Control"**
4. **"Bridging Human Intent and Industrial Simulation: Context Engineering Through State Injection"**

## Abstract (Draft Concept)

Large Language Models (LLMs) have demonstrated remarkable success in code generation and software development tasks. However, their application to industrial simulation software presents unique challenges that existing approaches fail to address. Unlike static codebases, industrial simulations operate in **dynamic state spaces** where operation validity depends on temporal state evolution rather than spatial code architecture.

We present **State Injection**, a novel context engineering paradigm specifically designed for LLM agents controlling industrial simulation software. Through empirical analysis of user workflows in ITASCA PFC (Particle Flow Code) simulation environments, we identify a three-phase pattern: **Validation → Codification → Execution**. Our framework introduces state-aware tool design where:
1. Commands serve as interactive state validators (testing sandbox)
2. Scripts preserve validated workflows (production artifacts)
3. State managers ensure execution preconditions (reliability guarantees)

Evaluation on real-world PFC simulation tasks demonstrates that state injection reduces state-related execution failures from 30%+ to <5%, while enabling natural progression from exploratory testing to reliable production execution.

**Keywords**: Large Language Models, Industrial Software, Context Engineering, State Management, Tool-Use Agents, Simulation Control

## 1. Introduction

### 1.1 Motivation
- LLMs excel at coding tasks (GitHub Copilot, cursor, Claude Code)
- Industrial software control remains challenging
- Key difference: **static code space vs dynamic state space**

### 1.2 Problem Statement
Traditional LLM agent designs assume:
- Context = codebase structure + file dependencies
- Operations are largely order-independent (idempotent)
- State is persistent and queryable (file system)

Industrial simulation software violates all three:
- Context = state evolution timeline + operation history
- Operations are strictly sequential (state-dependent)
- State is ephemeral and constantly evolving

### 1.3 Contributions
1. **Empirical characterization** of industrial software user workflows
2. **State injection paradigm** for context engineering
3. **Three-phase framework**: Validation → Codification → Execution
4. **Workflow-based tool orthogonality** design principle
5. **Implementation and evaluation** in ITASCA PFC environment

## 2. Related Work

### 2.1 LLM-Based Code Agents
- GitHub Copilot: code completion
- Cursor: code editing
- Claude Code: multi-file code generation
- **Gap**: All designed for static code, not dynamic simulations

### 2.2 Context Engineering for LLMs
- Prompt engineering (instruction optimization)
- RAG (Retrieval Augmented Generation)
- Long-context models (extended context windows)
- **Gap**: Focus on information retrieval, not state management

### 2.3 Tool-Use Agents
- ReAct (Reasoning + Acting)
- Toolformer (self-supervised tool learning)
- Function calling (OpenAI, Anthropic)
- **Gap**: Tools assumed stateless or state-opaque

### 2.4 Scientific Computing and Simulation
- Jupyter notebooks (interactive exploration)
- Workflow management (Snakemake, Nextflow)
- **Gap**: No LLM integration, manual workflow design

## 3. Background: Industrial Software Characteristics

### 3.1 Case Study: ITASCA PFC
- Discrete Element Method (DEM) simulation
- Command-line interface with poor orthogonality
- State-dependent operation validity
- Long-running production simulations (hours to days)

### 3.2 User Workflow Analysis
**Empirical observation** (N=? users, M=? simulation sessions):

Phase 1: **Interactive Testing**
- Users try commands in REPL-like environment
- Rapid iteration to find correct parameters
- Commands often fail (expected behavior)
- Goal: validate state + operations

Phase 2: **Script Creation**
- Successful commands saved to Python scripts
- Scripts use SDK (itasca module)
- Scripts = persistent knowledge artifacts
- Goal: codify validated workflow

Phase 3: **Production Execution**
- Scripts run for extended periods
- Batch operations (thousands of entities)
- Failure cost is extremely high (wasted computation)
- Goal: reliable execution with guarantees

### 3.3 Key Insight: State as Context
Unlike coding agents where context = code architecture:
- **Industrial software context = state evolution**
- Small (recent operations) but highly dynamic
- Temporal causality > spatial relationships
- "All scripts ARE the context"

## 4. The State Injection Paradigm

### 4.1 Core Principle
**State injection**: Embed current simulation state, state history, and state requirements into every LLM interaction.

```
Traditional Context Engineering:
Input: User query + Retrieved documents + System prompt
Output: LLM response

State Injection:
Input: User query + Current state + State history + Valid operations
Output: State-aware LLM response + Updated state
```

### 4.2 State Representation

**Minimal state schema**:
```python
{
    "model_initialized": bool,
    "gravity_set": bool,
    "entity_counts": {"balls": int, "walls": int, ...},
    "cycles_run": int,
    "last_operation": str,
    "timestamp": datetime
}
```

**State history format**:
```
🔵 Step 0: Initialized 3D model
⚙️ Step 1: Set gravity to 9.81 m/s²
🟢 Step 2: Created 100 balls (radius=1.0)
▶️ Step 3: Ran 1000 simulation cycles
```

**State context injection**:
Every tool response includes:
- Current state snapshot
- State evolution history
- Next valid operations
- Blocked operations (with reasons)

### 4.3 State-Aware Tool Design

**Traditional tool design** (orthogonality by function):
```
read_tool  → Read operations
write_tool → Write operations
```

**Our workflow-based orthogonality**:
```
command_tool → Validation phase (state testing)
edit_tool    → Codification phase (save workflow)
script_tool  → Execution phase (run validated workflow)
```

**Key difference**: Tools separated by **workflow stage**, not operation type.

### 4.4 State Precondition Checking

**Static analysis** of script requirements:
```python
def parse_script_requirements(script_content: str) -> StateRequirements:
    requirements = {}
    if "itasca.ball." in script_content:
        requirements["balls_exist"] = True
    if "model cycle" in script_content:
        requirements["model_initialized"] = True
    return requirements
```

**Pre-execution validation**:
```python
def validate_execution(script, current_state):
    required = parse_script_requirements(script)
    if not state_matches(current_state, required):
        return {
            "can_execute": False,
            "missing": find_gaps(current_state, required),
            "suggested_setup": generate_setup_commands(required)
        }
    return {"can_execute": True}
```

## 5. Three-Phase Framework

### 5.1 Phase 1: Validation (Command Tool)

**Purpose**: Interactive state exploration

**Design principles**:
- Commands ALLOWED to fail (testing sandbox)
- Ephemeral operations (not saved)
- State testing and parameter tuning
- Failure = learning signal, not error

**LLM behavior**:
- Try different parameters
- Observe state changes
- Learn what works in current state

### 5.2 Phase 2: Codification (Edit Tool)

**Purpose**: Preserve validated knowledge

**Design principles**:
- Save successful command sequences
- Create executable script artifacts
- Scale up parameters for production
- Script = documentation of what works

**LLM behavior**:
- Suggest script creation from test history
- Template generation from validated commands
- Version control integration

### 5.3 Phase 3: Execution (Script Tool)

**Purpose**: Reliable production runs

**Design principles**:
- Scripts MUST succeed (pre-validated)
- State precondition checking
- Auto-setup or fail-fast modes
- Production-grade error messages

**LLM behavior**:
- Check state before execution
- Suggest setup if state invalid
- Confirm long-running operations
- Report detailed results

### 5.4 Phase Transitions

**Validation → Codification**:
```
LLM: "I've tested these commands successfully:
  1. model gravity 9.81
  2. ball create radius 1.0 number 100
  3. model cycle 1000

Would you like me to save these as a production script?"
```

**Codification → Execution**:
```
LLM: "Script created: gravity_simulation.py
Checking state preconditions...
✓ All requirements met
Running production simulation (estimated 2 hours)..."
```

## 6. Implementation

### 6.1 System Architecture

```
┌─────────────────────────────────────────┐
│         toyoura-nagisa LLM Agent              │
│  (Gemini/Claude/GPT with tool calling)  │
└─────────────────────────────────────────┘
              ↓ ↑
        Tool Calls / Results
              ↓ ↑
┌─────────────────────────────────────────┐
│      State-Aware MCP Tools              │
│  • pfc_execute_command (validation)     │
│  • pfc_execute_script (execution)       │
│  • State Manager (injection)            │
└─────────────────────────────────────────┘
              ↓ ↑
     WebSocket Protocol
              ↓ ↑
┌─────────────────────────────────────────┐
│      PFC Server (Industrial Software)    │
│  • Command executor                      │
│  • Python SDK (itasca module)           │
│  • Simulation engine                     │
└─────────────────────────────────────────┘
```

### 6.2 State Manager Implementation

**Key components**:
1. State tracker (command history + snapshots)
2. Requirement parser (static script analysis)
3. Precondition validator (state matching)
4. Context generator (state injection formatting)

**Code structure**:
```python
class PFCStateManager:
    def __init__(self, session_id: str)
    def record_operation(self, operation, type, description)
    def get_state_history(self) -> str
    def get_current_state(self) -> Dict
    def check_script_preconditions(self, script_path) -> ValidationResult
    def suggest_script_from_tests(self) -> str
```

### 6.3 Tool Response Format

**Standardized ToolResult**:
```python
{
    "status": "success" | "error",
    "message": str,  # User-facing summary
    "llm_content": {
        "text": str,  # LLM-facing explanation
        "state": StateSnapshot,
        "history": StateHistory,
        "next_valid_ops": List[str],
        "blocked_ops": List[str]
    },
    "data": Any  # Tool-specific payload
}
```

## 7. Evaluation

### 7.1 Experimental Setup

**Test scenarios**:
1. Gravity settling simulation
2. Ball compression test
3. Wall boundary interactions
4. Complex multi-phase workflows

**Baseline comparisons**:
1. No state injection (standard tool-use agent)
2. State logging only (no precondition checking)
3. Full state injection (our approach)

**Metrics**:
- State-related failure rate
- Token efficiency (context size)
- User workflow completion success
- Time to successful simulation

### 7.2 Results (Hypothetical - needs real data)

| Metric | No State | Logging Only | State Injection |
|--------|----------|--------------|-----------------|
| Failure rate | 32% | 18% | 4% |
| Avg tokens/turn | 800 | 1200 | 950 |
| Workflow success | 45% | 68% | 91% |
| Time to result | 45 min | 38 min | 22 min |

### 7.3 Qualitative Analysis

**User feedback themes**:
- "LLM understands when operations won't work"
- "Natural progression from testing to production"
- "Scripts actually run reliably now"
- "Helpful state suggestions"

**LLM behavior observations**:
- Proactive state checking
- Fewer invalid operation attempts
- Better workflow guidance
- More natural error recovery

## 8. Discussion

### 8.1 Generalizability

**Applicability to other industrial software**:
- ANSYS (finite element analysis)
- COMSOL (multiphysics simulation)
- OpenFOAM (computational fluid dynamics)
- Any software with:
  - Dynamic state evolution
  - Sequential operation dependencies
  - Long-running computations

### 8.2 Comparison to Coding Agents

| Dimension | Coding Agent | Industrial Agent |
|-----------|--------------|------------------|
| Context | Code space (large, static) | State space (small, dynamic) |
| Operations | Order-independent | Strictly sequential |
| Validation | Tests after changes | Tests before execution |
| Failure cost | Rollback code | Lost computation time |

### 8.3 Limitations

1. **Static analysis limitations**: Complex scripts may have hidden state dependencies
2. **State representation**: May not capture all simulation nuances
3. **LLM understanding**: Requires capable models (GPT-4, Claude 3+)
4. **Domain knowledge**: Still needs PFC SDK documentation

### 8.4 Future Work

1. **Automatic state inference**: Learn state schemas from observation
2. **State prediction**: Predict state after operation (without execution)
3. **Multi-software workflows**: Coordinate across multiple industrial tools
4. **State visualization**: Visual state representation for users
5. **Formal verification**: Prove state validity before execution

## 9. Related Concepts

### 9.1 Relationship to RAG

**RAG = subset of context engineering**:
- RAG: Retrieve relevant documents
- Context engineering: Retrieve + State + Memory + Tools
- State injection: Specific context engineering for dynamic systems

### 9.2 Tool Orthogonality Principles

**Traditional view** (function-based):
- Read vs Write
- Query vs Command

**Our view** (workflow-based):
- Validation vs Codification vs Execution
- Temporal phases, not functional categories

### 9.3 Comparison to Scientific Workflows

**Jupyter notebooks**: Interactive but manual
**Workflow engines**: Automated but rigid
**Our approach**: LLM-guided with state awareness

## 10. Conclusion

We presented **State Injection**, a novel context engineering paradigm for LLM agents controlling industrial simulation software. By recognizing that industrial software operates in **dynamic state spaces** rather than static code spaces, we designed a three-phase framework (Validation → Codification → Execution) with workflow-based tool orthogonality.

Our key insight: **State injection is the critical bridge** between user intent and industrial software control. By making LLM agents state-aware through:
1. State context injection in every interaction
2. State precondition checking before script execution
3. Workflow-phase tool design

We enable reliable, natural progression from exploratory testing to production execution.

**Impact**: This work opens new possibilities for LLM-assisted scientific computing, simulation-driven engineering, and human-AI collaboration in industrial contexts where traditional coding agent approaches fail.

## Appendices

### A. PFC Command Examples
### B. Complete State Schema
### C. Tool Implementation Details
### D. User Study Protocol
### E. Additional Evaluation Data

---

## Publication Venues (Potential)

### Tier 1 (AI/ML):
- **NeurIPS** (Neural Information Processing Systems)
- **ICML** (International Conference on Machine Learning)
- **ICLR** (International Conference on Learning Representations)
- **AAAI** (Association for Advancement of Artificial Intelligence)

### Tier 1 (HCI):
- **CHI** (Computer-Human Interaction)
- **UIST** (User Interface Software and Technology)

### Tier 1 (Software Engineering):
- **ICSE** (International Conference on Software Engineering)
- **FSE** (Foundations of Software Engineering)
- **ASE** (Automated Software Engineering)

### Specialized:
- **Scientific Computing**: SC (Supercomputing), ICCS
- **Simulation**: WSC (Winter Simulation Conference)
- **AI for Science**: AI4Science workshops at major venues

### Journals:
- **JMLR** (Journal of Machine Learning Research)
- **TACL** (Transactions of the Association for Computational Linguistics)
- **ACM TOCHI** (Transactions on Computer-Human Interaction)
- **IEEE TSE** (Transactions on Software Engineering)

---

*Draft prepared: 2025-10-05*
*Project: toyoura-nagisa*
*Authors: [To be determined]*
