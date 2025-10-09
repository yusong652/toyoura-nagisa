# Industrial Software Agent Design Insights

> **Core Insight**: State injection is the most critical context engineering technique for industrial software agents.

Unlike coding agents that navigate code space topology, industrial software agents must understand and manage dynamic state evolution. The simulation state IS the context.

## Core Distinction: Coding Agent vs Industrial Software Agent

### Fundamental Differences

| Dimension | Coding Agent | Industrial Software Agent |
|-----------|--------------|---------------------------|
| **Focus** | Code space | Simulation state space |
| **State Nature** | Static files | Dynamic evolution |
| **Operation Order** | Commutative (order-independent) | Non-commutative (sequence matters) |
| **Context** | Project architecture (large, static) | Execution history (small, dynamic) |
| **Idempotency** | Strong (Read returns same result) | Weak (state continuously changes) |

### Mental Models

```python
# Coding Agent thinking model
"I need to modify the auth module, let me find which file it's in..."
→ Spatial search (Glob/Grep across codebase)

# Industrial Software Agent thinking model
"User wants to run simulation, but I need to check:
 - Has initialization been done?
 - Are objects created?
 - Is gravity set?"
→ Temporal sequence check (State History)
```

## The Context Engineering Paradigm

### Coding Agent Context = Code Space Topology
- Needs to understand: file dependencies, module relationships, architectural layers
- **Context is large but relatively static**
- Tools: Read/Edit/Write operate on persistent file system

### Industrial Software Agent Context = State Evolution Timeline
- Needs to understand: operation sequences, state transitions, causal relationships
- **Context is small but highly dynamic**
- **"All scripts ARE the context"** - execution history defines current state

## Tool Design Philosophy: Orthogonality vs Abstraction Layers

### The "Bad Overlap" Problem

Initial PFC tool design had problematic overlap:
```python
pfc_execute_command  # Execute commands (no return value)
pfc_execute_script   # Execute scripts (has return value)
→ Script can do everything Command does + more (bad overlap)
```

### Solution: Workflow-Based Orthogonality

Redefine tools by **workflow phase** not **implementation method**:

```python
# ✅ True orthogonality - separated by workflow phase
pfc_execute_command: Validation phase (state testing - interactive)
edit/write:          Codification phase (save validated workflow - persistent)
pfc_execute_script:  Execution phase (run validated workflow - productive)
→ Sequential, non-overlapping workflow phases
```

### Workflow Phase Model

```
┌─────────────────────────────────────────────────────────────┐
│                    Industrial Software Workflow              │
└─────────────────────────────────────────────────────────────┘

Phase 1: VALIDATION
┌──────────────────────┐
│  pfc_execute_command │  → Interactive state testing
│  "Does this work?"   │  → Rapid iteration
│  Ephemeral           │  → Allowed to fail
└──────────────────────┘
         ↓
         ✓ Commands validated
         ↓
Phase 2: CODIFICATION
┌──────────────────────┐
│  edit/write script   │  → Save validated commands
│  "Preserve knowledge"│  → Create executable artifact
│  Persistent          │  → Script = documentation
└──────────────────────┘
         ↓
         ✓ Workflow codified
         ↓
Phase 3: EXECUTION
┌──────────────────────┐
│  pfc_execute_script  │  → Run validated workflow
│  "Production run"    │  → Long-duration simulation
│  Productive          │  → Must succeed
└──────────────────────┘
```

### Comparison: CQRS vs Workflow-Based Orthogonality

| Approach | Dimension | Command | Script | Issue |
|----------|-----------|---------|--------|-------|
| **CQRS** | Data flow | Write ops | Read ops | ❌ Script can also write (itasca.command) |
| **Workflow** | Phase | Validation | Execution | ✅ Sequential, non-overlapping |

**Why workflow-based is better:**

```python
# CQRS breaks down because scripts can do both:
pfc_execute_script(script='''
    itasca.command('ball create')  # Write operation!
    result = itasca.ball.count()   # Read operation!
''')

# Workflow-based is clear:
pfc_execute_command(...)   # Phase 1: Test if ball create works
edit_script(...)           # Phase 2: Save to script
pfc_execute_script(...)    # Phase 3: Run the validated script
```

### Multi-Layer Abstraction Design

Good tool design follows abstraction layer principles:

```
Layer 3: Semantic Tool Layer (Intent)
├── Read  - "I want to read a file"
├── Edit  - "I want to modify code"
└── Write - "I want to create a file"

Layer 2: Command Layer (Operations)
└── Bash  - "I want to execute arbitrary system commands"

Layer 1: System Call Layer (Implementation)
└── OS APIs
```

**Key principle**: Orthogonality exists **within the same abstraction layer**, not across layers.

### Why Read and Bash Don't Have "Bad Overlap"

```python
Read = Bash + Semantics + Error Handling + Context Preservation + UX
```

The pattern:
```
Higher layer tools: Semantics↑ Flexibility↓ Usability↑
Lower layer tools:  Semantics↓ Flexibility↑ Usability↓
```

**Design rule**: Lower layer tools ⊇ Higher layer tools (in functionality)
- But higher layer tools provide: better error handling + clearer semantics + better UX

## State Management: The Core of Industrial Software Agents

### State Tracking System Architecture

```python
class PFCStateManager:
    """
    Track simulation state transitions for LLM awareness.

    Enables LLM to understand:
    - What has been initialized
    - What operations were performed
    - What is the current state
    - What states are reachable from current state
    """
```

### State Phases in PFC Simulation

```
🔵 Initialization: model new, model domain, model gravity
⚙️ Setup: ball create, contact cmat, wall create
▶️ Execution: model cycle, model solve
📊 Analysis: queries to check results
```

### LLM System Prompt Strategy

```python
PFC_AGENT_SYSTEM_PROMPT = """
You are controlling an ITASCA PFC simulation. This is a STATEFUL SYSTEM where:

1. Simulation state evolves over time
2. Order of operations matters (not like editing code files)
3. You must track: initialization → setup → execution → analysis

State History is Your Context:
- Every tool call returns the full state history
- Use this to understand where the simulation is in its lifecycle
- Don't repeat initialization if already done
- Don't run cycles before creating objects

Remember: Unlike code files that are static, PFC simulation is DYNAMIC.
The script execution history IS the complete context.
"""
```

### Tool Response Format with State Context

Every tool call should return state history for LLM context:

