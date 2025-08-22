
<p align="center">
  <img src="https://raw.githubusercontent.com/yusong652/aiNagisa/main/frontend/public/Nagisa.png" alt="aiNagisa Logo" width="200"/>
</p>

<h1 align="center">aiNagisa</h1>

<p align="center">
  <strong>An extensible, voice-enabled AI assistant with long-term memory and a dynamic tool-use framework.</strong>
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

aiNagisa is not just another chatbot. It's an exploration into creating a truly helpful and adaptive AI companion with blazing-fast performance. Our goal is to build a system that can learn, reason, and act in the world through a rich set of tools executed with intelligent parallel processing. We believe that the future of AI lies in its ability to seamlessly integrate with our digital lives while delivering exceptional speed and efficiency, and aiNagisa is our step in that direction.

## ✨ Key Innovations

aiNagisa is built on a foundation of several key technical innovations that deliver exceptional performance and set it apart:

### 🚀 **Parallel Tool Execution with Intelligent Batching**

aiNagisa features a revolutionary **parallel tool execution system** that delivers 60-70% faster performance for multi-tool scenarios. This intelligent batching system automatically determines the optimal execution strategy based on the number and nature of tool calls.

- **Intelligent Execution Strategy**: Single tools run immediately, while multiple tools (3+) execute concurrently using `asyncio.gather()` for maximum throughput
- **Error Isolation**: Failed tools don't prevent other tools from executing, ensuring robust operation even with partial failures
- **Real-time Progress Tracking**: Live notifications for parallel execution progress with detailed batch status updates
- **LLM-Driven Independence**: Trusts the LLM's judgment on tool independence and execution order, enabling sophisticated parallel workflows

### 🧠 **Autonomous Tool Orchestration with `FastMCP`**

At the heart of aiNagisa is the **Model Context Protocol (MCP)**, a powerful tool orchestration engine. Unlike traditional chatbots with hardcoded tool integrations, aiNagisa features a dynamic, semantic tool discovery and invocation system.

- **Semantic Tool Search**: We use a `ToolVectorizer` to embed the descriptions and capabilities of all available tools into a vector space. When a user makes a request, the LLM can query this vector space to find the most relevant tools for the task at hand. This allows for a much more flexible and extensible tool system.
- **Dynamic Tool Loading**: Tools are categorized and can be loaded on-demand, making the system lightweight and scalable. The LLM can request tool categories based on the task, and the MCP will provide the necessary tools.
- **Chain of Thought (CoT) and Tool Use**: The system supports complex, multi-step tasks by allowing the LLM to chain together multiple tool calls. The LLM can reason about the results of one tool and use them as input for another, enabling sophisticated workflows.

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
- **Provider-Specific Optimizations**: Each provider maintains its unique capabilities while benefiting from shared parallel execution and tool orchestration
- **Seamless Provider Switching**: Switch between models from OpenAI, Google, Anthropic, and local deployments (vLLM, Ollama) with zero configuration changes
- **Pluggable TTS**: The Text-to-Speech system is also pluggable, with support for both local (GPT-SoVITS) and remote (Fish Audio) TTS engines.

### 🎨 **Engaging Frontend with Live2D**

The user experience is a top priority. We've built a modern, responsive frontend with a unique twist.

- **React and Material-UI**: A clean, modern, and responsive UI built with industry-standard technologies.
- **Live2D Integration**: Nagisa is brought to life with a `Live2D` model that reacts to the conversation, creating a more engaging and personal interaction.

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
| | |  Unified LLM   |  |   Parallel Tool    | | |
| | |  Base Client   |  |   Execution (MCP)  | | |
| | +----------------+  +--------------------+ | |
| | +----------------+  +--------------------+ | |
| | | Tool Vectorizer|  |  Mem0 Memory Mgmt  | | |
| | |  (ChromaDB)    |  | (ChromaDB/Qdrant)  | | |
| | +----------------+  +--------------------+ | |
| +------------------------------------------+ |
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
│   │   ├── mcp/                   # Parallel Tool Execution (MCP)
│   │   │   ├── smart_mcp_server.py # Main MCP server
│   │   │   ├── tool_vectorizer.py  # Semantic tool search
│   │   │   └── tools/             # Tool implementations by category
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
└── ...
```

## 🚀 Performance Highlights

- **60-70% Faster Multi-Tool Execution**: Parallel processing delivers significant performance improvements for complex multi-tool workflows
- **Real-time Tool Orchestration**: Instant notifications and progress tracking for all tool execution phases
- **Zero-Latency Provider Switching**: Seamless transitions between LLM providers with unified architecture
- **Intelligent Resource Management**: Automatic batching optimization based on task complexity and tool independence

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

1. **Parallel Tool Execution**: Ask aiNagisa to perform multiple tasks simultaneously and watch the parallel processing in action
2. **Semantic Tool Discovery**: The system automatically finds and uses the most relevant tools for your requests
3. **Long-term Memory**: aiNagisa remembers your preferences and conversation history across sessions
4. **Live2D Integration**: Enjoy an interactive character that responds to conversations
5. **Voice Integration**: Use voice input for natural interaction (frontend feature)

## 🤝 Contributing

We are actively looking for contributors to help us push the boundaries of what's possible with AI assistants. Whether you're a frontend developer, a backend engineer, or an AI researcher, there are many ways to get involved. 

Key areas where we welcome contributions:
- **Performance Optimizations**: Help improve our parallel execution algorithms
- **New Tool Integrations**: Expand our tool ecosystem with new capabilities
- **LLM Provider Support**: Add support for additional LLM providers
- **Frontend Enhancements**: Improve the user experience and Live2D integration
- **Documentation**: Help others understand and contribute to the project

Please check out our contributing guidelines and the `CLAUDE.md` file for development setup instructions.

## 📄 License

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](LICENSE) file for details.
