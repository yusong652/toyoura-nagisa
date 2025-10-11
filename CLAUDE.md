# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**aiNagisa** is a **production-grade AI agent platform** bridging conversational AI with professional scientific computing workflows. The project demonstrates how modern LLM capabilities can be extended to control complex external systems while maintaining architectural elegance and reliability.

### Core Value Propositions

1. **Professional Scientific Computing Integration**
   - First-class support for ITASCA PFC (Particle Flow Code) discrete element simulations
   - Production-grade WebSocket architecture solving thread-safety and long-running task challenges
   - Real-time bidirectional communication between AI and simulation engines

2. **Intelligent Agent Specialization**
   - Multi-profile system dynamically configuring agent capabilities per domain
   - Token-optimized tool loading (coding: 10 tools, lifestyle: 14 tools, PFC: 14 tools, general: 28 tools)
   - Stateless per-request profile selection for scalability

3. **Clean Architecture at Scale**
   - Strict separation of presentation/domain/infrastructure layers (not just theoretical)
   - Pluggable LLM providers (Gemini, Anthropic, OpenAI, Local) with unified interface
   - Unified tool protocol ensuring consistent behavior across 28+ tools

4. **Long-term Contextual Memory**
   - ChromaDB-powered semantic similarity search
   - Session-based memory management with conversation history
   - Image-aware memory for multimodal context

### Technology Stack

- **Backend**: Python 3.11+, FastAPI, uvicorn, ChromaDB, FastMCP
- **Frontend**: React 19, TypeScript, Material-UI, Vite, Live2D (PIXI.js)
- **AI Infrastructure**: Multi-provider LLM support, real-time streaming, tool orchestration
- **Scientific Computing**: WebSocket integration with ITASCA PFC Python SDK
- **Communication**: WebSocket for real-time updates, RESTful API for state management

## Architecture & Core Features

### Clean Architecture Pattern

```
Presentation Layer (FastAPI, WebSocket)
    ↓ depends on
Domain Layer (Business Logic, Models)
    ↓ depends on
Infrastructure Layer (LLM, MCP, Memory, PFC)
```

**Key Principles**:
- **Dependency Inversion**: Infrastructure depends on domain abstractions
- **Single Responsibility**: Each layer has clear boundaries
- **Testability**: Domain logic isolated from external systems

**Example**: Swapping LLM providers requires zero domain layer changes (`backend/infrastructure/llm/base/llm_client.py`)

### LLM Multi-Provider Architecture

**Base Abstraction**: `backend/infrastructure/llm/base/llm_client.py`
```python
class LLMClient(ABC):
    @abstractmethod
    async def chat_stream(...) -> AsyncIterator[str]: ...
```

**Providers**: `backend/infrastructure/llm/providers/`
- `gemini/`: Google Gemini (primary provider)
- `anthropic/`: Anthropic Claude
- `openai/`: OpenAI GPT models
- `local/`: vLLM and Ollama support

**Configuration**: `backend/config/llm.py`

### Agent Profile System

**The Killer Feature**: Token-optimized, domain-specialized agent configurations.

| Profile | Tool Count | Token Usage | Use Case |
|---------|-----------|-------------|----------|
| **Coding** | 10 tools | 2,820 tokens | Code development, debugging |
| **Lifestyle** | 14 tools | 3,948 tokens | Email, calendar, communication |
| **PFC Expert** | 14 tools | 3,948 tokens | Scientific simulations |
| **General** | 28 tools | 7,896 tokens | Multi-domain tasks |
| **Disabled** | 0 tools | 0 tokens | Text-only conversation |

**Impact**: Coding profile uses 64% fewer tokens than General, enabling longer context windows.

**Implementation**: `backend/infrastructure/mcp/tool_profile_manager.py:12`

**API**: `/api/profiles` endpoint (`backend/presentation/api/profiles.py:41`)

### MCP Tool System

