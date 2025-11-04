
<p align="center">
  <img src="https://raw.githubusercontent.com/yusong652/aiNagisa/main/frontend/public/readme_header.png" alt="aiNagisa - LLM-Driven PFC Simulation Assistant with Script is Context Philosophy" width="900"/>
</p>

<p align="center">
  <a href="https://github.com/yusong652/aiNagisa/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-GPL%20v3-blue.svg" alt="License">
  </a>
  <a href="https://github.com/yusong652/aiNagisa/pulls">
    <img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome">
  </a>
</p>

---

## 🚀 Core Philosophy

aiNagisa is not just another chatbot. It's an exploration into creating a truly helpful and adaptive AI companion. Our goal is to build a system that can learn, reason, and act in the world through a rich set of tools and intelligent orchestration. We believe that the future of AI lies in its ability to seamlessly integrate with our digital lives, and aiNagisa is our step in that direction.

## ✨ Key Innovations

aiNagisa is built on a foundation of several key technical innovations:

### 🧠 **Agent Profile-Based Tool System with `FastMCP`**

At the heart of aiNagisa is the **Model Context Protocol (MCP)**, a powerful tool orchestration engine. Unlike traditional chatbots with hardcoded tool integrations, aiNagisa features a flexible agent profile system.

- **Agent Profile System**: Tools are organized into categories (coding, lifestyle, communication, etc.) and loaded based on agent profiles, ensuring the LLM has access to relevant capabilities for specific tasks
- **Dynamic Tool Loading**: Different agent profiles (General, PFC Expert, etc.) activate appropriate tool categories, making the system lightweight and context-appropriate
- **Multi-Step Reasoning**: The system supports complex workflows by allowing the LLM to chain together multiple tool calls, reasoning about results and using them as input for subsequent operations

### 📚 **Intelligent Long-Term Memory with Mem0**

aiNagisa features an advanced long-term memory system powered by Mem0 that automatically learns from conversations and builds a persistent understanding of users and their preferences.

- **Mem0 Integration**: Uses the modern Mem0 framework for intelligent memory extraction and management, automatically determining what information is worth remembering from conversations
- **Semantic Memory Search**: Vector-based memory retrieval using ChromaDB/Qdrant backend ensures relevant context is found even with different phrasing
- **Automatic Context Injection**: Seamlessly injects relevant memories into system prompts and conversations without explicit user requests
- **Multi-Provider LLM Support**: Memory extraction works with Gemini, OpenAI, and Anthropic models for optimal quality and cost balance
- **Smart Debug Controls**: Clean logging with optional debug mode to monitor memory injection and embedding processes
- **Configurable Behavior**: Fine-tune memory relevance thresholds, search timeouts, and injection strategies through comprehensive configuration options

### 🗣️ **Unified Multi-Provider LLM Architecture**

aiNagisa features a sophisticated **unified LLM architecture** with a shared base class that ensures consistent behavior across all providers while enabling provider-specific optimizations.

- **Unified Base Architecture**: All LLM providers (Gemini, OpenAI, Anthropic, Local) inherit from a common `LLMClientBase` with standardized streaming interfaces
- **Provider-Specific Optimizations**: Each provider maintains its unique capabilities while benefiting from shared tool orchestration and conversation management
- **Seamless Provider Switching**: Switch between models from OpenAI, Google, Anthropic, and local deployments (vLLM, Ollama) with zero configuration changes
- **Pluggable TTS**: The Text-to-Speech system is also pluggable, with support for both local (GPT-SoVITS) and remote (Fish Audio) TTS engines.

### 🎨 **Engaging Frontend with Live2D**

The user experience is a top priority. We've built a modern, responsive frontend with a unique twist.

- **React and Material-UI**: A clean, modern, and responsive UI built with industry-standard technologies.
- **Live2D Integration**: Nagisa is brought to life with a `Live2D` model that reacts to the conversation, creating a more engaging and personal interaction.

### 🔬 **LLM-Driven Industrial Software Integration (PFC)**

