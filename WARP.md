# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

toyoura-nagisa is a production-grade AI agent platform bridging conversational AI with professional scientific computing workflows. The system combines a Python FastAPI backend with a React frontend and features multi-provider LLM architecture, agent specialization, and ChromaDB-powered memory.

**Key Innovations**:
- **Agent Profile System**: Token-optimized, domain-specialized agent configurations (coding: 10 tools, lifestyle: 14 tools, PFC: 14 tools, general: 27 tools)
- **SubAgent Delegation**: MainAgent can delegate specialized tasks to lightweight SubAgents for context optimization
- **Clean Architecture**: Business logic in application layer (Agent), infrastructure handles only API communication

## Development Commands

### Quick Start
```bash
# Start both frontend and backend concurrently
npm run dev:all

# Alternative: Start services separately
npm run dev:backend    # Start FastAPI backend
npm run dev:web        # Start React frontend
```

### Backend Development
```bash
# Start backend server
npm run dev:backend
# OR manually:
cd packages/backend && uv run python run.py

# Install dependencies
uv sync

# Run tests
uv run pytest

# Run MCP server directly (for debugging)
uv run python packages/backend/infrastructure/mcp/smart_mcp_server.py
```

### Frontend Development
```bash
# Start Web frontend
npm run dev:web
# OR manually:
cd packages/web && npm run dev

# Build and test
npm run build
npm run preview
npm run lint
```

### Installation Commands
```bash
# Install all dependencies
npm install
uv sync

# Copy configuration (required for first run)
cp -r packages/backend/config_example/ packages/backend/config/
# Then edit packages/backend/config/llm.py with your API keys
```

### Running Single Tests
```bash
# Run specific test files or patterns
uv run pytest packages/backend/tests/test_specific_module.py
uv run pytest -k "test_pattern_name"
```

## Architecture Overview

### High-Level System Design

toyoura-nagisa follows **Clean Architecture** principles with clear separation of concerns:

```
┌─────────────────────────────────────────┐
│           Frontend (React)              │
│  Live2D, Chat UI, Voice Input          │
└────────────┬────────────────────────────┘
             │ WebSocket/HTTP
┌────────────▼────────────────────────────┐
│         Backend (Clean Arch)            │
│ ┌─────────────┐ ┌───────────────────────┤
│ │Presentation │ │Application Layer     │
│ │(API/WebSocket)│ │ Agent, AgentService │
│ └─────────────┘ └───────────────────────┤
│ ┌─────────────────────────────────────────┤
│ │        Infrastructure Layer           │
│ │ ┌─────────────┐ ┌─────────────────────┤
│ │ │ LLM Client  │ │ Tool Execution      │
│ │ │ (stateless) │ │ (MCP/FastMCP)      │
│ │ └─────────────┘ └─────────────────────┤
│ │ ┌─────────────┐ ┌─────────────────────┤
│ │ │ ChromaDB    │ │ Domain Models       │
│ │ │ Memory      │ │ (StreamingChunk)    │
│ │ └─────────────┘ └─────────────────────┤
└─────────────────────────────────────────┘
```

### Key Architectural Components

**1. Agent System (Application Layer)**
- `Agent` class at `packages/backend/application/services/agent.py` implements business logic
- Handles tool calling loop, streaming orchestration, and conversation management
- `AgentService` provides clean interface for presentation layer
- SubAgent support via `invoke_agent` tool for task delegation

**2. Unified Multi-Provider LLM Architecture (Infrastructure Layer)**
- `LLMClientBase` at `packages/backend/infrastructure/llm/base/client.py` provides stateless API interfaces
- Supports Gemini, OpenAI, Anthropic, and Local models (vLLM, Ollama) with consistent interfaces
- Provider-specific implementations handle only API communication

**3. Tool Execution System (MCP)**
- FastMCP-based tool orchestration at `packages/backend/infrastructure/mcp/smart_mcp_server.py`
- Profile-based tool loading optimizes token usage per domain
- Tool categories: builtin, coding, lifestyle, pfc, agent
- Real-time progress tracking with WebSocket notifications

**4. ChromaDB Memory System**
- Semantic memory with vector similarity search
- Session-based memory isolation
- Memory database stored at `memory_db/`

**5. Clean Architecture Layers**
- **Presentation**: FastAPI routes (`packages/backend/presentation/api/`) and WebSocket handlers
- **Application**: Agent orchestration (`packages/backend/application/services/`)
- **Domain**: Core models (`packages/backend/domain/models/`)
- **Infrastructure**: External integrations (`packages/backend/infrastructure/`)

### Frontend Architecture