**Unified Tool Response Format** (`backend/infrastructure/mcp/utils/tool_result.py:27`):
```python
@dataclass
class ToolResult:
    status: Literal["success", "error"]    # Operation outcome
    message: str                           # User-facing summary
    llm_content: Optional[Any]             # Structured LLM content
    data: Optional[Dict[str, Any]]         # Tool-specific metadata
```

**Tool Categories** (`backend/infrastructure/mcp/tools/`):

| Category | Tools | Description |
|----------|-------|-------------|
| `builtin/` | web_search | Internet search |
| `coding/` | write, read, edit, bash, glob, grep, etc. | Development tools |
| `lifestyle/` | email, calendar, contacts, location, time, etc. | Productivity tools |
| `pfc/` | pfc_execute_command/script, check_status, list_tasks | PFC simulation control |

**Benefits**:
- Explicit schema for automatic documentation
- Stable contract across all tools
- LLM consistency in reasoning
- Extensible via `data` field

### PFC Integration Overview

**Problem**: AI-assisted control of professional scientific software (ITASCA PFC) requires solving:
1. Thread-safety (PFC SDK requires main thread execution)
2. Long-running tasks (simulations can run for hours)
3. Progress visibility (commands are non-interruptible)
4. Type system mismatch (Python types → PFC command strings)

**Solution Architecture**:
```
WebSocket Client → Queue → Main Thread Executor → PFC SDK
                     ↓
                TaskManager (independent status tracking)
```

**Key Components**:
- **Main Thread Executor**: Queue-based execution ensuring thread safety (`pfc-server/server/main_thread_executor.py`)
- **Task Manager**: Non-blocking lifecycle tracking (`pfc-server/server/task_manager.py:19`)
- **Script Executor**: Real-time output capture for progress monitoring (`pfc-server/server/script_executor.py:28`)
- **Command Executor**: Type-driven command assembly (`pfc-server/server/executor.py:152`)

**PFC Tools Workflow**:
1. `pfc_execute_command`: Immediate commands (returns success/failure)
2. `pfc_execute_script`: Long simulations (returns task_id immediately)
3. `pfc_check_task_status`: Query progress with real-time output
4. `pfc_list_tasks`: Overview of all tracked tasks

**Detailed Documentation**: See `pfc-server/README.md` for implementation details, thread-safety architecture, and usage examples.

**Backend Integration**: `backend/infrastructure/mcp/tools/pfc/` + `backend/infrastructure/pfc/websocket_client.py`

## Development Commands

### Prerequisites
- **GitHub CLI**: Required for issue management and PR workflows
  ```bash
  # macOS
  brew install gh

  # Linux (Debian/Ubuntu)
  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
  && sudo apt update \
  && sudo apt install gh

  # After installation, authenticate with:
  gh auth login
  ```

### Backend Development
```bash
# Start the backend server
uv run python backend/app.py

# Run the MCP server directly
uv run python backend/infrastructure/mcp/smart_mcp_server.py

# Run tests
uv run pytest

# Install dependencies
uv sync

# Install development dependencies (including GitHub CLI)
uv sync --extra dev
```

### Frontend Development
```bash
cd frontend

# Start development server
npm run dev

# Build for production
npm run build

# Run linting
npm run lint

# Preview production build
npm run preview
```

### PFC Integration Development

```bash
# Start PFC WebSocket server (in PFC GUI Python console)
exec(open(r'C:\Dev\Han\aiNagisa\pfc-server\start_server.py', encoding='utf-8').read())

# Test integration (with PFC server running)
uv run python examples/pfc_integration/DEMo.py
```

## File Structure