aiNagisa implements an experimental LLM agent system for ITASCA PFC discrete element simulations, demonstrating how AI assistants can interact with specialized industrial software through a **documentation-driven, script-only workflow**.

- **Documentation-Driven Development**: LLM queries command documentation before writing any code, ensuring correct syntax and understanding
- **Script-Only Execution**: All PFC operations flow through Python scripts using `itasca.command()`, eliminating dual-tool complexity
- **Test-First Validation**: Mandatory small-scale testing before production runs catches errors early
- **Systematic Error Handling**: Clear escalation chain (docs → API → web search → user) for troubleshooting
- **WebSocket-Based Communication**: Real-time bidirectional communication between aiNagisa and PFC through a dedicated WebSocket server
- **State-Aware Agent Design**: The LLM maintains awareness of simulation state evolution, treating simulations as dynamic systems rather than static code
- **Thread-Safe Architecture**: All PFC SDK calls execute in the main thread using queue-based coordination to ensure callback compatibility

**Workflow Pattern**:
```
Query Documentation → Write Test Script → Execute (small scale) →
Fix Errors (if any) → Write Production Script → Execute (full scale) → Monitor Progress
```

This integration represents an initial exploration of LLM-driven control for complex industrial software, with room for further refinement and generalization.

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

### Project Structure (Clean Architecture)

```
aiNagisa/
├── backend/
│   ├── app.py                     # FastAPI application entrypoint
│   ├── presentation/              # Presentation Layer
│   │   ├── api/                   # REST API endpoints
│   │   ├── websocket/             # WebSocket connection management
│   │   └── streaming/             # Response streaming handlers
│   ├── domain/                    # Domain Layer
│   │   └── models/                # Core business logic and message models
│   ├── infrastructure/            # Infrastructure Layer
│   │   ├── llm/                   # Multi-provider LLM architecture
│   │   │   ├── base/              # Unified LLM base classes
│   │   │   ├── providers/         # Provider-specific implementations
│   │   │   │   ├── gemini/        # Google Gemini integration
│   │   │   │   ├── anthropic/     # Anthropic Claude integration
│   │   │   │   ├── openai/        # OpenAI integration
│   │   │   │   └── local/         # Local LLM support (vLLM, Ollama)
│   │   │   └── shared/            # Common utilities and constants
│   │   ├── mcp/                   # Tool Execution (MCP)
│   │   │   ├── smart_mcp_server.py # Main MCP server
│   │   │   ├── tool_profile_manager.py # Agent profile management
│   │   │   └── tools/             # Tool implementations by category
│   │   │       └── pfc/           # PFC simulation tools (query + execute + monitor)
│   │   ├── pfc/                   # PFC WebSocket client integration
│   │   │   └── websocket_client.py # Auto-reconnecting WebSocket client
│   │   ├── memory/                # Mem0-powered long-term memory system
│   │   ├── storage/               # File and session storage
│   │   └── tts/                   # Text-to-speech engines
│   ├── config/                    # Configuration management
│   └── shared/                    # Common utilities and exceptions
├── frontend/
│   ├── src/
│   │   ├── App.tsx               # Main React application component
│   │   ├── components/           # UI components (ChatBox, Live2DCanvas, etc.)
│   │   └── contexts/             # React contexts for state management
│   └── public/
│       └── live2d_models/        # Live2D model files
├── pfc-server/                   # PFC WebSocket server (independent service)
│   ├── server/                   # Server implementation (runs in PFC process)
│   │   ├── server.py             # WebSocket server + routing
│   │   ├── executor.py           # Command executor + task classification
│   │   ├── script_executor.py    # Python script execution
│   │   ├── main_thread_executor.py # Queue-based main thread execution
│   │   └── task_manager.py       # Long-running task tracking
│   ├── examples/                 # Example PFC projects
│   │   ├── scripts/              # Example simulation scripts
│   │   └── test_scripts/         # Test scripts
│   ├── start_server.py           # Server startup script
│   ├── pyproject.toml            # Server dependencies
│   └── README.md                 # Independent server documentation
└── ...
```

## 🚀 Key Features