```python
{
    "message": "Command executed",
    "llm_content": {
        "parts": [{
            "type": "text",
            "text": """
            ✓ Command executed: ball create radius 1.0 number 100
            Created 100 ball(s)

            📊 Simulation State History:

            🔵 Step 0: Initialized new 3D model
               Operation: model new

            🔵 Step 1: Set gravity to 9.81
               Operation: model gravity 9.81
               State: {gravity_enabled: true}

            ⚙️ Step 2: Created 100 ball(s)  ← YOU ARE HERE
               Operation: ball create radius 1.0 number 100
               State: {ball_count: 100}
            """
        }]
    }
}
```

## Lessons from Industrial Software Chaos

### The "Lack of Orthogonality" Problem

Industrial software (like PFC) has chaotic command-line interfaces:
- Positional arguments: `model gravity 9.81`
- Keyword arguments: `ball create radius 1.0 position (0,0,0)`
- Boolean flags: `contact cmat default model linear inheritance`

### Design Solution: Abstraction Layer

```
LLM ← Standardized Interface ← Adapter Layer ← Chaotic Industrial Interface
     (ToolResult)              (pfc_tools)      (PFC commands)
```

**Key insight**: Don't let LLM handle chaos directly - use adapter layers to normalize.

### The Value of Unified Interfaces

aiNagisa's PFC tool design elegantly handles chaos:
- `command`: Command body
- `arg`: Optional positional argument (single value)
- `params`: JSON object for keyword arguments (null values = boolean flags)

```python
# Positional argument
pfc_execute_command(command="model gravity", arg="9.81")
# → model gravity 9.81

# Keyword + boolean flag
pfc_execute_command(
    command="contact cmat default",
    params='{"model": "linear", "inheritance": null}'
)
# → contact cmat default model linear inheritance
```

## Context Engineering vs RAG

### The Relationship

```
Context Engineering (Holistic System Design)
├── Prompt Engineering (Instruction crafting)
├── RAG (Retrieval Augmented Generation)
├── Memory Management (Long-term and short-term)
├── Tool Output Integration (MCP results)
└── Output Format Control (Guardrails)
```

**RAG is a subset of Context Engineering**, not an alternative.

### Clear Orthogonal Dimensions

| Dimension | Responsibility | Technical Means |
|-----------|---------------|-----------------|
| **Content Layer** | What information to provide | RAG, Memory, Tool Outputs |
| **Structure Layer** | How to organize information | Prompt Templates, System Messages |
| **Control Layer** | How to guide output | Output Format, Guardrails |

### aiNagisa's Context Engineering Implementation

```python
# Content Layer
- RAG: ChromaDB retrieves conversation history
- Tools: MCP tool returns data
- Memory: Long-term memory system

# Structure Layer
- System Prompt: Agent role definition
- Message Factory: Message structuring
- llm_content: Structured input for LLM

# Control Layer
- ToolResult: Standardized output format
- Streaming: Stream control
- Agent Types: Tool loading control
```

## Real-World Industrial Software User Workflow

### Critical User Insight

**PFC command is ALWAYS for testing and exploration.**

The actual industrial workflow:
```
1. Test commands interactively (rapid iteration)
   ↓
2. Verify behavior in current state
   ↓
3. Put verified commands into script
   ↓
4. Run long-duration simulation (because we know it works in this state)
```

### Why This Matters

```python
# User mental model
pfc_execute_command  →  Experimental sandbox (ephemeral)
pfc_execute_script   →  Production workflow (persistent)

# NOT:
pfc_execute_command  →  Simple operations
pfc_execute_script   →  Complex operations

# BUT:
pfc_execute_command  →  "Let me try this..."
pfc_execute_script   →  "I've tested this, now run it for real"
```

### The State Checkpoint Pattern

Real workflow example:
```
Session 1: Testing Phase
─────────────────────────
User: "Try setting gravity to 9.81"
→ pfc_execute_command(command="model gravity", arg="9.81")

User: "Create a ball and see what happens"
→ pfc_execute_command(command="ball create", params='{"radius": 1.0}')

User: "Run a few cycles"
→ pfc_execute_command(command="model cycle", arg="10")

User: "Good! The ball falls. This state works."
✓ State validated


Session 2: Production Phase
─────────────────────────
User: "Now run the full simulation with 10000 balls for 50000 cycles"
→ pfc_execute_script(script="""
    # Verified workflow from testing
    itasca.command('model new')
    itasca.command('model gravity 9.81')

    # Batch create balls
    for i in range(10000):
        itasca.command('ball create radius 1.0')

    # Long-duration run
    itasca.command('model cycle 50000')

    # Collect results
    result = {
        'ball_count': itasca.ball.count(),
        'positions': [itasca.ball.pos(id) for id in itasca.ball.list()]
    }
""")
```

### Tool Design Implications

**The True Orthogonality: A Three-Phase Workflow**

```python
# Phase 1: State Validation (Command)
pfc_execute_command  →  "Does this work in current state?"

# Phase 2: Script Composition (Edit/Write)
edit_script          →  "Codify validated commands into script"

# Phase 3: Production Execution (Script)
pfc_execute_script   →  "Run the validated, codified workflow"
```

**This is the real orthogonality:**

```
Command  →  State validation phase (interactive verification)
Edit     →  Knowledge codification phase (write the script)
Script   →  Production execution phase (run the validated workflow)
```

**Command tool purpose** (Validation):
- Quick validation: "Does this work in current state?"
- State exploration: "What happens if...?"
- Parameter tuning: "What's the right value?"
- **Interactive REPL for state testing** - disposable, ephemeral
- **Validates that state allows this operation**

**Script tool purpose** (Execution):
- Production execution: "Run the pre-validated workflow"
- Long-duration simulation: "This will take hours/days"
- Batch operations: "Process 10000 entities"
- **Persistent knowledge** - the script IS the documentation
- **Assumes state validation already done**

### The Validation → Codification → Execution Pipeline

