# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

toyoura-nagisa is an extensible, voice-enabled AI assistant with long-term memory and a dynamic tool-use framework. The system combines a Python FastAPI backend with a React frontend and features sophisticated parallel tool execution, multi-provider LLM architecture, and intelligent memory management.

**Key Innovation**: The project delivers 60-70% faster performance for multi-tool scenarios through parallel execution with intelligent batching, making it significantly faster than traditional sequential tool execution.

## Development Commands

### Quick Start
```bash
# Start both frontend and backend concurrently
npm run dev

# Alternative: Start services separately
npm run start:backend    # Start FastAPI backend
npm run start:frontend   # Start React frontend
```

### Backend Development
```bash
# Start backend server
uv run python backend/app.py
# Alternative entry point
uv run python backend/run.py

# Install dependencies
uv sync

# Run tests
uv run pytest

# Run MCP server directly (for debugging)
uv run python backend/infrastructure/mcp/smart_mcp_server.py

# Code quality
npm run lint:backend     # Lint with ruff
npm run format:backend   # Format with ruff
```

### Frontend Development
```bash
cd frontend

# Start development server (with 5s backend wait)
npm run dev
# Start without delay
npm run dev:nodelay

# Build and test
npm run build
npm run preview
npm run lint
```

### Installation Commands
```bash
# Install all dependencies
npm run install:frontend
uv sync

# Copy configuration (required for first run)
cp -r backend/config_example/ backend/config/
# Then edit backend/config/llm.py with your API keys
```

### Running Single Tests
```bash
# Run specific test files or patterns
uv run pytest backend/tests/test_specific_module.py
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
│ │Presentation │ │Domain (Business Logic)│
│ │(API/WebSocket)│ │ Message Factory     │
│ └─────────────┘ └───────────────────────┤
│ ┌─────────────────────────────────────────┤
│ │        Infrastructure Layer           │
│ │ ┌─────────────┐ ┌─────────────────────┤
│ │ │ Unified LLM │ │ Parallel Tool Exec  │
│ │ │ Providers   │ │ (MCP/FastMCP)      │
│ │ └─────────────┘ └─────────────────────┤
│ │ ┌─────────────┐ ┌─────────────────────┤
│ │ │ Mem0 Memory │ │ ChromaDB Storage    │
│ │ │ Management  │ │ & Vectorization     │
│ │ └─────────────┘ └─────────────────────┤
└─────────────────────────────────────────┘
```

### Key Architectural Components

**1. Unified Multi-Provider LLM Architecture**
- All LLM providers inherit from `LLMClientBase` at `backend/infrastructure/llm/base/client.py`
- Supports Gemini, OpenAI, Anthropic, and Local models (vLLM, Ollama) with consistent interfaces
- Provider-specific optimizations while maintaining shared parallel execution capabilities

**2. Parallel Tool Execution System (MCP)**
- FastMCP-based tool orchestration at `backend/infrastructure/mcp/smart_mcp_server.py`
- Intelligent batching: single tools run immediately, 3+ tools execute concurrently
- Error isolation prevents failed tools from blocking others
- Real-time progress tracking with WebSocket notifications

**3. Intelligent Long-Term Memory (Mem0)**
- Semantic memory using Mem0 framework with ChromaDB backend
- Automatic conversation context extraction and injection
- Session-based memory isolation with vector similarity search
- Memory database stored at `backend/memory_db/`

**4. Clean Architecture Layers**
- **Presentation**: FastAPI routes (`backend/presentation/api/`) and WebSocket handlers (`backend/presentation/websocket/`)
- **Domain**: Business logic and message factory (`backend/domain/models/`)
- **Infrastructure**: External integrations (`backend/infrastructure/` - LLM, MCP, Memory, TTS, Storage)

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
   cp -r backend/config_example/ backend/config/
   ```

2. Edit configuration files in `backend/config/`:
   - `llm.py`: LLM provider API keys (Gemini, OpenAI, Anthropic, Local)
   - `memory.py`: Mem0 memory system settings
   - `tts.py`: Text-to-speech provider configuration
   - `email.py`, `text_to_image.py`: Additional service configurations

### Google Services Integration
For tools that use Google services (Calendar, Gmail, Contacts):
```bash
# Initialize Google OAuth tokens
uv run python backend/infrastructure/mcp/tools/google_auth/init_google_token.py
```

## Tool System Architecture

### Dynamic Tool Categories
Tools are organized into categories and loaded based on agent types:

- **builtin**: Web search and core system tools
- **coding**: File operations, shell commands, Python execution  
- **lifestyle**: Calendar, contacts, email, location, places, text-to-image, time utilities

### Tool Loading Strategy
- **Current Approach**: Static tool categories with intelligent composition
- **Previous Approach**: Dynamic vectorization with semantic search (proven less reliable with current LLM capabilities)
- Tools registered via category-specific functions in `backend/infrastructure/mcp/tools/`

## Development Patterns

### Message Flow Architecture
- Messages processed through factory pattern: `message_factory()` and `message_factory_no_thinking()`
- Support for text, image, and tool result messages with structured ToolResult format
- Real-time streaming via WebSocket with progress notifications

### Session Management
- UUID-based session identification
- Persistent chat history with metadata in `backend/chat/data/`
- Tool cache cleared when switching sessions
- Memory isolation per session

### Memory System Integration
- Automatic conversation context extraction using Mem0
- Semantic similarity search for relevant memory retrieval
- Memory injection into system prompts without explicit user requests
- Debug mode available for monitoring memory operations

## Technology Stack

**Backend:**
- **Python 3.10+** with **uv** package manager
- **FastAPI** + **uvicorn** for API server
- **FastMCP** for Model Context Protocol
- **ChromaDB** for vector storage (memory + tool vectorization)
- **Mem0** for intelligent memory management
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
- Memory: `mem0ai`, `chromadb`
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
uv run pytest backend/tests/test_specific_module.py

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
1. Create tool implementation in appropriate category under `backend/infrastructure/mcp/tools/`
2. Register tool in category's registration function
3. Tools automatically available via MCP protocol

### LLM Provider Integration
1. Implement provider-specific client inheriting from `LLMClientBase`
2. Add provider configuration to `backend/config/llm.py`
3. Register provider in LLM factory

### Frontend Component Development
- Use TypeScript with explicit typing
- Follow Material-UI patterns for consistency
- Implement WebSocket communication for real-time features
- Consider Live2D character integration for interactive elements

This architecture enables rapid development while maintaining high performance and extensibility for the toyoura-nagisa AI assistant platform.