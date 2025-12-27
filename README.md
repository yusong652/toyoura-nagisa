
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

Simulation software comes with extensive documentation. The agent doesn't guess—it queries and browses documentation hierarchies to discover:

- **What exists**: Available features and their usage patterns
- **What's missing**: Gaps that require workarounds
- **What's limited**: Built-in features that don't fully cover the use case

**Discovery Flow**

```
├─ Query       → keyword search returns documentation paths
├─ Browse      → navigate hierarchy, see available options
├─ Discover    → identify gaps and limitations
└─ Decide      → use built-in features vs implement custom solutions
```

### ⚡ **Adaptive Simulation Control**

The agent maintains full control over simulation execution through deep backend integration.

**Autonomous Control Loop**

```
├─ Submit      → pfc_execute_task(compression_script)
├─ Monitor     → pfc_check_task_status → "Cycle 50000: stress=98kPa"
├─ Analyze     → bash/read → parse output files, extract metrics
├─ Diagnose    → pfc_capture_plot → verify uniform stress distribution
├─ Complete    → Task finished, checkpoint saved
├─ Submit      → pfc_execute_task(shear_script)  ← starts new task
├─ Monitor     → pfc_check_task_status → "Strain: 2.1%, peak approaching"
├─ Interrupt   → Detects instability → stops execution
└─ Restart     → pfc_execute_task(adjusted_script) ← restarts with fixes
```

The agent decides when to continue, when to stop, and when to restart—without user intervention.

### 🤖 **SubAgent Delegation**

Complex explorations risk context window exhaustion and hallucination. SubAgents solve both:

- **Context Isolation**: SubAgent exploration doesn't consume MainAgent's context window
- **Structured Results**: Only verified findings return to MainAgent—no intermediate noise
- **Read-Only Safety**: SubAgents cannot execute simulations or modify files

- **PFC Explorer**: Documentation queries, API exploration, project history search
- **PFC Diagnostic**: Multimodal visual analysis, task output correlation, structured diagnosis

The MainAgent stays focused on decision-making while SubAgents handle deep exploration.

### 🤝 **Intent Awareness**

User operations automatically become agent context:

- **Terminal commands**: Bash operations visible to agent without copy-paste
- **Console execution**: PFC IPython operations persist as tracked tasks—user scripts are context too
- **File mentions**: `@file` syntax injects file content inline

Scripts *are* the context—yours included. The agent sees what you did, no explanation needed.

## 🎨 Additional Features

Beyond the core PFC integration, toyoura-nagisa includes:

- **Multi-Provider LLM Support** - Gemini, Claude, OpenAI, Zhipu, Moonshot, OpenRouter, vLLM, Ollama
- **Long-Term Memory** (ChromaDB) - Learns user preferences across sessions
- **Live2D Character** - Interactive visual companion that responds to conversations
- **Text-to-Speech** - Local (GPT-SoVITS) or cloud (Fish Audio) voice output

## 🚀 Quick Start

**Requirements**: Python 3.10+ with [uv](https://github.com/astral-sh/uv), Node.js 18+

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
npm run dev:cli       # CLI (or npm run dev:web for Web UI)
```

### PFC Integration

For ITASCA PFC simulations, install `websockets==9.1` in PFC's Python environment, then start the server in PFC GUI:

```python
exec(open(r'/path/to/toyoura-nagisa/services/pfc-server/start_server.py', encoding='utf-8').read())
```

See `services/pfc-server/README.md` for detailed setup.

## 🤝 Contributing

1. **Open an issue first** - Discuss your idea before implementing
2. **Fork & PR** - Fork the repo, create a branch, submit PR
3. **Keep PRs focused** - One feature or fix per PR

## 📄 License

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](LICENSE) file for details.
