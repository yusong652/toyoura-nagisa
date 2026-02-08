# pfc-mcp: Bridging Large Language Models and Discrete Element Simulation via the Model Context Protocol

**Target**: Computers and Geotechnics / ASCE Journal of Computing in Civil Engineering
**Status**: Draft outline v2
**Date**: 2026-02-08

---

## Positioning

This is the first system to integrate Large Language Models with Discrete Element Method simulation software. Not "AI-assisted" in the traditional surrogate-model sense — this is direct, interactive, bidirectional control of a professional DEM engine (ITASCA PFC) through natural language, enabled by the open Model Context Protocol (MCP) standard.

Prior work in "AI + geotechnics" has focused on surrogate models, constitutive model calibration, or image-based analysis. No existing work addresses the fundamental UX problem: **the interface between human intent and simulation execution**.

---

## Abstract (Draft)

Discrete Element Method (DEM) simulations are indispensable in geotechnical engineering, yet their adoption is constrained by the steep learning curve of professional software such as ITASCA PFC. This paper presents pfc-mcp, the first open-source system that enables Large Language Models (LLMs) to directly interact with a DEM simulation engine through the Model Context Protocol (MCP) standard. The system provides 10 MCP tools spanning documentation retrieval, script generation, task execution, real-time monitoring, and visual diagnostics — forming a complete AI-assisted simulation workflow. We identify five design principles critical to effective LLM-simulation integration: documentation-driven generation, multimodal diagnostic loops, progressive disclosure navigation, LLM-cognitive schema design, and iterative execution feedback. Through case studies on representative DEM tasks, we demonstrate how each principle addresses specific failure modes that arise when LLMs interact with domain-specific engineering software. The system is client-agnostic: any MCP-compatible AI application can serve as the user interface. pfc-mcp is publicly available and establishes a replicable architectural pattern for connecting LLMs to other computational mechanics software.

---

## 1. Introduction

### 1.1 The Interface Problem in Computational Geomechanics

- DEM is mature and powerful (Cundall & Strack, 1979; Potyondy & Cundall, 2004)
- ITASCA PFC: industry-standard, used in mining, tunneling, rock mechanics, granular flow
- But: steep learning curve — proprietary scripting language (FISH) + Python SDK + 128 commands + complex contact model configuration
- Typical onboarding: weeks to months for a new researcher
- This is not unique to PFC: FLAC3D, UDEC, ABAQUS, LAMMPS all share this pattern

### 1.2 The Gap in Current AI + Geotechnics Research

- Existing "AI in geomechanics" work focuses on:
  - Surrogate models replacing FEM/DEM (physics-informed neural networks, DeepONet)
  - ML-based constitutive models (GNN for granular materials)
  - Image/sensor data analysis (crack detection, site classification)
- These treat AI as a **replacement** for simulation
- Missing: AI as an **interface** to simulation — helping engineers use existing tools more effectively
- No prior work on LLM-driven simulation control in geotechnical engineering

### 1.3 The Model Context Protocol Opportunity

- MCP (Anthropic, 2024): open standard for LLM-tool integration
- Analogous to USB for peripherals — standardized protocol, any client, any server
- Rapidly adopted: Claude Desktop, Cursor, Windsurf, VS Code, custom agents
- Enables a new category: domain-specific MCP servers for professional software
- pfc-mcp is the first such server for computational mechanics

### 1.4 Contributions

1. **First LLM-DEM integration**: A complete system enabling natural language interaction with ITASCA PFC discrete element simulations
2. **Five design principles**: Identification and validation of design principles critical to effective LLM-simulation integration, demonstrated through failure-mode case studies
3. **MCP-based architecture**: Client-agnostic design via the open Model Context Protocol, decoupling AI interface from simulation engine
4. **Replicable pattern**: Architectural template applicable to other computational mechanics software (FLAC3D, UDEC, ABAQUS, LAMMPS)

---

## 2. System Architecture

### 2.1 Overview

```text
                    MCP Protocol (stdio/SSE)
                           |
 [Any MCP Client] <------> [pfc-mcp Server]
  Claude Desktop            |  10 MCP Tools
  Cursor                    |  Doc Retrieval Engine
  Custom Agent              |  Bridge Client
                            |
                    WebSocket (port 9001)
                            |
                     [pfc-bridge]
                      Running inside PFC GUI
                      Main-thread executor
                      Task lifecycle manager
                      Signal-based diagnostics
                            |
                     [ITASCA PFC Engine]
                      DEM Simulation Core
```

