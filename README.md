
<p align="center">
  <img src="./packages/web/public/readme_header.png" alt="toyoura-nagisa - LLM-Driven PFC Simulation Assistant with Script is Context Philosophy" width="900"/>
</p>

<p align="center">
  <a href="https://github.com/yusong652/toyoura-nagisa/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-GPL%20v3-blue.svg" alt="License">
  </a>
  <a href="https://github.com/yusong652/toyoura-nagisa/pulls">
    <img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome">
  </a>
</p>

---

## 💡 Script is Context

**Toyoura Nagisa** demonstrates context engineering for LLM-driven discrete element simulations.

Traditional DEM workflows involve repetitive cycles: searching documentation, comparing command syntax with Python APIs, and manually debugging scripts. We automate this: the LLM navigates documentation, understands command-API tradeoffs, generates tested code, and iterates until success.

Every script execution creates a git snapshot with full workspace state. The LLM queries task history, reviews previous approaches, and builds upon past work—forming persistent cross-session context that survives restarts and spans projects.

Scripts *are* the context. Each execution compounds understanding.

## 🎯 Core Features

### 🔬 **Documentation-Driven Workflow**

The LLM doesn't guess - it queries, navigates, and discovers:

1. **Query by Keywords** - Search returns documentation paths, not raw content
2. **Browse by Path** - Navigate to specific docs, or explore parent directories to discover alternatives
3. **Write Test Script** - Small-scale validation (10 particles, 100 steps)
4. **Execute Production Script** - Full simulation with progress monitoring

**Example Workflow**:
```
User: "Create a ball settling simulation with 1000 particles"

toyoura-nagisa:
1. Queries 'ball generate' → returns path: "ball generate"
2. Browses "ball generate" → learns syntax, sees [no Python API]
3. Queries 'gravity' → returns path: "model gravity"
4. Browses "model gravity" → learns scripting pattern
5. Writes test script (10 particles) → validates approach
6. Executes production (1000 particles) → monitors progress
```

**Boundary Discovery**:
```
User: "Create walls around the domain"

toyoura-nagisa:
1. Queries "wall create" → returns path: "wall create"
2. Browses "wall create" → sees [no Python API]
3. Browses "itasca.wall" → confirms: only find/list/count, no create
4. Decision: uses itasca.command("wall create ...") wrapper
```

**Manual Implementation**:
```
User: "Apply confining pressure to cylindrical boundary"

toyoura-nagisa:
1. Queries "servo" → finds servo command
2. Browses "wall servo" → sees limitation: single force direction only
3. Browses "itasca.wall.Wall" → finds set_vel(), contact force methods
4. Decision: implements custom radial pressure control loop
```

### ⚡ **Task Lifecycle Management**

Long-running PFC simulations require monitoring, control, and learning from history.

**Session 1: Compression Test**

```
User: "Run isotropic compression to 100kPa confining pressure"

toyoura-nagisa:
1. Submit: pfc_execute_task → script includes termination condition
2. Monitor: pfc_check_task_status → tracks progress
   - "Compression cycles: 50000, stress: 95kPa"
   - "Target reached, saving checkpoint..."
3. Result: Task completed normally
4. (If instability detected: pfc_interrupt_task → stop and adjust)
```

**Session 2: Shear Test**

```
User: "Run triaxial shear test on the consolidated sample"

toyoura-nagisa:
1. Checks pfc_list_tasks → sees "Isotropic compression" completed
2. Checks pfc_check_task_status → reviews final output
   - Checkpoint: "consolidated_100kPa.sav"
   - Wall IDs: top_wall=1, bottom_wall=2
3. Reviews compression script → servo settings, contact model
4. Writes shear script:
   - model restore "consolidated_100kPa.sav"
   - References wall IDs for axial loading
```

**Session N: Learn from Failure**

```
Previous shear test failed with instability...

toyoura-nagisa:
1. Checks pfc_list_tasks → finds similar shear tasks
2. Compares outputs: successful runs vs failed runs
3. Reviews scripts: identifies parameter differences
4. Applies working approach to complete the task
```

