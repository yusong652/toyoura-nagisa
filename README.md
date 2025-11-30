
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

**Toyoura Nagisa** pioneers context engineering for LLM-driven discrete element simulations. Every PFC operation becomes a versioned Python script—queryable through git history and task lists, forming persistent cross-session context that the LLM learns from.

Traditional simulation tools demand users memorize syntax. We invert this: scripts *are* the context. The LLM queries documentation, generates tested code, and builds understanding from execution history—elegant context engineering at scale.

## 🎯 Core Features

### 🔬 **Documentation-Driven Workflow**

The LLM doesn't guess - it queries before acting:

1. **Query Command Documentation** - Get syntax, parameters, and usage examples
2. **Query Python API** - Understand how to script PFC commands properly
3. **Write Test Script** - Small-scale validation (10 particles, 100 steps)
4. **Execute Production Script** - Full simulation with progress monitoring

**Example Workflow**:
```
User: "Create a ball settling simulation with 1000 particles"

toyoura-nagisa:
1. Queries 'ball generate' documentation → learns syntax
2. Queries 'model gravity' API → understands scripting
3. Writes test script (10 particles) → validates approach
4. Executes test → catches errors early
5. Writes production script (1000 particles) → runs full simulation
6. Monitors progress → reports results
```

### 🧠 **Agent Profile System**

Different tasks need different tools. toyoura-nagisa loads tool categories based on agent profiles:

| Profile | Tools | Token Usage | Purpose |
|---------|-------|-------------|---------|
| **PFC Expert** | 14 tools | 3,948 tokens | PFC simulation control |
| **Coding** | 10 tools | 2,820 tokens | Software development |
| **General** | 27 tools | 7,614 tokens | Multi-domain tasks |
| **Lifestyle** | 14 tools | 3,948 tokens | Email, calendar, contacts |

**PFC Expert Tools**: Documentation query, script execution, progress monitoring, task status tracking

### ⚡ **Real-Time WebSocket Integration**

Production-grade architecture solving industrial software integration challenges:

- **Thread-Safe Execution**: Queue-based main thread coordination for PFC SDK callbacks
- **Background Task Management**: Long-running simulations don't block user interactions
- **Progress Monitoring**: Real-time output capture from running simulations
- **Auto-Reconnection**: Resilient WebSocket client with exponential backoff

### 🗣️ **Multi-Provider LLM Support**

Unified architecture with pluggable LLM providers:

**Cloud Providers:**
- **Google Gemini** - Fast, cost-effective, excellent tool calling
- **Anthropic Claude** - Superior reasoning for complex workflows
- **OpenAI GPT** - Reliable general-purpose performance
- **Moonshot Kimi** - Chinese language optimization with competitive pricing
- **OpenRouter** - Access to multiple models through unified API

**Self-Hosted:**
- **vLLM** - High-throughput inference server for local deployments
- **Ollama** - Easy local model management and deployment

All providers share the same tool orchestration engine and conversation management, allowing seamless switching without code changes.

## 🎨 Additional Features

Beyond the core PFC integration, toyoura-nagisa includes:

- **Long-Term Memory** (Mem0 + ChromaDB) - Learns user preferences across sessions
- **Live2D Character** - Interactive visual companion that responds to conversations
- **Voice Input** - Natural speech interaction through the frontend
- **Text-to-Speech** - Local (GPT-SoVITS) or cloud (Fish Audio) voice output
- **Clean Architecture** - Strict separation of presentation/domain/infrastructure layers

## 🛠️ Technical Deep Dive

### System Architecture

```
+------------------------------------------------+
|                 Frontend (React)               |
| (Live2D, Chat UI, Geolocation, Voice Input)    |
+----------------------+-------------------------+
                       | (WebSocket / HTTP)
+----------------------v-------------------------+
|              Backend (Clean Architecture)       |
| +------------------+  +----------------------+ |
| |  Presentation    |  |      Domain          | |
| | (API, WebSocket) |  |  (Business Logic)    | |
| +------------------+  +----------------------+ |
|                      |                         |
| +--------------------v-----------------------+ |
| |            Infrastructure Layer            | |
| | +----------------+  +--------------------+ | |
| | |  Unified LLM   |  |   Tool Execution   | | |
| | |  Base Client   |  |       (MCP)        | | |
| | +----------------+  +--------------------+ | |
| | +----------------+  +--------------------+ | |
| | | Agent Profile  |  |  Mem0 Memory Mgmt  | | |
| | |    System      |  | (ChromaDB/Qdrant)  | | |
| | +----------------+  +--------------------+ | |
| | +----------------+  +--------------------+ | |
| | |  PFC WebSocket |  |   PFC Tools (MCP)  | | |
| | |     Client     |  | (Command/Script)   | | |
| | +----------------+  +--------------------+ | |
| +------------------------------------------+ |
+-------------+----------------------------------+
              | (WebSocket: ws://localhost:9001)
+-------------v----------------------------------+
|        PFC Workspace (External Process)        |
|  WebSocket Server + Task Manager + Executor    |
|         ITASCA PFC SDK (Main Thread)           |
+------------------------------------------------+
```

### Project Structure (Monorepo Architecture)