### 2.2 The Bridge Pattern

- **Problem**: PFC's Python SDK must execute on the GUI main thread. LLM tool calls are async and concurrent.
- **Solution**: pfc-bridge — a WebSocket server running inside PFC's embedded Python environment
  - Queue-based main-thread executor: all SDK calls marshalled to main thread
  - Task lifecycle manager: non-blocking submission, background execution, progress capture
  - Signal-based diagnostics: callback mechanism for non-blocking queries during simulation cycles
  - Real-time output streaming: stdout/stderr capture for progress monitoring

### 2.3 Tool Design

| Tool | Type | Purpose |
| ---- | ---- | ------- |
| `pfc_browse_commands` | Documentation | Navigate 128 PFC commands by category |
| `pfc_browse_python_api` | Documentation | Browse Python SDK (modules, objects, methods) |
| `pfc_browse_reference` | Documentation | Contact model properties, range filter syntax |
| `pfc_query_command` | Search | BM25 keyword search over command documentation |
| `pfc_query_python_api` | Search | BM25 keyword search over Python SDK |
| `pfc_execute_task` | Execution | Submit Python script for async execution |
| `pfc_check_task_status` | Monitoring | Query task progress with paginated output |
| `pfc_list_tasks` | Monitoring | List all tracked tasks with filtering |
| `pfc_interrupt_task` | Control | Request graceful interruption of running task |
| `pfc_capture_plot` | Visualization | Capture simulation state as image with configurable rendering |

---

## 3. Design Principles and Case Studies

This section presents five design principles for effective LLM-simulation integration. Each principle is motivated by a specific failure mode observed when LLMs interact with domain-specific engineering software, and validated through a concrete case study using ITASCA PFC.

### 3.1 Documentation-Driven Generation (D1)

**Principle**: Provide authoritative, structured documentation at runtime rather than relying on LLM pre-training knowledge or fine-tuning.

**Failure mode without D1**: LLMs have near-zero pre-training knowledge of PFC's proprietary command syntax and Python SDK. Without runtime documentation, the LLM hallucinates plausible but incorrect API names.

**Case study: Contact model configuration**

Task: "Set up a linear contact model with normal stiffness 1e5 and friction coefficient 0.5"

- **Without documentation tools**: The LLM generates `contact.set_property('stiffness_normal', 1e5)` and `contact.set_property('friction', 0.5)`. Both property names are wrong — PFC uses `kn` and `fric`. The script fails silently or raises an error.
- **With documentation tools**: The LLM calls `pfc_browse_reference(topic="contact-models linear")` and receives the complete property table with correct names (`kn`, `ks`, `fric`), units, types, and defaults. The generated script uses `contact cmat add model linear property kn 1e5 fric 0.5` — syntactically and semantically correct on the first attempt.

**Design implication**: The documentation must be structured for LLM consumption (not human browsing). Each property needs machine-readable name, type, unit, and default value, not prose descriptions.

### 3.2 Multimodal Diagnostic Loop (D2)

**Principle**: Provide visual diagnostic capabilities alongside textual output. Spatial and physical anomalies in DEM simulations are often invisible in text logs but immediately apparent in visualization.

**Failure mode without D2**: A simulation completes without errors, but produces physically meaningless results (particle interpenetration, explosive divergence, unrealistic force chains). Text-only monitoring reports "completed" with no indication of failure.

**Case study: Detecting particle divergence**

Task: Debug a simulation where particles are escaping the model domain after cycling.

- **Without visual diagnosis**: The agent calls `pfc_check_task_status`, sees `status=completed`, reads output log showing cycle count and timestep — everything appears normal. The agent reports success. Meanwhile, particles have flown through gaps in the wall geometry at high velocity.
- **With visual diagnosis**: The agent calls `pfc_capture_plot(ball_color_by="velocity")` and receives an image showing several particles colored bright red (high velocity) outside the expected domain boundaries. The agent immediately identifies the issue: incomplete wall enclosure. It queries `pfc_browse_commands(command="wall generate")` to find the correct wall creation syntax, generates a fix, and re-executes.