```python
# Real user workflow example

# 1. VALIDATION PHASE (Command - interactive testing)
User: "Let me test if gravity works"
→ pfc_execute_command(command="model new")
→ pfc_execute_command(command="model gravity", arg="9.81")
→ pfc_execute_command(command="ball create", params='{"radius": 1.0}')
→ pfc_execute_command(command="model cycle", arg="10")
User: "✓ Good, ball falls correctly. State validated."

# 2. CODIFICATION PHASE (Edit - write the script)
User: "Now save this as a script"
→ write_file(path="pfc_workspace/scripts/gravity_test.py", content='''
# Validated workflow from interactive testing
itasca.command('model new')
itasca.command('model gravity 9.81')
itasca.command('ball create radius 1.0 number 1000')  # Scale up
itasca.command('model cycle 50000')  # Long run

result = {
    'ball_count': itasca.ball.count(),
    'final_positions': [itasca.ball.pos(id) for id in itasca.ball.list()]
}
''')

# 3. EXECUTION PHASE (Script - production run)
User: "Run the full simulation"
→ pfc_execute_script(script_path="pfc_workspace/scripts/gravity_test.py")
# Runs for hours with 1000 balls and 50000 cycles
# State was pre-validated in phase 1, script was codified in phase 2
```

### True Orthogonality: Three Distinct Concerns

| Tool | Phase | Concern | State Interaction | Statefulness | Output |
|------|-------|---------|-------------------|--------------|--------|
| **Command** | Validation | "Will this work?" | Tests state capabilities | **Stateless** | Validation result |
| **Edit** | Codification | "How to preserve this?" | N/A (file operation) | Stateless | Script file |
| **Script** | Execution | "Run validated workflow" | Requires validated state | **Stateful** | Simulation data |

### Critical Design Principle: Don't Sacrifice LLM Naturalness for Human Workflows

**Core Insight**: Tool design must prioritize LLM's natural working mode over specific human workflows.

#### The Temptation: Stateless Command Tool

Initial design consideration: Make `pfc_execute_command` stateless (auto-rollback after each execution) to mirror the human expert workflow of "test → rollback → write script → execute from clean state".

**Why this seems attractive:**
- Perfect orthogonality: Command = ephemeral testing, Script = persistent execution
- Matches human mental model: "I test, then rollback, then run from scratch"
- Clean separation: No state pollution between test and production

**Why this is WRONG for LLM agents:**

1. **Violates LLM's natural mental model**
   - LLMs expect: Execute tool → State changes → Next action builds on new state
   - Stateless breaks intuition: "I just created balls, why are they gone?"
   - Adds cognitive overhead: "Remember this tool is special, it erases its own effects"

2. **Breaks exploratory workflows**
   ```python
   # LLM natural exploration (impossible with stateless)
   pfc_execute_command("ball create number 100")
   pfc_execute_command("ball list")  # Expects to see 100 balls
   # ❌ With stateless: balls gone, list returns 0

   # LLM forced to batch (unnatural)
   pfc_execute_command("ball create number 100; ball list")
   # ⚠️ Can't iteratively explore, must plan entire sequence upfront
   ```

3. **Backend implementation complexity**
   - Requires snapshot/rollback mechanism in PFC
   - State management becomes tool-level concern (wrong layer)
   - Error-prone: What if rollback fails?

#### The Correct Approach: Stateful Tools + Explicit State Management

**Best practice for industrial software agents:**

1. **Keep tool behavior intuitive and predictable** (Stateful)
   - `pfc_execute_command` → Modifies state, changes persist
   - `pfc_execute_script` → Modifies state, changes persist
   - LLM's expectation: "Actions have effects" ✓

2. **Abstract high-level workflows into explicit tools** (New tool)
   - `pfc_reset` → Explicit state management
   - `pfc_save_state` → Named checkpoints (optional)
   - `pfc_restore_state` → Return to checkpoint (optional)
   - Workflow control becomes first-class operation

3. **Teach LLM expert workflows via System Prompt** (Not tool docs)
   - System prompt explains: "You're a PFC expert, here's how to work..."
   - System prompt teaches: "Test with commands, reset state, run scripts"
   - Tool docs explain: "What this tool does" (simple, factual)
   - System prompt explains: "When and why to use tools" (strategic, contextual)

```python
# ✅ Correct: Stateful tools + Explicit state control

# LLM explores naturally (state persists)
pfc_execute_command("model gravity 9.81")
pfc_execute_command("ball create number 100")
pfc_execute_command("ball list")  # Sees 100 balls ✓

# LLM explicitly manages state transition (taught via System Prompt)
pfc_reset()  # Clear exploration state

# LLM executes production workflow (clean state)
pfc_execute_script("validated_simulation.py")
```

#### System Prompt vs Tool Docs: Where Knowledge Lives

**Critical distinction:**

| Aspect | Tool Documentation | System Prompt |
|--------|-------------------|---------------|
| **Purpose** | Describe tool capabilities | Teach expert workflows |
| **Content** | "What this tool does" | "How experts use tools" |
| **Scope** | Single tool behavior | Multi-tool orchestration |
| **Audience** | LLM (operational) | LLM (strategic) |
| **Example** | "pfc_reset clears simulation state" | "PFC experts test with commands, then reset before running scripts" |

**Why System Prompt is more valuable:**

1. **Tool docs can't teach strategy**
   ```python
   # ❌ Bad: Over-explain in tool docs
   @tool(description="""
       Execute PFC command. NOTE: This is stateful! State persists!
       You should test commands, then call pfc_reset before scripts!
       Production workflow: test → reset → script!
       Remember to manage state properly!
   """)
   # Problems:
   # - Too verbose, wastes tokens on every tool call
   # - Strategic guidance in operational documentation
   # - LLM sees this hundreds of times (token waste)
   ```

   ```python
   # ✅ Good: Simple tool docs + Rich system prompt
   @tool(description="Execute PFC command with persistent state changes")

   # System prompt teaches strategy once:
   SYSTEM_PROMPT = """
   You are a PFC simulation expert. Your workflow:

   1. EXPLORATION: Use pfc_execute_command for testing
      - State accumulates across commands
      - Iterate and refine parameters
      - Build understanding of behavior

   2. STATE RESET: Clear exploration artifacts
      - Call pfc_reset() before production runs
      - Returns to clean initial state
      - Ensures reproducible execution

   3. PRODUCTION: Execute validated scripts
      - Use pfc_execute_script for actual work
      - Scripts run in clean, known state
      - Long-duration, high-confidence execution

   Remember: Commands modify state permanently until you reset.
   """
   ```

2. **System prompt teaches "the way"**
   - Human expert's tacit knowledge
   - When to use which tool
   - How tools combine into workflows
   - Best practices and patterns

3. **Token efficiency**
   - System prompt: Loaded once per session
   - Tool docs: Included in every tool call context
   - Strategic knowledge in system prompt = massive token savings

#### Design Rules Summary