Every execution—success or failure—becomes context for future decisions.

### 🤖 **SubAgent Delegation**

The main agent can delegate exploration tasks to a specialized SubAgent:

**PFC Explorer**: Queries command documentation, searches Python API examples, explores project history for successful patterns, and searches the web for references—all without consuming the main agent's context window.

## 🎨 Additional Features

Beyond the core PFC integration, toyoura-nagisa includes:

- **Multi-Provider LLM Support** - Gemini, Claude, OpenAI, Zhipu, Moonshot, OpenRouter, vLLM, Ollama
- **Long-Term Memory** (ChromaDB) - Learns user preferences across sessions
- **Live2D Character** - Interactive visual companion that responds to conversations
- **Text-to-Speech** - Local (GPT-SoVITS) or cloud (Fish Audio) voice output

## 🚀 Getting Started

### Prerequisites

**toyoura-nagisa Backend:**
- **Python 3.10+** with `uv` package manager ([install guide](https://github.com/astral-sh/uv))
- **Node.js 18+** - For frontend development

**PFC Integration (Core Feature):**
- **ITASCA PFC** with embedded Python environment
- **websockets==9.1** - Install in PFC's Python 3.6 environment:
  ```python
  # In PFC GUI IPython console
  import subprocess
  subprocess.call(['pip', 'install', '--user', 'websockets==9.1'])
  ```
  Or use command line with `--user` flag:
  ```bash
  pip install --user websockets==9.1
  ```

### Quick Start

```bash
# Clone and install
git clone https://github.com/yusong652/toyoura-nagisa.git
cd toyoura-nagisa
npm install && uv sync

# Configure
cp -r packages/backend/config_example/ packages/backend/config/
# Edit packages/backend/config/llm.py with your API keys

# Start
npm run dev:backend   # Backend API (localhost:8000)
npm run dev:web       # Web Frontend (localhost:5173)
npm run dev:cli       # CLI interface
```

### PFC Workspace Setup

For ITASCA PFC discrete element simulations:

```bash
# 1. Install websockets in PFC's Python environment
pip install websockets==9.1

# 2. Start PFC WebSocket server in PFC IPython shell
import sys
sys.path.append(r'/path/to/toyoura-nagisa/services/pfc-server')
exec(open(r'/path/to/toyoura-nagisa/services/pfc-server/start_server.py', encoding='utf-8').read())

# 3. In toyoura-nagisa, select "PFC Expert" agent profile
# 4. Interact with PFC through natural language
```

**PFC Workflow Example**:

```
You: "Create a ball settling simulation with 1000 particles"

Nagisa:
1. Queries command documentation for 'ball generate', 'model gravity', etc.
2. Writes test script with 10 particles (small scale)
3. Executes test → validates syntax
4. Writes production script with 1000 particles
5. Executes production (run_in_background=True) → returns task_id + git commit
6. Monitors progress with pfc_check_task_status(task_id)
7. Reports results

You: "Stop the simulation, I need to adjust parameters"
Nagisa: pfc_interrupt_task("a1b2c3d4") → task gracefully interrupted

You: "Show me only error messages from the last run"
Nagisa: pfc_check_task_status(task_id, filter="Error") → filtered output
```

See `services/pfc-server/README.md` for detailed setup and usage instructions.

## 🤝 Contributing

We are exploring how LLMs can control complex industrial software through documentation-driven workflows. If you work with specialized scientific or engineering tools (CAD, FEA, CFD, etc.), your insights are valuable.

**High-Priority Contributions:**
- **Industrial Software Integrations**: Extend the "Script is Context" pattern to other specialized tools
- **PFC Workflow Improvements**: Enhanced error handling, better progress monitoring, smarter documentation queries
- **Documentation System**: Expand command documentation coverage and API examples

**General Contributions:**
- **Agent Profile System**: New profiles for domain-specific tool sets
- **LLM Provider Support**: Additional providers and optimization strategies
- **Frontend UX**: Better visualization of simulation progress and tool usage

Please check out `CLAUDE.md` for development setup and architecture documentation.

## 📄 License

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](LICENSE) file for details.
