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

### The Stateless vs Stateful Design Principle

**Key insight**: Command should be **stateless** to enable true validation sandbox behavior.

#### Command Execution Flow (Stateless - Returns to Initial State)

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
Return to Initial State ← KEY: Command doesn't persist changes in session
 ↓
Return Result
 ↓
Backend → LLM
 ↓
LLM decides next action
```

**Critical behavior**: Command execution is **transactional and ephemeral**:
- Execute command in PFC
- Observe result (success/error)
- **Return PFC to initial state** (rollback changes)
- Report result to LLM
- LLM uses result to decide next step

**Why return to initial state?**
1. **True validation sandbox**: Test without side effects
2. **Repeatable experiments**: Can test same command multiple times
3. **No state pollution**: Each command starts from clean slate
4. **Safe exploration**: Mistakes don't accumulate

#### Script Execution Flow (Stateful - Persists Changes)

```
LLM
 ↓
pfc_execute_script (MCP Tool)
 ↓
State Manager: Check preconditions
 ↓ (if valid)
Backend (aiNagisa)
 ↓
WebSocket → PFC Server
 ↓
Execute PFC Script
 ↓
Success or Error
 ↓
Persist State Changes ← KEY: Script commits changes
 ↓
Update State Snapshot
 ↓
Return Result
 ↓
Backend → State Manager → LLM
```

**Critical behavior**: Script execution is **persistent and stateful**:
- Validate state preconditions first
- Execute script in PFC
- **Commit all changes** (persist state)
- Update state tracking
- Report result with new state

#### Comparison: Command vs Script Execution

| Aspect | Command (Stateless) | Script (Stateful) |
|--------|---------------------|-------------------|
| **State changes** | Rollback (return to initial) | Commit (persist changes) |
| **Purpose** | Validation testing | Production execution |
| **Repeatability** | Always from same state | Builds on previous state |
| **Failure impact** | No lasting effect | Changes may persist |
| **LLM workflow** | Test → decide | Validate → execute |

```python
# Command: Stateless (ephemeral, disposable)
pfc_execute_command(command="ball create", params='{"number": 100}')
→ Executes in current PFC state
→ Returns: "Created 100 balls"
→ Does NOT track: "I created balls for this session"
→ State changes in PFC, but command itself is stateless