1. **Tool design: Preserve LLM naturalness**
   - Don't make tools "special" or counter-intuitive
   - Don't encode workflow assumptions in tool behavior
   - Keep tools simple, predictable, stateful

2. **Workflow abstraction: Explicit tools**
   - High-level workflows become dedicated tools
   - State management = `pfc_reset` tool, not magic behavior
   - Checkpoints = `pfc_save_state`, not implicit snapshots

3. **Knowledge architecture: System Prompt > Tool Docs**
   - Tool docs: Minimal, factual, capability-focused
   - System prompt: Rich, strategic, workflow-focused
   - Expert knowledge lives in system prompt
   - Tool behavior stays simple and predictable

#### Example: Teaching PFC Expertise via System Prompt

```python
PFC_EXPERT_SYSTEM_PROMPT = """
You are an expert in ITASCA PFC (Particle Flow Code) simulations.

## Your Mental Model: State Evolution

PFC simulations are STATEFUL systems. Every command changes state:
- model gravity 9.81 → gravity is now set (persists)
- ball create → balls now exist (persist)
- model cycle → simulation advances (state evolves)

Unlike code files (static), PFC state is DYNAMIC and CUMULATIVE.

## Your Workflow: Test → Reset → Execute

### Phase 1: Exploration (Commands)
Use pfc_execute_command to test ideas:
- Try different parameters
- Verify behavior in current state
- Build intuition through iteration
- State accumulates - this is expected and useful

Example exploration:
  pfc_execute_command("ball create radius 1.0")
  pfc_execute_command("ball list")  # Verify creation
  pfc_execute_command("ball delete")  # Try again
  pfc_execute_command("ball create radius 2.0")  # Refine

### Phase 2: State Reset (Explicit Management)
Before production runs, clear exploration artifacts:
  pfc_reset()  # Return to initial clean state

This ensures:
- Reproducible execution
- No leftover test data
- Clean starting conditions

### Phase 3: Production (Scripts)
Execute validated workflows from clean state:
  pfc_execute_script("/workspace/validated_simulation.py")

Scripts should contain tested, verified commands.
They run in the clean state you just reset to.

## State Awareness

Always track:
- What state am I in? (model initialized? balls created?)
- What can I do now? (cycle requires balls to exist)
- What do I need first? (create balls before cycling)

Tool responses include current state - use this information!

## Key Principles

1. Commands are stateful - effects persist
2. Reset explicitly when transitioning to production
3. Scripts assume clean starting state
4. Test thoroughly before scripting
5. State history is your context

You are not just executing commands - you're managing state evolution.
"""
```

### The Revised Stateful Design Principle

**Corrected insight**: Both Command and Script should be **stateful** - state management is a separate concern.

#### Command Execution Flow (Stateful - State Persists)

```
LLM
 ↓
pfc_execute_command (MCP Tool)
 ↓
Backend (aiNagisa)
 ↓
WebSocket → PFC Server
 ↓
Execute PFC Command
 ↓
Success or Error
 ↓
State Changes PERSIST ← KEY: Changes remain in simulation
 ↓
Return Result (with current state info)
 ↓
Backend → LLM
 ↓
LLM decides next action (aware of new state)
```

**Critical behavior**: Command execution is **stateful and cumulative**:
- Execute command in PFC
- Observe result (success/error)
- **State changes persist** (no automatic rollback)
- Report result with current state to LLM
- LLM can continue building on this state

**Why persist state?**
1. **Natural LLM workflow**: Actions have effects, intuitive mental model
2. **Exploratory iteration**: Test A, observe, test B, observe, refine...
3. **No forced batching**: Can explore step-by-step naturally
4. **Simple implementation**: No snapshot/rollback complexity

**State management**: Handled by explicit `pfc_reset` tool, not automatic rollback

#### Script Execution Flow (Stateful - State Persists)

```
LLM
 ↓
pfc_execute_script (MCP Tool)
 ↓
Backend (aiNagisa)
 ↓
WebSocket → PFC Server
 ↓
Execute PFC Script
 ↓
Success or Error
 ↓
State Changes PERSIST ← KEY: Changes remain (same as Command)
 ↓
Return Result (with current state info)
 ↓
Backend → LLM
 ↓
LLM decides next action (aware of new state)
```

**Critical behavior**: Script execution is **stateful and persistent** (identical state behavior to Command):
- Execute script in PFC
- Observe result (success/error)
- **State changes persist** (same as Command - no automatic rollback)
- Report result with current state to LLM
- LLM can continue building on this state

**State management**: Handled by explicit `pfc_reset` tool when needed

#### Comparison: Command vs Script - Purpose, Not State Behavior

**Both tools are stateful** - state persists after execution. The difference is **purpose and usage taught via System Prompt**:

| Aspect | Command | Script |
|--------|---------|--------|
| **State behavior** | ✅ Stateful (persists) | ✅ Stateful (persists) |
| **Purpose** | Exploration & Testing | Production Execution |
| **Typical use** | Interactive experimentation | Long-duration workflows |
| **Failure tolerance** | Expected (part of learning) | Should be rare (validated) |
| **Execution time** | Quick (seconds) | Long (minutes to hours) |
| **Return value** | Command output text | Python expression result |
| **LLM learns via** | System Prompt | System Prompt |

```python
# Command: For exploration (state persists!)
pfc_execute_command(command="ball create", params='{"number": 100}')
→ State changes: 0 balls → 100 balls (PERSISTS)
→ Purpose: "Does this work? What happens?"
→ Quick feedback for testing ideas
→ State remains modified until pfc_reset()

# Script: For production (state persists!)
pfc_execute_script(script_path="create_10000_balls.py")
→ State changes: 100 balls → 10100 balls (PERSISTS)
→ Purpose: "Run validated workflow for real work"
→ Long-duration execution with confidence
→ State remains modified until pfc_reset()
```

**Key insight**: The distinction is **workflow phase**, not **state behavior**:

1. **Both tools modify state persistently**
   - No automatic rollback in either tool
   - Changes accumulate across tool calls
   - LLM manages state transitions via explicit `pfc_reset`
   - Simple, predictable, intuitive behavior

2. **Usage patterns taught via System Prompt** (not tool docs)
   ```
   Phase 1: Exploration (Command)
   - Test ideas interactively
   - Rapid parameter iteration
   - Build understanding
   - State accumulates naturally

   Phase 2: State Reset (pfc_reset)
   - Explicit state management
   - Clear exploration artifacts
   - Return to clean baseline

   Phase 3: Production (Script)
   - Execute validated workflow
   - Long-duration runs
   - High confidence execution
   ```