**React 19 + TypeScript** with key features:
- **Live2D Integration**: Interactive character using `pixi-live2d-display` 
- **Material-UI**: Consistent component styling
- **Real-time Communication**: WebSocket for streaming responses
- **Vite**: Fast development and build tooling

## Configuration Setup

### Environment Configuration
1. Copy configuration templates:
   ```bash
   cp -r packages/backend/config_example/ packages/backend/config/
   ```

2. Edit configuration files in `packages/backend/config/`:
   - `llm.py`: LLM provider API keys (Gemini, OpenAI, Anthropic, Local)
   - `memory.py`: Memory system settings
   - `tts.py`: Text-to-speech provider configuration
   - `email.py`, `text_to_image.py`: Additional service configurations

### Google Services Integration
For tools that use Google services (Calendar, Gmail, Contacts):
```bash
# Initialize Google OAuth tokens
uv run python packages/backend/infrastructure/mcp/tools/google_auth/init_google_token.py
```

## Tool System Architecture

### Tool Categories
Tools are organized into categories and loaded based on agent profiles:

- **builtin**: Web search and core system tools
- **coding**: File operations (read, write, edit, glob, grep), shell commands (bash)
- **lifestyle**: Calendar, contacts, email, location, places, text-to-image, time utilities
- **pfc**: PFC simulation tools (query, execute_task, check_status, list_tasks)
- **agent**: SubAgent invocation (invoke_agent)

### Agent Profile System
- Profiles define which tools are available per domain
- Token-optimized loading: coding profile uses 64% fewer tokens than general
- Configuration at `packages/backend/domain/models/agent_profiles.py`
- Tools registered via category-specific functions in `packages/backend/infrastructure/mcp/tools/`

## Development Patterns

### Message Flow Architecture
- Messages processed through factory pattern: `message_factory()` and `message_factory_no_thinking()`
- Support for text, image, and tool result messages with structured ToolResult format
- Real-time streaming via WebSocket with progress notifications
- Agent handles conversation turns via `AgentService.process_chat()`

### Session Management
- UUID-based session identification
- Persistent chat history with metadata in `data/`
- Tool cache cleared when switching sessions
- Memory isolation per session

### Memory System Integration
- ChromaDB-powered semantic similarity search
- Session-based memory management with conversation history
- Memory injection into system prompts
- Memory database stored at `memory_db/`

## Technology Stack

**Backend:**
- **Python 3.11+** with **uv** package manager
- **FastAPI** + **uvicorn** for API server
- **FastMCP** for Model Context Protocol
- **ChromaDB** for vector storage and memory
- **WebSockets** for real-time communication

**Frontend:**
- **React 19** with **TypeScript**
- **Material-UI** component library
- **PIXI.js** + **Live2D** for character animation
- **Vite** for development and building
- **WebSocket** client for real-time features

**Key Dependencies:**
- Multi-provider LLM support: `google-genai`, `openai`, `anthropic`, `vllm`, `ollama`
- Tool integrations: `google-api-python-client`, `googlemaps`
- Memory: `chromadb`
- TTS: `fish-audio-sdk`, `torch`, `torchaudio`

## Development Guidelines

### Code Quality Standards
- **Type Annotations**: All functions must have explicit type annotations
- **Docstring Format**: Use structured docstrings with Args/Returns sections
- **Clean Architecture**: Maintain separation between presentation, domain, and infrastructure
- **Error Handling**: Use structured ToolResult format for consistent error reporting

### Testing Strategy
```bash
# Run all backend tests
uv run pytest

# Test specific modules
uv run pytest packages/backend/tests/test_specific_module.py

# Test with coverage
uv run pytest --cov
```

### Performance Considerations
- **Parallel Execution**: System automatically optimizes tool execution based on task complexity
- **Memory Efficiency**: Session-based memory isolation with automatic cleanup
- **Provider Switching**: Zero-latency transitions between LLM providers
- **Resource Management**: Intelligent batching reduces overhead for multi-tool workflows

## Common Development Workflows

### Adding New Tools
1. Create tool implementation in appropriate category under `packages/backend/infrastructure/mcp/tools/`
2. Register tool in category's registration function
3. Add tool name to desired profiles in `packages/backend/domain/models/agent_profiles.py`
4. Tools automatically available via MCP protocol

### LLM Provider Integration
1. Implement provider-specific client inheriting from `LLMClientBase`
2. Add provider configuration to `packages/backend/config/llm.py`
3. Register provider in LLM factory

### Frontend Component Development
- Use TypeScript with explicit typing
- Follow Material-UI patterns for consistency
- Implement WebSocket communication for real-time features
- Consider Live2D character integration for interactive elements

This architecture enables rapid development while maintaining high performance and extensibility for the toyoura-nagisa AI agent platform.