# Script: Stateful (persistent, tracked)
pfc_execute_script(script_path="simulation.py")
→ Checks preconditions against tracked state
→ Records execution in state history
→ Updates state snapshot
→ State-aware execution with guarantees
```

**Why this matters**:

1. **Command = Pure Function with Rollback**
   ```python
   # Stateless: same inputs → same behavior (always from initial state)
   command(cmd="model gravity", arg="9.81")
   # Executes in PFC
   # Returns result
   # PFC state rolls back to initial
   # No memory of previous commands
   # No session tracking
   # Just: "try this operation and report result, then rollback"

   # Example workflow:
   initial_state = get_pfc_state()  # Empty simulation

   command(cmd="ball create", params='{"number": 100}')
   # → PFC creates 100 balls
   # → Reports: "Created 100 balls"
   # → PFC rolls back to initial_state (0 balls)

   command(cmd="ball create", params='{"number": 200}')
   # → PFC creates 200 balls (starting from 0 again!)
   # → Reports: "Created 200 balls"
   # → PFC rolls back to initial_state (0 balls)

   # Both commands start from same state - true sandbox
   ```

2. **Script = Stateful Process with Commit**
   ```python
   # Stateful: maintains execution context and persists changes
   script(path="sim.py")
   # Executes in PFC
   # Changes PERSIST (commit, not rollback)
   # Remembers: what scripts ran before
   # Tracks: state evolution
   # Validates: preconditions based on history

   # Example workflow:
   initial_state = get_pfc_state()  # Empty simulation

   script(path="create_100_balls.py")
   # → PFC creates 100 balls
   # → Changes COMMIT (persist)
   # → new_state: {balls: 100}

   script(path="create_200_more_balls.py")
   # → Starts from new_state (100 balls already exist)
   # → PFC creates 200 more balls
   # → Changes COMMIT (persist)
   # → new_state: {balls: 300}

   # Scripts build on each other - stateful progression
   ```

3. **Separation of Concerns**
   ```
   Command Tool (stateless + rollback) → Sandbox testing, no side effects
   State Manager (stateful)            → Context tracking, state injection
   Script Tool (stateful + commit)     → Production execution, state evolution
   ```

4. **The Rollback vs Commit Pattern**
   ```python
   # Command: Transactional execution with rollback
   def execute_command(cmd):
       snapshot = pfc.save_state()        # Save current state
       try:
           result = pfc.execute(cmd)      # Execute command
           return result                   # Return result
       finally:
           pfc.restore_state(snapshot)    # ALWAYS rollback

   # Script: Persistent execution with commit
   def execute_script(script):
       if not validate_preconditions(script):
           raise StateError("Preconditions not met")

       result = pfc.execute(script)       # Execute script
       state_manager.commit(result)       # COMMIT changes
       return result
   ```

**Why this is true orthogonality:**

1. **Non-overlapping concerns**:
   - Command: State capability testing (ephemeral)
   - Edit: Knowledge preservation (persistent)
   - Script: Workflow execution (productive)

2. **Sequential dependency**:
   ```
   Command → discovers what works
   Edit    → codifies what works
   Script  → executes what works
   ```

3. **Different failure modes**:
   - Command fails → "This parameter/state doesn't work, try another"
   - Edit fails → "File system issue"
   - Script fails → "State preconditions not met" (should rarely happen if validated)

4. **Like Coding Agent's workflow**:
   ```
   # Coding Agent
   Read   → Understand current code
   Edit   → Modify code
   Test   → Validate changes

   # Industrial Software Agent
   Command → Validate state operations
   Edit    → Codify validated operations
   Script  → Execute codified workflow
   ```

### State Manager Integration

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

1. **State injection is the most critical context engineering technique** - For industrial software agents, state IS the context
2. **Command tools should be stateless** - Validation sandbox, not state tracker; complexity lives in State Manager
3. **Script tools should be stateful** - Production execution requires state awareness and guarantees
4. **Chaos is the norm** - Good abstraction layers beat expecting standard interfaces
5. **Data flow is key** - SDK returns values, commands don't - this defines capability boundaries
6. **LLM should generate code, not call commands directly** - Code is documentation, reusable and auditable
7. **Tool design: quantity ≠ capability, consistency > flexibility**
8. **Industrial software agent's superpower: state management, not architecture understanding**

### Stateless vs Stateful Design Pattern

```python
# ✅ Good: Separate concerns
class CommandTool:
    """Stateless - pure execution"""
    async def execute(self, cmd: str) -> Result:
        return await pfc_client.send(cmd)  # No state tracking

class StateManager:
    """Stateful - context management"""
    def observe_result(self, result: Result):
        self.history.append(result)  # Track state
        self.current_state.update(result)  # Update snapshot

    def inject_context(self, result: Result) -> ContextualResult:
        return {
            "result": result,
            "state": self.current_state,
            "history": self.history
        }

class ScriptTool:
    """Stateful - validated execution"""
    async def execute(self, script: str) -> Result:
        # Uses StateManager for precondition checking
        if not state_manager.validate_preconditions(script):
            raise StateError("Preconditions not met")
        return await pfc_client.send_script(script)


# ❌ Bad: Mixed concerns
class CommandTool:
    """Stateful command - confuses validation with tracking"""
    def __init__(self):
        self.history = []  # ❌ Why does validation need history?
        self.state = {}    # ❌ Why does validation need state?

    async def execute(self, cmd: str) -> Result:
        result = await pfc_client.send(cmd)
        self.history.append(result)  # ❌ Validation shouldn't track
        self.state.update(result)    # ❌ Validation shouldn't persist
        return result
```

### The State Injection Paradigm

```python
# Traditional context engineering (for coding agents)
Context = Code Architecture + File Dependencies + Module Relationships
→ Large, static, spatial context

# State injection (for industrial software agents)
Context = Current State + State History + State Requirements + State Transitions
→ Small, dynamic, temporal context
```

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