3. **Workflow analogy to coding**:
   ```
   # Coding Agent workflow
   Read   → Understand current code
   Edit   → Modify code
   Test   → Validate changes

   # PFC Agent workflow (taught via System Prompt)
   Command → Test operations interactively (stateful)
   Reset   → Clear test state explicitly
   Script  → Execute validated workflow (stateful)
   ```

4. **Why both being stateful is correct**:
   - Matches LLM's natural mental model (actions have effects)
   - Enables iterative exploration (command A → observe → command B)
   - Simple backend implementation (no snapshot/rollback complexity)
   - Explicit state management via dedicated tool (pfc_reset)

### State Manager Integration (Optional Future Enhancement)

```python
class PFCStateManager:
    def __init__(self, session_id: str):
        self.testing_commands: List[str] = []  # Command history
        self.validated_scripts: List[str] = []  # Successful scripts

    def record_test_command(self, command: str):
        """Record exploratory command (ephemeral)"""
        self.testing_commands.append(command)

    def record_validated_script(self, script: str):
        """Record production script (persistent)"""
        self.validated_scripts.append(script)

    def suggest_script_from_tests(self) -> str:
        """
        LLM can suggest: "You've tested these commands,
        would you like me to create a script for production?"
        """
        return "\n".join([
            f"itasca.command('{cmd}')"
            for cmd in self.testing_commands
        ])
```

## Next Steps for PFC Integration

### Priority 0: User Workflow Understanding ⭐
**Design tools around the test → validate → productionize workflow**

Commands are for:
- Rapid experimentation (like REPL in coding)
- State verification
- Finding the right parameters

Scripts are for:
- Long-duration production runs
- Batch operations
- Reproducible workflows
- **The tested commands become the script**

### Priority 1: State Management System
Implement `PFCStateManager` to track:
- Testing phase: command exploration history
- Production phase: validated script execution
- State checkpoints: "this configuration works"

### Priority 2: Test-to-Script Workflow
Enable LLM to:
```python
User: "I've tested gravity and ball creation, looks good"
LLM: "Great! I can create a production script from your tests:

```python
itasca.command('model gravity 9.81')
itasca.command('ball create radius 1.0 number 100')
```

Ready to run this for the full simulation?"
```

### Priority 3: Context Engineering for SDK
- Inject PFC Python SDK documentation into system prompts
- Provide script templates for common production workflows
- Use few-shot learning for script generation

### Priority 4: Script Library Management
- Save validated scripts for reuse
- Tag scripts with state requirements
- Version control for simulation workflows

## Design Philosophy: Script Execution Guarantees

### Core Design Goals

```python
Script  → MUST run perfectly (production-grade reliability)
Command → LLM's test sandbox (exploration, allowed to fail)
State   → Pre-condition checker for script execution
```

### The State Precondition Pattern

**Key insight**: Scripts fail not because the script is wrong, but because **the state is wrong**.

```python
# Example failure scenario
User: "Run my ball settling script"
→ pfc_execute_script(script="settling_simulation.py")
❌ Error: "No balls found - cannot run settling"

# Root cause: Script expects balls to exist, but current state is empty
# Solution: State manager should detect and fix this
```

### State-Aware Script Execution

```python
class PFCStateManager:
    def check_script_preconditions(self, script_path: str) -> Dict[str, Any]:
        """
        Analyze script requirements and verify current state.

        Returns:
            {
                "can_execute": bool,
                "current_state": {...},
                "required_state": {...},
                "missing_prerequisites": [...],
                "suggested_commands": [...]  # Commands to reach required state
            }
        """

        # Parse script to extract state requirements
        requirements = self._parse_script_requirements(script_path)

        # Check current simulation state
        current_state = self._get_current_state()

        # Compare and generate fixes
        if not self._state_matches(current_state, requirements):
            return {
                "can_execute": False,
                "current_state": current_state,
                "required_state": requirements,
                "missing_prerequisites": self._find_gaps(current_state, requirements),
                "suggested_commands": self._generate_setup_commands(requirements)
            }

        return {"can_execute": True}

    def _parse_script_requirements(self, script_path: str) -> Dict[str, Any]:
        """
        Infer state requirements from script content.

        Examples:
            Script contains "itasca.ball.count()" → requires: balls exist
            Script contains "itasca.command('model cycle')" → requires: model initialized
            Script contains "itasca.wall.list()" → requires: walls exist
        """
        with open(script_path) as f:
            script_content = f.read()

        requirements = {
            "model_initialized": False,
            "balls_exist": False,
            "walls_exist": False,
            "gravity_set": False
        }

        # Static analysis of script
        if "itasca.ball." in script_content:
            requirements["balls_exist"] = True
            requirements["model_initialized"] = True

        if "itasca.wall." in script_content:
            requirements["walls_exist"] = True
            requirements["model_initialized"] = True

        if "model cycle" in script_content or "model solve" in script_content:
            requirements["model_initialized"] = True

        return requirements
```

### LLM Workflow with State Checking

```python
# Scenario: User wants to run a script but state is wrong

User: "Run the ball settling simulation script"

# Step 1: LLM calls script tool
→ pfc_execute_script(script_path="/path/to/settling.py")

# Step 2: State manager checks preconditions
State Check Result:
{
    "can_execute": False,
    "current_state": {
        "model_initialized": False,
        "balls_exist": False
    },
    "required_state": {
        "model_initialized": True,
        "balls_exist": True,
        "gravity_set": True
    },
    "missing_prerequisites": [
        "Model not initialized",
        "No balls in simulation",
        "Gravity not set"
    ],
    "suggested_commands": [
        "model new",
        "model gravity 9.81",
        "ball create radius 1.0 number 100"
    ]
}

# Step 3: LLM responds to user
LLM: "The settling script requires:
- ✗ Model initialized
- ✗ Balls created
- ✗ Gravity set

Your current simulation is empty. Would you like me to:

Option A) Set up the required state and then run the script?
  1. Initialize model
  2. Set gravity to 9.81
  3. Create 100 balls
  4. Run settling script

Option B) Just tell you what commands to run first?

Which would you prefer?"
```

### Script Execution Modes