```
toyoura-nagisa/
├── packages/
│   ├── backend/                   # Python backend (FastAPI)
│   │   ├── app.py                 # FastAPI application entrypoint
│   │   ├── presentation/          # Presentation Layer
│   │   │   ├── api/               # REST API endpoints
│   │   │   └── websocket/         # WebSocket connection management
│   │   ├── domain/                # Domain Layer
│   │   │   └── models/            # Core business logic and message models
│   │   ├── infrastructure/        # Infrastructure Layer
│   │   │   ├── llm/               # Multi-provider LLM architecture
│   │   │   │   ├── base/          # Unified LLM base classes
│   │   │   │   └── providers/     # Provider implementations (gemini, anthropic, openai, local)
│   │   │   ├── mcp/               # Tool Execution (MCP)
│   │   │   │   ├── smart_mcp_server.py # Main MCP server
│   │   │   │   ├── tool_profile_manager.py # Agent profile management
│   │   │   │   └── tools/         # Tool implementations by category
│   │   │   ├── pfc/               # PFC WebSocket client integration
│   │   │   ├── memory/            # Long-term memory system (ChromaDB)
│   │   │   └── tts/               # Text-to-speech engines
│   │   └── config/                # Configuration management
│   ├── web/                       # React web frontend
│   │   ├── src/
│   │   │   ├── App.tsx            # Main React application
│   │   │   ├── components/        # UI components (ChatBox, Live2DCanvas, etc.)
│   │   │   └── contexts/          # React contexts for state management
│   │   └── public/
│   │       └── live2d_models/     # Live2D model files
│   ├── cli/                       # Terminal CLI frontend (Ink/React)
│   │   └── src/
│   │       └── ui/                # CLI components and hooks
│   └── core/                      # Shared TypeScript core library
│       └── src/
│           ├── connection/        # WebSocket connection management
│           ├── session/           # Session management
│           └── api/               # API client
├── services/
│   └── pfc-server/                # PFC WebSocket server (independent service)
│       ├── server/                # Server implementation (runs in PFC process)
│       │   ├── server.py          # WebSocket server + routing
│       │   ├── script_executor.py # Python script execution
│       │   ├── main_thread_executor.py # Queue-based main thread execution
│       │   └── task_manager.py    # Long-running task tracking
│       ├── examples/              # Example PFC projects
│       └── README.md              # Independent server documentation
└── ...
```

## 🚀 What Makes toyoura-nagisa Different?

Traditional approaches to PFC automation require users to:
- ❌ Remember complex command syntax
- ❌ Manually write and debug scripts
- ❌ Monitor console output continuously
- ❌ Context-switch between documentation and coding

**toyoura-nagisa automates this entire workflow:**
- ✅ LLM queries documentation automatically
- ✅ Test-first validation catches errors early
- ✅ Script-based execution creates self-documenting history
- ✅ Real-time monitoring with background task management

## 🚀 Getting Started

### Prerequisites

**toyoura-nagisa Backend:**
- **Python 3.10+** with `uv` package manager ([install guide](https://github.com/astral-sh/uv))
- **Git** - Required for file search tools (glob/grep functionality)
- **Node.js 16+** - For frontend development

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

**Optional:**
- **GitHub CLI (`gh`)** - For development workflows (issue/PR management)

### Quick Start

```bash
# Clone the repository
git clone https://github.com/yusong652/toyoura-nagisa.git
cd toyoura-nagisa

# Install all dependencies (frontend + backend)
npm install
uv sync

# Copy and configure settings
cp -r packages/backend/config_example/ packages/backend/config/
# Edit packages/backend/config/llm.py with your API keys

# Start both frontend and backend together
npm run dev
```

The application will be available at:
- Web Frontend: http://localhost:5173
- Backend API: http://localhost:8000

### CLI Mode

For engineers who prefer working in the terminal - run the full agentic PFC workflow without leaving your command line:

```bash
# Start CLI interface
npm run dev:cli

# Or start backend separately and run CLI
npm run dev:backend  # Terminal 1
npm run dev:cli      # Terminal 2
```

The CLI provides the same documentation-driven workflow as the web interface: natural language → documentation query → test script → production simulation, all from your terminal.

### Manual Setup

#### Backend Setup
```bash
# Install dependencies with uv
uv sync

# Copy and configure settings
cp -r packages/backend/config_example/ packages/backend/config/
# Edit packages/backend/config/llm.py with your API keys

# Start the backend server
npm run dev:backend
# Or manually: cd packages/backend && uv run python run.py
```

#### Web Frontend Setup
```bash
# Start web development server
npm run dev:web
# Or manually: cd packages/web && npm run dev
```

#### CLI Setup
```bash
# Build and run CLI
npm run dev:cli
# Or manually: cd packages/cli && npm run dev
```

### Configuration

Configure your preferred LLM providers in `packages/backend/config/llm.py`:
- **Gemini**: Primary provider with full feature support
- **Anthropic**: Claude integration with tool calling
- **OpenAI**: GPT models with comprehensive API integration
- **Local**: vLLM and Ollama support for self-hosted models

Configure additional features in `packages/backend/config/`:
- **Memory**: `memory.py` - Long-term memory settings (ChromaDB)
- **TTS**: `tts.py` - Text-to-speech providers (local/cloud)
- **Email**: `email.py` - Gmail integration for lifestyle agent
- **Text-to-Image**: `text_to_image.py` - Image generation capabilities

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
5. Executes production → monitors progress
6. Reports results
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