```
aiNagisa/
├── backend/
│   ├── app.py                      # Main FastAPI application
│   ├── presentation/               # API routes and WebSocket handlers
│   │   ├── api/
│   │   │   └── profiles.py        # Agent profile API
│   │   ├── websocket/             # WebSocket connection management
│   │   └── streaming/             # Response streaming handlers
│   ├── domain/                     # Core business logic
│   │   └── models/                # Domain models and message factory
│   ├── infrastructure/             # External system integrations
│   │   ├── llm/                   # LLM provider integrations
│   │   │   ├── base/              # Common abstractions (LLMClient ABC)
│   │   │   ├── providers/         # Provider implementations
│   │   │   │   ├── gemini/
│   │   │   │   ├── anthropic/
│   │   │   │   ├── openai/
│   │   │   │   └── local/
│   │   │   └── shared/
│   │   ├── mcp/                   # Model Context Protocol system
│   │   │   ├── smart_mcp_server.py      # Main MCP server
│   │   │   ├── tool_profile_manager.py  # Agent profile system
│   │   │   ├── tools/             # Tool implementations
│   │   │   │   ├── builtin/
│   │   │   │   ├── coding/
│   │   │   │   ├── lifestyle/
│   │   │   │   └── pfc/           # PFC simulation tools
│   │   │   └── utils/
│   │   │       └── tool_result.py # Unified tool response format
│   │   ├── pfc/
│   │   │   └── websocket_client.py # PFC WebSocket client
│   │   ├── memory/                # ChromaDB memory system
│   │   ├── storage/               # File and session storage
│   │   └── tts/                   # Text-to-speech engines
│   ├── config/                     # Configuration management
│   ├── shared/                     # Common utilities and exceptions
│   ├── memory_db/                  # ChromaDB persistence
│   └── workspace/                  # Development workspace
├── pfc-server/                     # PFC WebSocket server (independent service)
│   ├── server/                    # Server implementation
│   │   ├── server.py              # WebSocket server + routing
│   │   ├── executor.py            # Command executor + task classification
│   │   ├── script_executor.py     # Script execution with output capture
│   │   ├── main_thread_executor.py # Queue-based main thread execution
│   │   └── task_manager.py        # Long-running task tracking
│   ├── examples/                  # Example PFC projects
│   │   ├── scripts/               # Example simulation scripts
│   │   └── test_scripts/          # Test scripts
│   ├── start_server.py            # Startup script
│   ├── pyproject.toml             # Server dependencies
│   └── README.md                  # Independent server documentation
├── frontend/
│   ├── src/
│   │   ├── components/            # React components
│   │   ├── contexts/              # React contexts
│   │   └── App.tsx               # Main application
│   └── package.json              # Frontend dependencies
└── pyproject.toml                # Python project configuration
```

## Configuration

### Environment Setup
- Copy configuration examples from `backend/config_example/` to `backend/config/`
- Main config files: `base.py`, `llm.py`, `tts.py`, `email.py`, `text_to_image.py`
- Database locations:
  - Memory DB: `backend/memory_db/`
  - Session data: `backend/chat/data/`

### Google Services Integration
Many tools integrate with Google services via OAuth:
- Authentication tokens stored in `backend/infrastructure/mcp/tools/google_auth/tokens/`
- Supports Gmail, Google Calendar, and Google Contacts
- Use `backend/infrastructure/mcp/tools/google_auth/init_google_token.py` to set up authentication

## Development Patterns

### Message Handling
- Messages use factory pattern with `message_factory()` and `message_factory_no_thinking()`
- Support for text, image, and tool result messages
- Real-time streaming with WebSocket support

### Tool Integration
- Each tool category has its own registration function
- Tools follow FastMCP protocol
- All tools return standardized `ToolResult` format
- Semantic search enables dynamic tool discovery

### Session Management
- UUID-based session identification
- Persistent chat history with metadata
- Session cleanup and tool cache management

### Task Management Pattern

Long-running operations (PFC simulations, large file operations) use task-based execution:

1. **Submit**: Tool returns `task_id` immediately (non-blocking)
2. **Monitor**: Query status with `task_id` to check progress
3. **Complete**: Retrieve results when status changes to "success"

This pattern prevents:
- Client timeouts on long operations
- Thread pool exhaustion
- Blocking user interactions

**Implementation**: `pfc-server/server/task_manager.py:19`

## Testing

### Backend Testing
```bash
# Run all tests
uv run pytest
```

### Frontend Testing
The frontend uses standard React testing practices with Vite.