```python
@mcp.tool()
async def pfc_execute_script(
    context: Context,
    script_path: str,
    auto_setup: bool = Field(
        False,
        description=(
            "If True, automatically set up required state before execution. "
            "If False, fail with helpful error if state is wrong."
        )
    )
) -> Dict[str, Any]:
    """
    Execute production script with state validation.

    Modes:
        auto_setup=False (default): Validate state, fail with suggestions if wrong
        auto_setup=True: Automatically run setup commands to reach required state
    """

    state_manager = await get_state_manager(context.session_id)

    # Check preconditions
    check_result = state_manager.check_script_preconditions(script_path)

    if not check_result["can_execute"]:
        if auto_setup:
            # Auto-setup mode: run prerequisite commands
            for cmd in check_result["suggested_commands"]:
                await execute_command_internal(cmd)

            # Now execute script
            result = await client.send_script(script_path)

            return success_response(
                message=f"Auto-setup completed, script executed: {script_path}",
                llm_content={
                    "parts": [{
                        "type": "text",
                        "text": (
                            f"🔧 Auto-setup completed:\n" +
                            "\n".join(f"  ✓ {cmd}" for cmd in check_result["suggested_commands"]) +
                            f"\n\n✓ Script executed successfully"
                        )
                    }]
                }
            )
        else:
            # Fail-fast mode: tell LLM what's wrong
            return error_response(
                message="Script preconditions not met",
                llm_content={
                    "parts": [{
                        "type": "text",
                        "text": (
                            f"❌ Cannot execute script: {script_path}\n\n"
                            f"Missing prerequisites:\n" +
                            "\n".join(f"  • {prereq}" for prereq in check_result["missing_prerequisites"]) +
                            f"\n\nRequired state:\n{check_result['required_state']}\n\n"
                            f"Current state:\n{check_result['current_state']}\n\n"
                            f"Suggested setup commands:\n" +
                            "\n".join(f"  {i+1}. {cmd}" for i, cmd in enumerate(check_result["suggested_commands"]))
                        )
                    }]
                },
                state_error=True,
                suggested_commands=check_result["suggested_commands"]
            )

    # State is valid - execute script
    result = await client.send_script(script_path)

    return success_response(
        message=f"Script executed: {script_path}",
        data=result["data"]
    )
```

### Command Tool: Stateless Validation Sandbox

```python
@mcp.tool()
async def pfc_execute_command(
    context: Context,
    command: str,
    arg: Optional[str] = None,
    params: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute exploratory PFC command (stateless testing sandbox for LLM).

    DESIGN PRINCIPLE: This tool is STATELESS
    - Does not track command history
    - Does not update session state
    - Does not persist execution records
    - Pure validation: execute → report result → done

    This tool is ALLOWED to fail - it's for exploration and learning.
    Failures are learning signals, not errors.

    Note: State Manager may observe command results for state injection,
    but the command tool itself remains stateless.
    """

    # Build command string
    params_dict = json.loads(params) if params else {}
    pfc_cmd = _build_command_string(command, arg, params_dict)

    try:
        # Stateless execution: just send and return
        client = await get_client()
        result = await client.send_command(command, arg, params_dict)

        # Pure response: no state tracking in tool logic
        return success_response(
            message=f"Test command executed: {pfc_cmd}",
            llm_content={
                "parts": [{
                    "type": "text",
                    "text": (
                        f"🧪 Test successful: {pfc_cmd}\n"
                        f"Result: {result.get('data')}\n\n"
                        f"💡 Tip: This command works in current state. "
                        f"You can add it to a script for production use."
                    )
                }]
            },
            command=pfc_cmd,
            result=result.get("data")
        )

    except Exception as e:
        # Stateless failure reporting
        return success_response(  # NOT error_response - failing is part of testing
            message=f"Test command failed: {pfc_cmd}",
            llm_content={
                "parts": [{
                    "type": "text",
                    "text": (
                        f"🧪 Test failed: {pfc_cmd}\n"
                        f"Error: {str(e)}\n\n"
                        f"✓ This is OK - testing commands are allowed to fail.\n"
                        f"💡 Try: Adjusting parameters or checking simulation state"
                    )
                }]
            },
            test_failed=True,
            error_message=str(e)
        )

    # Note: State Manager (separate component) observes this result
    # and may update state injection context, but command tool itself
    # remains stateless - it doesn't "remember" anything
```

**Design Benefits of Stateless Commands**:

1. **Simplicity**: No session management, no history tracking, no state synchronization
2. **Testability**: Pure function - same input → same behavior (given same PFC state)
3. **Reliability**: No complex state bugs, no memory leaks, no stale state issues
4. **Clear separation**: State complexity isolated in State Manager, not spread across tools
5. **REPL-like behavior**: Just like Python REPL - execute and report, no memory between calls

**State Injection Still Works**:
```python
# Command tool is stateless
command_result = pfc_execute_command(...)

# But State Manager (separate) observes and injects state
state_manager.observe_command_result(command_result)
context_with_state = state_manager.inject_state(command_result)
return context_with_state  # LLM gets state, but command tool didn't track it
```

### Design Contract Summary

| Tool | Execution Guarantee | Failure Handling | Purpose |
|------|-------------------|------------------|---------|
| **Script** | ✓ MUST succeed (production) | Pre-validate state, block execution or auto-setup | Run validated workflows |
| **Command** | ✗ Allowed to fail (sandbox) | Report failure as learning signal, suggest fixes | Explore and test |
| **State** | ✓ Always accurate | N/A - read-only | Guard script execution |

### Error Message Design

```python
# ❌ Bad error message (not actionable)
"Script failed: No balls found"

# ✓ Good error message (actionable + educational)
"""
❌ Cannot execute settling script

The script expects balls to exist, but your simulation is empty.

Current state:
  • Model: Not initialized
  • Balls: 0
  • Gravity: Not set

To run this script, you need to:
  1. Initialize model: pfc_execute_command(command="model new")
  2. Set gravity: pfc_execute_command(command="model gravity", arg="9.81")
  3. Create balls: pfc_execute_command(command="ball create", params='{"number": 100}')

Would you like me to set this up for you?
"""
```

## Core Principles Summary