**Design implication**: `pfc_capture_plot` supports configurable color mapping (`velocity`, `displacement`, `force-contact`, `radius`, `group`) specifically to enable diagnostic reasoning. The tool returns MCP-native `ImageContent`, allowing multimodal LLMs to directly interpret the visualization.

### 3.3 Progressive Disclosure Navigation (D3)

**Principle**: Structure documentation in hierarchical navigation levels rather than flat search results. Present information progressively — overview first, details on demand — to match LLM context window constraints and reasoning patterns.

**Failure mode without D3**: Presenting all 128 commands at once overwhelms the LLM's context, leading to confusion between similar commands or selection of inappropriate alternatives.

**Case study: Choosing between `ball create` and `ball generate`**

Task: "Create a specimen of 10,000 particles in a cylindrical container"

- **Without progressive navigation (flat dump)**: The LLM receives all 128 commands. Both `ball create` (single ball, exact position) and `ball generate` (batch generation, random packing) appear in the list. The LLM might select `ball create` in a loop — technically possible but extremely slow and producing unrealistic uniform packing.
- **With progressive navigation**: The LLM calls `pfc_browse_commands(command="ball")`, sees 20 ball commands with one-line summaries. It identifies both `create` ("Create a single ball") and `generate` ("Generate non-overlapping balls") as candidates. It drills into `pfc_browse_commands(command="ball generate")` to read the full documentation including keywords for number, radius distribution, and spatial constraints. It correctly selects `ball generate` with appropriate parameters.

**Design implication**: Three-level navigation (root → category → command) mirrors how domain experts mentally organize PFC's API. Each level provides enough context to decide whether to drill deeper or pivot, without consuming excessive context tokens.

### 3.4 LLM-Cognitive Schema Design (D4)

**Principle**: Design tool parameter schemas (names, types, descriptions, defaults, units) to optimize LLM comprehension and correct invocation, not just API correctness.

**Failure mode without D4**: Parameters with missing descriptions, ambiguous names, or unintuitive units cause LLMs to either avoid using the parameter or pass incorrect values.

**Case study: Camera positioning for diagnostic capture**

Task: "Capture a top-down view of the particle assembly"

- **Without LLM-cognitive descriptions**: The `pfc_capture_plot` tool has parameters `eye` (type: `list[float]`) and `center` (type: `list[float]`) with no descriptions. The LLM does not understand that `eye` is the camera position in model coordinates. It either omits the parameter (getting a default oblique view) or passes semantically wrong values.
- **With LLM-cognitive descriptions**: `eye` has description `"Camera position in model coordinates [x, y, z]"` and `center` has `"Camera look-at point in model coordinates [x, y, z]"`. The LLM correctly infers that a top-down view requires `eye=[0, 0, 100]` (above the model) and `center=[0, 0, 0]` (looking at the origin).

**Additional examples of LLM-cognitive design choices**:
- `timeout` parameter uses seconds (not milliseconds) because LLMs naturally reason in human time units
- `ball_color_by` accepts aliases (`force_contact` and `force-contact` both work) because LLMs may generate either form
- Only `output_path` is required; all other parameters have sensible defaults, enabling minimal-parameter invocation
- Error responses include an `action` field with explicit next steps ("start pfc-bridge in PFC GUI, then retry")

**Design implication**: Every parameter description, default value, and unit choice is a communication decision with the LLM. Schema design is not an afterthought — it directly determines tool utilization rate and invocation correctness.

### 3.5 Iterative Execution Feedback (D5)

**Principle**: Enable the LLM to submit scripts, observe execution results (including errors), and iteratively correct its approach. First-attempt correctness is neither expected nor required; what matters is convergence.

**Failure mode without D5**: The LLM generates a script, has no way to verify it, and delivers it to the user as a final product. Errors are only discovered when the user manually runs the script in PFC.

**Case study: Missing model domain**

Task: "Create 50 balls with radius 0.5 in a 10x10x10 box"