### PFC Integration Testing
```bash
# Comprehensive integration test (with PFC server running)
uv run python examples/pfc_integration/DEMo.py

# Tests: normal tasks, long tasks, status queries, WebSocket
#        responsiveness, task completion, main thread execution
```

## Common Issues & Quick Fixes

### LLM Provider Selection
- Configure preferred provider in `backend/config/llm.py`
- All providers support tool calling and streaming
- Local models supported via vLLM and Ollama

### Tool Loading
- Tools are loaded dynamically based on agent profile
- Profile selection is per-request (stateless)
- MCP server runs on port 9000 for tool communication

### Memory Management
- ChromaDB handles conversation memory and long-term context
- Session-based memory isolation
- Memory cleanup on session deletion

### PFC Integration
- PFC server runs on port 9001 (WebSocket)
- Server must be started in PFC GUI before using PFC tools
- Long tasks return task_id immediately for non-blocking operation
- Check `pfc-server/README.md` for troubleshooting

## Key Development Notes

- **Clean Architecture**: Implemented, not just theoretical - see dependency flow in `backend/`
- **Python Dependency Management**: Uses UV with `pyproject.toml`
- **Frontend Development**: Vite + TypeScript + Material-UI
- **Real-time Communication**: WebSocket for streaming responses
- **LLM Flexibility**: Pluggable architecture supports multiple providers
- **Tool System**: Asynchronous MCP-based tools with dynamic loading
- **Memory Architecture**: ChromaDB for conversation history and semantic search
- **Character Animation**: Live2D integration using PIXI.js
- **TTS Flexibility**: Support for local (GPT-SoVITS) and remote (Fish Audio) providers
- **Agent Specialization**: Profile-based tool loading optimizes token usage
- **Task-Based Execution**: Non-blocking operation management for long-running computations
- **Unified Tool Protocol**: ToolResult schema ensures consistent tool behavior
- **Stateless Profile Design**: Per-request profile selection eliminates session complexity

## 📚 Specialized Guides

For detailed guidance on specific development topics, refer to these specialized documents:

### Frontend Development
**File**: `.claude/guides/typescript-guide.md`

Comprehensive TypeScript development guide covering:
- Type system mastery (interfaces, generics, unions, conditionals)
- React-TypeScript integration patterns
- Component architecture and composition
- Custom hooks with proper typing
- Advanced type techniques and best practices

**When to use**: Frontend component development, TypeScript refactoring, React hook implementation

### Code Quality Standards
**File**: `.claude/guides/code-standards.md`

Project-wide coding standards including:
- Function documentation requirements (docstrings, type annotations)
- Type validation principles (avoiding redundancy, trusting internal APIs)
- Git commit message format and attribution
- Code readability guidelines

**When to use**: Writing new functions, creating commits, code reviews

### PFC Integration Deep Dive
**File**: `pfc-server/README.md`

Detailed PFC integration documentation covering:
- Thread-safety architecture and main thread execution
- Task classification and background execution patterns
- Type-driven command assembly examples
- Real-time progress monitoring implementation
- Troubleshooting and debugging guides

**When to use**: Working on PFC tools, understanding scientific computing integration

---

## Git Configuration

### Commit Message Requirements

When creating commits, follow these guidelines for attribution and project identification:

1. **Project Attribution**: Always reference the aiNagisa project repository URL `https://github.com/yusong652/aiNagisa` in commit messages rather than external tools
2. **Co-authorship**: Use "Co-authored-with: Nagisa Toyoura" to reflect collaborative development instead of external tool attribution
3. **Project Context**: Ensure commit messages reflect the aiNagisa project context and goals

### Example Commit Format
```
feat: improve tool extraction logic

Enhance MCP tool result processing for better LLM integration
in the aiNagisa voice-enabled AI assistant.

https://github.com/yusong652/aiNagisa

Co-authored-with: Nagisa Toyoura <nagisa.toyoura@gmail.com>
```

---
**Note**: This guide focuses on development workflow and architecture patterns. For technical showcase and detailed implementation explanations, see project documentation (NAGISA.md) and specialized guides listed above.