1. **Don't sacrifice LLM naturalness for human workflows** - Tool behavior must match LLM's intuitive mental model, not mimic specific human expert patterns
2. **Stateful tools + Explicit state management** - All simulation tools should persist state; provide dedicated tools (pfc_reset) for state control
3. **System Prompt > Tool Docs for workflow teaching** - Tool docs describe capabilities; System Prompt teaches expert workflows and tool orchestration
4. **Purpose, not state behavior, distinguishes tools** - Command (exploration) vs Script (production) differ in usage intent, both are stateful
5. **Gentle prompts > Complex concepts** - Guide LLM through natural language hints in tool responses ("Haven't saved state, need to?"), not abstract models
6. **State injection is the most critical context engineering technique** - For industrial software agents, state IS the context
7. **Abstraction layers hide chaos** - Industrial software has messy APIs; good adapter layers provide clean, consistent interfaces to LLM
8. **Data flow defines capability boundaries** - SDK returns values, commands don't - this determines tool purpose
9. **Industrial software agent's superpower: state management** - Understanding state evolution, not code architecture

### Tool Design Pattern: Simple Stateful Tools + Dedicated State Management

```python
# ✅ Good: Both tools are stateful, state management is separate
class CommandTool:
    """Stateful exploration tool - state persists"""
    async def execute(self, cmd: str) -> Result:
        result = await pfc_client.send(cmd)  # State persists in PFC
        return result  # Simple: execute and return

class ScriptTool:
    """Stateful production tool - state persists"""
    async def execute(self, script: str) -> Result:
        result = await pfc_client.send_script(script)  # State persists in PFC
        return result  # Simple: execute and return

class PFCResetTool:
    """Explicit state management - separate concern"""
    async def reset(self) -> Result:
        await pfc_client.send(cmd)("model new")  # Explicit reset
        return success_response("State reset to initial")

# State injection happens at response level, not tool level
def inject_state_context(result: Result) -> ContextualResult:
    """Separate component adds state info to response"""
    current_state = query_pfc_state()  # Query PFC for current state
    return {
        "result": result,
        "current_state": current_state,  # Injected for LLM awareness
        "suggested_actions": get_valid_next_actions(current_state)
    }


# ❌ Bad: Auto-rollback behavior (violates LLM naturalness)
class CommandTool:
    """Stateless with automatic rollback - CONFUSING"""
    async def execute(self, cmd: str) -> Result:
        snapshot = await pfc_client.save_state()  # Save state
        try:
            result = await pfc_client.send(cmd)  # Execute
            return result  # Return result
        finally:
            await pfc_client.restore_state(snapshot)  # ❌ Auto-rollback!
        # Problem: LLM expects "create ball" to create ball
        # But it's gone after function returns - counterintuitive!
```

### The State Injection Paradigm

**Core principle: Guide through gentle prompts, not complex concepts**

```python
# Traditional context engineering (for coding agents)
Context = Code Architecture + File Dependencies + Module Relationships
→ Large, static, spatial context

# State injection (for industrial software agents)
Context = Current State + Gentle Workflow Prompts + Next Action Hints
→ Small, dynamic, temporal context with natural guidance
```

**LLM-friendly guidance through tool responses:**

```python
# ✅ Good: Natural prompts in tool responses
# After command execution:
{
  "message": "Command executed: ball create number 100",
  "llm_content": {
    "text": """
    ✓ Created 100 balls successfully

    📊 Current state: 1100 balls, gravity 9.81

    💡 Gentle reminder: This command modified the state.
       If you want to make this permanent, consider:
       • Reading current state file to understand baseline
       • Writing updated script for production use
       • Or use pfc_reset if this was just a test
    """
  }
}

# Before script execution (if state may be unclear):
{
  "message": "About to execute script",
  "llm_content": {
    "text": """
    💡 Friendly heads-up: You're about to run a script.
       Have you checked the current state?
       • Read state file if you need to understand current baseline
       • Use pfc_reset if you want a clean start
       • Or proceed if you're confident about current state
    """
  }
}

# ❌ Bad: Complex dual-layer concepts
{
  "llm_content": {
    "baseline_state": {...},  # Too complex
    "test_overlay": {...},    # Too conceptual
    "current_state": {...}    # Cognitive overhead
  }
  # Problem: LLM has to understand abstract state model
  # Better: Just tell LLM what to do next in natural language
}
```

**Design philosophy:**

1. **Don't make LLM learn complex models** - Just guide naturally
2. **Prompt at decision points** - "Haven't saved state yet, need to?"
3. **Suggest concrete actions** - "Consider reading state file first"
4. **Natural language > Abstract concepts** - "This was a test, want to keep it?" vs "test overlay layer"

**Example workflow with gentle guidance:**

```python
# Step 1: LLM executes command
→ pfc_execute_command("ball create number 100")

Response: """
✓ Created 100 balls

💡 This was a test command. Want to:
   • pfc_reset (discard this test)
   • Write script (make it permanent)
   • Keep testing (add more commands)
"""

# Step 2: LLM wants to run script
→ pfc_execute_script("production_sim.py")

Response: """
💡 About to run production script.
   Current state has test changes from commands.
   Need to pfc_reset first for clean baseline?
"""

# Step 3: LLM makes informed choice naturally
→ pfc_reset()  # Based on gentle prompt, not complex model understanding
```

**Why this is better:**
- No complex "dual-layer" mental model needed
- Natural conversational guidance
- LLM learns through doing, not through theory
- Prompts appear exactly when needed (contextual)

**Why state injection is critical:**

1. **Scripts fail because of wrong state, not wrong code**
   - State validation prevents runtime failures
   - Pre-execution checks save hours of computation
   - Auto-setup enables seamless workflows

2. **State history is compact yet complete**
   - No need to understand entire project architecture
   - Execution sequence tells the whole story
   - Each script builds on previous state

3. **State requirements are inferrable**
   - Static analysis of scripts reveals dependencies
   - `itasca.ball.count()` → implies balls must exist
   - `model cycle` → implies model must be initialized

4. **State-aware tools enable confidence**
   - LLM knows: "Can I execute this script now?"
   - LLM knows: "What needs to happen first?"
   - LLM knows: "What state will this create?"

### Implementation Strategy for State Injection

```python
# Every tool response includes state context
{
    "status": "success",
    "message": "Command executed",
    "llm_content": {
        "parts": [{
            "type": "text",
            "text": """
            ✓ Command executed: ball create radius 1.0 number 100

            📊 Current State:
            • Model: Initialized (3D)
            • Gravity: 9.81 m/s²
            • Balls: 100
            • Walls: 0
            • Last action: Created 100 balls
            • Simulation cycles: 0

            ✓ Ready for: model cycle, model solve
            ⚠ Need setup for: wall operations (no walls)
            """
        }]
    },
    "state_snapshot": {
        "model_initialized": True,
        "ball_count": 100,
        "gravity_set": True,
        "cycles_run": 0
    }
}
```