- **Agent Profile System**: Different agent profiles activate relevant tool categories for specific tasks
- **Flexible LLM Integration**: Seamless switching between multiple LLM providers with unified architecture
- **Intelligent Memory System**: Automatic learning and context injection powered by Mem0
- **Real-time Communication**: WebSocket-based streaming for responsive user experience

## 🚀 Getting Started

### Prerequisites

- Python 3.8+ with `uv` package manager
- Node.js 16+ for frontend development
- GitHub CLI (`gh`) for issue management and PR workflows

### Quick Start (Concurrent Mode)

```bash
# Clone the repository
git clone https://github.com/yusong652/aiNagisa.git
cd aiNagisa

# Install frontend dependencies
npm run install:frontend

# Install backend dependencies with uv
uv sync

# Copy and configure settings
cp -r backend/config_example/ backend/config/
# Edit backend/config/llm.py with your API keys

# Start both frontend and backend together
npm run dev
```

The application will be available at:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000

### Manual Setup

#### Backend Setup
```bash
# Clone the repository (if not already done)
git clone https://github.com/yusong652/aiNagisa.git
cd aiNagisa

# Install dependencies with uv
uv sync

# Copy and configure settings
cp -r backend/config_example/ backend/config/
# Edit backend/config/llm.py with your API keys

# Start the backend server
uv run python backend/app.py
```

#### Frontend Setup
```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### Configuration

Configure your preferred LLM providers in `backend/config/llm.py`:
- **Gemini**: Primary provider with full feature support
- **Anthropic**: Claude integration with tool calling
- **OpenAI**: GPT models with comprehensive API integration
- **Local**: vLLM and Ollama support for self-hosted models

Configure memory system behavior in `backend/config/memory.py`:
- **Memory Features**: Enable/disable memory saving and auto-injection
- **LLM Selection**: Choose extraction model (Gemini Flash, GPT-4o mini, Claude Haiku)
- **Performance Tuning**: Adjust search timeouts, relevance thresholds, and context limits
- **Debug Mode**: Enable detailed logging to monitor memory operations with `debug_mode=True`

### Key Features to Explore

1. **Agent Profiles**: Switch between different agent profiles (General, PFC Expert) to activate specialized tool sets
2. **Tool Categories**: The system loads appropriate tool categories based on the selected agent profile
3. **Long-term Memory**: aiNagisa remembers your preferences and conversation history across sessions
4. **Live2D Integration**: Enjoy an interactive character that responds to conversations
5. **Voice Integration**: Use voice input for natural interaction (frontend feature)
6. **PFC Integration** (optional): Interact with ITASCA PFC simulations through natural language with state-aware agent guidance

### PFC Workspace Setup (Optional)

For users working with ITASCA PFC discrete element simulations:

```bash
# 1. Install websockets in PFC's Python environment
pip install websockets

# 2. Start PFC WebSocket server in PFC IPython shell
import sys
sys.path.append(r'/path/to/aiNagisa/pfc-server')
exec(open(r'/path/to/aiNagisa/pfc-server/start_server.py', encoding='utf-8').read())

# 3. In aiNagisa, select "PFC Expert" agent profile
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

See `pfc-server/README.md` for detailed setup and usage instructions.

## 🤝 Contributing

We are actively looking for contributors to help us push the boundaries of what's possible with AI assistants. Whether you're a frontend developer, a backend engineer, or an AI researcher, there are many ways to get involved. 

Key areas where we welcome contributions:
- **Tool System Enhancements**: Improve tool orchestration and agent profile management
- **New Tool Integrations**: Expand our tool ecosystem with new capabilities
- **LLM Provider Support**: Add support for additional LLM providers
- **Frontend Enhancements**: Improve the user experience and Live2D integration
- **Industrial Software Integration**: Extend the PFC integration pattern to other specialized software (CAD, FEA, etc.)
- **Documentation**: Help others understand and contribute to the project

Please check out our contributing guidelines and the `CLAUDE.md` file for development setup instructions.

## 📄 License

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](LICENSE) file for details.
