
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

*Capability guides action, limitation guides creation.*

Documentation tools guide script generation by providing verified syntax and usage patterns. The agent queries for relevant paths, browses for syntax, and discovers capability boundaries—revealing where to use built-ins and where to innovate.

### ⚡ **Adaptive Simulation Control**

The agent maintains complete control over simulation lifecycle. It submits scripts, monitors real-time progress, analyzes intermediate results, and decides autonomously when to continue, when to interrupt, and when to restart with adjustments.

```
Submit → Monitor → Analyze → Decide (continue | interrupt | restart)
```

### 🔍 **Multimodal Diagnostics**

*Qualitative is radar, quantitative is microscope.*

The agent captures visual output during simulation cycles—particle configurations, velocity arrows, contact force chains, cross-sections. Visual patterns reveal where to look; task output data confirms what's wrong.

### 🤖 **SubAgent Delegation**

Complex explorations risk context window exhaustion and hallucination. SubAgents solve both:

- **Context Isolation**: SubAgent exploration doesn't consume MainAgent's context window
- **Structured Results**: Only verified findings return to MainAgent—no intermediate noise
- **Read-Only Safety**: SubAgents cannot execute simulations or modify files

- **PFC Explorer**: Documentation queries, API exploration, project history search
- **PFC Diagnostic**: Multimodal visual analysis, task output correlation, structured diagnosis

The MainAgent stays focused on decision-making while SubAgents handle deep exploration.

### 📚 **Extensible Skills**

*Teach once, reuse forever.*

Skills are structured guides that encode domain expertise. The agent follows them step-by-step, handling complex workflows you'd otherwise explain repeatedly. Don't know how to set up pfc-server? The `pfc-server-setup` skill walks the agent through environment verification, dependency installation, and server launch.

Define your own skills to capture simulation workflows, analysis pipelines, or project-specific conventions. Your expertise becomes reusable agent knowledge.

### 🤝 **Intent Awareness**

*Your scripts are context too.*

- **PFC Console** (`>`): Direct access to PFC's Python environment. Edit scripts, import modules, run experiments. Each execution becomes a tracked task with background support. You stay in control.
- **Terminal** (`!`): Bash commands and outputs flow into agent context automatically.
- **File mentions** (`@`): Reference any file inline; content is injected on the fly.

The agent sees what you did, no explanation needed.

## 🎨 Additional Features

Beyond the core PFC integration, toyoura-nagisa includes:

- **Multi-Provider LLM Support** - Gemini, Claude, OpenAI, Zhipu, Moonshot, OpenRouter, vLLM, Ollama
- **Long-Term Memory** (ChromaDB) - Learns user preferences across sessions
- **Live2D Character** - Interactive visual companion that responds to conversations
- **Text-to-Speech** - Local (GPT-SoVITS) or cloud (Fish Audio) voice output

## 🚀 Quick Start

**Requirements**: Python 3.10+ with [uv](https://github.com/astral-sh/uv), Node.js 18+

```bash
# Clone the repository
git clone https://github.com/yusong652/toyoura-nagisa.git
cd toyoura-nagisa

# Install dependencies
npm install           # Frontend packages (workspaces)
uv sync               # Python backend

# Build all packages (required for first run)
npm run build:all

# Configure
cp -r packages/backend/config_example/ packages/backend/config/
# Edit packages/backend/config/llm.py with your API keys

# Start
npm run dev:backend   # Backend API (localhost:8000)
npm run dev:cli       # CLI (or npm run dev:web for Web UI)
```

### PFC Integration

For ITASCA PFC simulations:

1. **Ask Nagisa**: Just say "help me start PFC" and the agent handles environment setup, dependency installation, and server launch.

2. **Manual start**: In PFC GUI IPython console:
   ```python
   %run /path/to/toyoura-nagisa/services/pfc-server/start_server.py
   ```

See `services/pfc-server/README.md` for detailed setup.

## 🤝 Contributing

1. **Open an issue first** - Discuss your idea before implementing
2. **Fork & PR** - Fork the repo, create a branch, submit PR
3. **Keep PRs focused** - One feature or fix per PR

## 📄 License

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](LICENSE) file for details.