**State injection at every interaction ensures:**
- LLM always knows current capabilities
- LLM can predict next valid operations
- LLM can prevent invalid operations before attempting
- User gets clear visibility into simulation progress

---

**Key Insight**: Don't get caught up in terminology boundaries. Build clear system layering. Whether it's called "context engineering" or "RAG" matters less than having a dynamic system that assembles everything the LLM needs.

**Practical engineering perspective > academic terminology debates** 🎯

## Project Direction: State Injection Context Engineering

### The Bridge Between User and Industrial Software

Through understanding **user experience** and **industrial software responses**, we have discovered how to design the bridge:

```
User Intent
    ↓
LLM Understanding
    ↓
State Injection ← The critical bridge
    ↓
PFC Commands/Scripts
    ↓
Simulation Results
```

### The Next Battle: State Injection Context Engineering

**Core challenge**: Make LLM state-aware at every interaction

**Implementation strategy**:

```python
# Every tool response must include state context
Tool Response = {
    "status": "success",
    "data": {...},
    "llm_content": {
        "current_state": {...},      # What is the state NOW?
        "state_history": [...],      # How did we get here?
        "next_valid_ops": [...],     # What can we do next?
        "blocked_ops": [...]         # What requires different state?
    }
}
```

### Implementation Roadmap

#### Phase 1: State Manager Foundation
**Goal**: Track simulation state across command and script executions

**Tasks**:
1. Implement `PFCStateManager` class
   - Track state history (command sequence)
   - Maintain current state snapshot
   - Parse script requirements

2. Integrate with existing tools
   - `pfc_execute_command` records state transitions
   - `pfc_execute_script` validates state preconditions

3. State snapshot mechanism
   - Query PFC for current state after each operation
   - Store: model_initialized, ball_count, wall_count, gravity, cycles_run

#### Phase 2: State Injection in Tool Responses
**Goal**: LLM receives state context with every response

**Tasks**:
1. Enhance `success_response()` to include state
   ```python
   success_response(
       message="...",
       llm_content={
           "text": "...",
           "state": state_manager.get_current_state(),
           "history": state_manager.get_state_history()
       }
   )
   ```

2. Design state presentation format
   - Human-readable state summary
   - Actionable next steps
   - Clear blocked operations

3. Test with LLM to validate understanding
   - Can LLM correctly interpret state?
   - Can LLM predict next valid operations?
   - Can LLM avoid invalid operations?

#### Phase 3: Script Precondition Checking
**Goal**: Scripts only execute when state is valid

**Tasks**:
1. Static analysis of script requirements
   - Parse script to extract state dependencies
   - Build requirement graph

2. Pre-execution validation
   - Check current state vs requirements
   - Generate setup suggestions if invalid

3. Auto-setup mode (optional)
   - Automatically run prerequisite commands
   - Bring simulation to required state
   - Then execute script

#### Phase 4: Validation → Codification → Execution Workflow
**Goal**: Streamline the three-phase workflow

**Tasks**:
1. Command history tracking
   - Record successful test commands
   - Offer to generate script from history

2. Script generation from validated commands
   ```python
   User: "These commands work, save them as a script"
   LLM: state_manager.suggest_script_from_tests()
   → Generates production script from test history
   ```

3. Workflow guidance
   - LLM suggests: "You've validated these, ready to codify?"
   - LLM warns: "This script needs state validation first"

#### Phase 5: Context Engineering Optimization
**Goal**: Minimize token usage while maximizing state awareness

**Tasks**:
1. Smart state summarization
   - Full history vs compact summary
   - Adaptive detail based on context

2. State diff instead of full snapshot
   - "Changed: ball_count 0 → 100"
   - More efficient than full state dump

3. Predictive state hints
   - "With current state, you can: cycle, solve"
   - "To create walls, you need: model initialized ✓"

### Success Metrics

**How do we know state injection is working?**

1. **LLM rarely executes invalid operations**
   - Before: 30%+ of script executions fail due to wrong state
   - After: <5% state-related failures

2. **LLM proactively suggests state setup**
   - "I notice the model isn't initialized, let me set that up first"

3. **Users trust script execution**
   - Scripts don't fail after hours of computation
   - State validation catches issues upfront

4. **Natural workflow progression**
   - Users test with commands
   - LLM suggests codifying to script
   - Scripts execute reliably

### Design Principles for Implementation

1. **State is not optional** - Every tool response includes state
2. **State is actionable** - Always tell LLM what they can/can't do
3. **State is compact** - Minimize tokens while maximizing information
4. **State is visual** - Use emojis/symbols for quick scanning
5. **State is predictive** - Show next valid operations, not just current

### Example Target Behavior

```python
User: "Create 100 balls and run a simulation"

# LLM understands current state is empty
LLM: "I need to set up the simulation first. Let me:
  1. Initialize model
  2. Set gravity
  3. Create 100 balls
  4. Run simulation cycles

Current state: ⚪ Empty
After setup:   🟢 Ready for simulation"

# Phase 1: Validation (commands)
→ pfc_execute_command(command="model new")
  State: 🔵 Model initialized

→ pfc_execute_command(command="model gravity", arg="9.81")
  State: 🔵 Model initialized, ⚙️ Gravity: 9.81

→ pfc_execute_command(command="ball create", params='{"number": 100}')
  State: 🔵 Model initialized, ⚙️ Gravity: 9.81, 🟢 Balls: 100

LLM: "Setup validated! These commands work.
Would you like me to save this as a script for future runs?"

User: "Yes"

# Phase 2: Codification (edit)
→ write_script("gravity_simulation.py", validated_commands)

# Phase 3: Execution (script)
LLM: "Script created. Running full simulation..."
→ pfc_execute_script("gravity_simulation.py")
  State: 🔵 Model initialized, ⚙️ Gravity: 9.81, 🟢 Balls: 100, ▶️ Cycles: 1000
```

### Key Insight Summary

**We discovered the bridge design through:**
- 👤 **User experience**: Command for testing → Script for production
- 🔧 **Industrial software response**: State evolution is the context
- 🤖 **LLM capability**: Can understand and manage state if injected properly

**The breakthrough**: State injection is not just logging - it's the primary context engineering technique that makes industrial software agents work.

---

*Generated: 2025-10-05*
*Project: aiNagisa - Voice-enabled AI Assistant with Industrial Software Control*
*Repository: <https://github.com/yusong652/aiNagisa>*