- **Without execution feedback**: The LLM generates a script that creates balls with `ball create radius 0.5 position (...)` but omits the prerequisite `model domain extent -5 5 -5 5 -5 5`. The script is syntactically valid Python but will fail at runtime because PFC requires a domain to be defined before ball creation.
- **With execution feedback**:
  - **Turn 1**: LLM writes and submits the script via `pfc_execute_task`. Bridge returns error: "A model domain must be specified prior to ball creation."
  - **Turn 2**: LLM reads the error via `pfc_check_task_status`, queries `pfc_browse_commands(command="model domain")` to learn the syntax, prepends `model domain extent -5 5 -5 5 -5 5` to the script, and resubmits.
  - **Turn 3**: Execution succeeds. LLM verifies with `pfc_capture_plot` — 50 balls visible in the domain.

**Key metrics observable from D5**:

| Metric | Meaning |
| ------ | ------- |
| First-attempt success rate | Quality of documentation retrieval + LLM's prior knowledge |
| Convergence rate (within N turns) | Effectiveness of error feedback + LLM's debugging ability |
| Average turns to success | System efficiency for a given task difficulty |
| Non-convergent tasks | Current capability boundary of the system |

**Design implication**: The execution tools (`pfc_execute_task`, `pfc_check_task_status`) are not just "run buttons" — they form a feedback channel. Error messages from PFC are propagated verbatim to the LLM, enabling self-correction without human intervention.

---

## 4. Evaluation

### 4.1 Experimental Design

**Benchmark task set**: N representative PFC tasks across difficulty levels:

| Level | Description | Example |
| ----- | ----------- | ------- |
| L1 | Basic setup | Create domain + generate balls |
| L2 | Configuration | Set up contact model with specific properties |
| L3 | Boundary conditions | Create wall enclosure with servo control |
| L4 | Complete workflow | Biaxial compression test (prepare, consolidate, load) |
| L5 | Diagnosis | Identify and fix a physically incorrect simulation |

**Protocol**: For each task, an LLM agent with full pfc-mcp tools is given the task description and allowed up to N turns of autonomous interaction. All tool calls, generated scripts, and execution results are recorded.

**Metrics**:

- First-attempt success rate (S1: syntax, S2: PFC-executable, S3: physically correct)
- Convergence rate within N turns
- Average turns to convergence
- Tool utilization patterns (which tools used, in what order)
- Failure mode classification (documentation gap, hallucination, physical reasoning error)

**Cross-model comparison**: Same task set executed with multiple LLM providers (Claude, GPT-4o, Gemini) to assess model-independence of the architecture.

### 4.2 Design Principle Validation

Each case study from Section 3 serves as a controlled demonstration:

| Principle | Without | With | Observable difference |
| --------- | ------- | ---- | --------------------- |
| D1 Documentation-driven | Hallucinated property names | Correct properties from reference | Script correctness rate |
| D2 Multimodal diagnosis | "Completed" with hidden errors | Visual anomaly detection | Diagnosis success rate |
| D3 Progressive disclosure | Wrong command selection | Informed command selection | Appropriate tool usage |
| D4 Schema design | Parameters unused or misused | Correct parameter invocation | Tool invocation accuracy |
| D5 Execution feedback | Single-shot, errors undetected | Iterative convergence | Final success rate |

### 4.3 Documentation Retrieval Quality

- BM25 precision/recall on representative query set
- Query categories: exact command lookup, conceptual search, cross-domain queries
- Failure analysis: what types of queries produce noisy results

---

## 5. Discussion

### 5.1 Why MCP, Not Fine-Tuning?

- Fine-tuning requires training data, is model-specific, and becomes stale with software updates
- MCP provides real-time access to authoritative documentation
- Any model improvement automatically benefits all MCP users
- Zero marginal cost per new LLM provider
- MCP ecosystem is growing: tools built once are usable across all MCP-compatible clients

### 5.2 The "Script is Context" Philosophy

- Every AI-generated script is a reproducible artifact
- Simulation reproducibility is preserved: the LLM assists, but the script is the source of truth
- Engineers review and approve scripts before production use — AI as a drafting tool, not an autonomous executor

### 5.3 Limitations

- BM25 search has limited semantic understanding (natural language queries can return noisy results); hybrid search (BM25 + embedding) may improve quality
- No physics validation: LLM can generate syntactically correct but physically meaningless parameter combinations
- Visual diagnosis depends on multimodal LLM capability; text-only models cannot use D2
- Single-task execution model (PFC constraint, not architectural)
- Requires PFC license (pfc-mcp is open-source, PFC is commercial)

### 5.4 Generalization to Other Software

The five design principles and the three-layer architecture (documentation + bridge + MCP tools) are not PFC-specific:

| Software | Domain | Bridge challenge | Documentation scope |
| -------- | ------ | ---------------- | ------------------- |
| FLAC3D | Finite difference, continuum | Same ITASCA ecosystem, similar bridge | Different command set |
| UDEC / 3DEC | Discontinuum mechanics | Same ITASCA ecosystem | Different command set |
| ABAQUS | FEM, general purpose | Python scripting API, batch execution | Extensive keyword reference |
| LAMMPS | Molecular dynamics | Command-line driven, no GUI thread issue | Input script syntax |
| OpenFOAM | CFD | Dictionary-based configuration | Case setup conventions |

The key insight: the documentation curation effort (structuring domain knowledge for LLM consumption) is the hardest and most valuable part, not the bridge implementation.

---

## 6. Related Work

### 6.1 AI in Geotechnical Engineering

- Surrogate models for DEM (cite recent works)
- ML-based constitutive models
- Physics-informed neural networks for geomechanics
- **Gap**: All treat AI as replacement for simulation; none address AI as interface to simulation

### 6.2 LLM-Assisted Scientific Computing

- Code generation for numerical simulation (Codex, StarCoder)
- ChatGPT for MATLAB/Python scientific scripting
- LLM agents for laboratory automation (chemistry, biology)
- **Gap**: No work on LLM integration with commercial DEM/FEM software via standardized protocols

### 6.3 Tool-Augmented LLMs

- Function calling (OpenAI, 2023)
- Model Context Protocol (Anthropic, 2024)
- Domain-specific MCP servers (database, filesystem, web)
- **Gap**: No MCP server for computational mechanics

---

## 7. Conclusion

pfc-mcp demonstrates that the interface between engineers and simulation software is a tractable problem for LLM integration. Through five design principles — documentation-driven generation, multimodal diagnostic loops, progressive disclosure, LLM-cognitive schema design, and iterative execution feedback — we show how to build effective LLM-simulation integration that goes beyond naive "chatbot wrapper" approaches.

The system is the first of its kind in computational geomechanics. Its client-agnostic MCP architecture means that any AI application — from Claude Desktop to custom research agents — can serve as a natural language interface to ITASCA PFC, without fine-tuning, without vendor lock-in, and without sacrificing the reproducibility that scientific computing demands.

The architectural pattern and design principles established here provide a template for bringing LLM accessibility to the broader landscape of professional engineering software — wherever the gap between human intent and software capability remains a bottleneck.

---

## Key Figures (Planned)

1. **System architecture diagram** — MCP client <-> pfc-mcp <-> pfc-bridge <-> PFC engine
2. **Design principle overview** — D1-D5 with failure modes and solutions
3. **Case study: D1** — Without/with documentation, showing property name hallucination vs correct retrieval
4. **Case study: D2** — Diagnostic plot showing particle divergence (velocity-colored), agent reasoning
5. **Case study: D3** — Three-level navigation trace: root -> ball -> generate
6. **Case study: D4** — Schema comparison: before/after description addition, invocation accuracy
7. **Case study: D5** — Iterative convergence trace: error -> fix -> success over 3 turns
8. **Cross-model comparison** — Success rates across LLM providers on benchmark tasks
9. **Tool utilization patterns** — Which tools are called, in what sequence, for different task types

---

## Writing Notes

- The paper's core contribution is the five design principles, not the system itself — the system is the evidence
- Each principle follows the pattern: failure mode -> design decision -> case study -> implication
- Emphasize "first" positioning clearly but professionally — cite exhaustively to prove no prior work exists
- Avoid "AI replaces engineers" framing — this is "AI augments engineers' access to their own tools"
- Keep the paper accessible to geotechnical audience: they care about "can I use this for my next project?", not about transformer architectures
- The MCP standard is key differentiator: not a one-off hack, but a standards-based integration that benefits from ecosystem growth
- For evaluation, the agentic loop with execution feedback IS the experiment — record tool calls, convergence behavior, failure modes
