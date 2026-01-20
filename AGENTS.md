# CLAUDE.md

This file provides guidance to Agent when working with code in this repository.

## Project Overview

**toyoura-nagisa** is an AI agent platform for professional scientific computing, focusing on ITASCA PFC (Particle Flow Code) discrete element simulations with real-time WebSocket communication.

### Technology Stack

- **Backend**: Python 3.10+, FastAPI, uvicorn, ChromaDB, FastMCP
- **Frontend**: React 19, TypeScript, Material-UI, Vite, Live2D (PIXI.js)
- **AI Infrastructure**: Multi-provider LLM support, real-time streaming, tool orchestration
- **Scientific Computing**: WebSocket integration with ITASCA PFC Python SDK
- **Communication**: WebSocket for real-time updates, RESTful API for state management

## Architecture & Core Features

### Clean Architecture Pattern

```
Presentation Layer (API, WebSocket, Handlers)
    ↓ depends on
Application Layer (Services, Orchestration)
    ↓ depends on
Domain Layer (Models, Business Rules)
    ↓ depends on
Infrastructure Layer (LLM, MCP, Memory, PFC, Storage)
```

**Key Principles**:
- **Dependency Inversion**: Infrastructure depends on domain abstractions
- **Single Responsibility**: Each layer has clear boundaries
- **Testability**: Domain logic isolated from external systems

**Layer Responsibilities**:
- **Presentation**: API routes, WebSocket handlers, request/response formatting
- **Application**: Business logic orchestration (ChatOrchestrator, content processing)
- **Domain**: Core models and business rules (StreamingChunk, BaseMessage)
- **Infrastructure**: External integrations (LLM providers, MCP tool registration, storage). Note: MCP tools currently contain business logic; planned refactor to move tool logic to Application layer

**Example**: Swapping LLM providers requires zero application/domain layer changes (`backend/infrastructure/llm/base/client.py`)

### LLM Providers

Located in `backend/infrastructure/llm/providers/`: google (primary), anthropic, openai, moonshot, zhipu, openrouter, local (vLLM/Ollama).

**Configuration**: `backend/config/llm.py`

### SubAgent System

MainAgent can delegate specialized tasks to lightweight SubAgents via the `invoke_agent` tool.

**Available SubAgents**:

| SubAgent | Tools | Max Iterations | Purpose |
|----------|-------|----------------|---------|
| **PFC Explorer** | 14 read-only | 20 | Documentation search, codebase exploration |
| **PFC Diagnostic** | 9 read-only | 64 | Multimodal visual analysis, task status inspection |

**PFC Explorer Tools**: `read`, `glob`, `grep`, `bash`, `bash_output`, `pfc_browse_commands`, `pfc_browse_python_api`, `pfc_query_python_api`, `pfc_query_command`, `pfc_browse_reference`, `pfc_list_tasks`, `pfc_check_task_status`, `web_search`, `todo_write`

**PFC Diagnostic Tools**: `pfc_capture_plot`, `read`, `pfc_check_task_status`, `pfc_list_tasks`, `glob`, `grep`, `bash`, `bash_output`, `todo_write`

**Architecture**:
- **Non-Streaming**: SubAgents use synchronous API calls for efficiency
- **Memory Isolation**: SubAgent todos stored in memory (`_memory_todos`), not persisted to disk
- **Context Separation**: SubAgent exploration doesn't consume MainAgent's context window
- **Read-Only**: SubAgents cannot execute simulations or modify files (no `pfc_execute_task`, `write`, `edit`)

**Storage Mode** (determined by `agent_profile`):
- MainAgent (`pfc_expert`): `persistent=True` → local file (`workspace/todos.json`)
- SubAgent (`pfc_explorer`, `pfc_diagnostic`): `persistent=False` → in-memory storage

**Implementation**:
- Tool: `backend/infrastructure/mcp/tools/agent/invoke_agent.py`
- Config: `backend/domain/models/agent_profiles.py` (`PFC_EXPLORER`, `PFC_DIAGNOSTIC`, `SUBAGENT_*_TOOLS`)
- Prompts: `backend/config/prompts/pfc_explorer.md`, `backend/config/prompts/pfc_diagnostic.md`

### MCP Tool System

**Tool Categories** (`backend/infrastructure/mcp/tools/`):
- `coding/`: write, read, edit, bash, glob, grep
- `pfc/`: pfc_execute_task, pfc_check_task_status, pfc_list_tasks, pfc_capture_plot, pfc_query_*, pfc_browse_*
- `planning/`: todo_write
- `agent/`: invoke_agent
- `builtin/`: web_search

### PFC Integration Overview

**Problem**: AI-assisted control of professional scientific software (ITASCA PFC) requires solving:
1. Thread-safety (PFC SDK requires main thread execution)
2. Long-running tasks (simulations can run for hours)
3. Progress visibility (commands are non-interruptible)
4. Documentation-driven workflow (LLM needs command syntax guidance)

**Solution Architecture**:
```
Documentation Query → Test Script → Production Script → WebSocket → PFC SDK
     ↓                    ↓              ↓
Query Tools      Small-Scale Test   Full Simulation
(syntax ref)     (quick validate)   (task tracking)
```

**Key Components**:
- **Main Thread Executor**: Queue-based execution ensuring thread safety (`services/pfc-server/server/main_thread_executor.py`)
- **Task Manager**: Non-blocking lifecycle tracking (`services/pfc-server/server/task_manager.py:19`)
- **Script Executor**: Real-time output capture for progress monitoring (`services/pfc-server/server/script_executor.py:28`)
- **Diagnostic Executor**: Callback-based execution for non-blocking diagnostics during simulation cycles (`services/pfc-server/server/diagnostic_executor.py`)
- **Documentation System**: Command syntax + Python usage examples (`backend/infrastructure/pfc/commands/`)

**PFC Tools Workflow (Script-Only)**:
1. **Query**: `pfc_query_command` / `pfc_query_python_api` - Get command syntax and Python examples
2. **Test**: `pfc_execute_task` (small scale, `run_in_background=False`) - Quick validation
3. **Production**: `pfc_execute_task` (full scale, `run_in_background=True`) - Long simulations with git snapshot
4. **Monitor**: `pfc_check_task_status` - Query progress with real-time output
5. **List**: `pfc_list_tasks` - Overview of all tracked tasks with version info

**Core Pattern**: All PFC commands executed via Python scripts using `itasca.command("...")` pattern.

**Git Version Tracking**:
- Each `pfc_execute_task` creates a git snapshot on the `pfc-executions` branch
- **IMPORTANT**: NEVER checkout or work on the `pfc-executions` branch in PFC projects
- This branch is automatically managed; working on it will break git snapshot creation
- If accidentally on this branch, switch back: `git checkout master`

**Detailed Documentation**: See `services/pfc-server/README.md` for implementation details, thread-safety architecture, and usage examples.

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
npm run dev:backend
# OR manually:
cd packages/backend && uv run python run.py

# Run the MCP server directly
uv run python packages/backend/infrastructure/mcp/mcp_server.py

# Run tests
uv run pytest

# Install dependencies
uv sync

# Install development dependencies (including GitHub CLI)
uv sync --extra dev
```

### Frontend Development
```bash
# Start Web frontend
npm run dev:web
# OR manually:
cd packages/web && npm run dev

# Build for production
npm run build

# Run linting
npm run lint

# Preview production build
npm run preview
```

### PFC Integration Development

**Important**: pfc-server is NOT a UV workspace member. It runs in PFC's embedded Python environment with separate dependencies.

```bash
# 1. Install pfc-server dependencies in PFC's Python environment
#    (Run in PFC GUI IPython console)
pip install websockets==9.1

# 2. Start PFC WebSocket server (in PFC GUI Python console)
exec(open(r'C:\Dev\Han\toyoura-nagisa\services\pfc-server\start_server.py', encoding='utf-8').read())

# 3. Test integration from toyoura-nagisa environment (with PFC server running)
uv run python examples/pfc_integration/DEMo.py
```

**Why separate?**
- pfc-server requires `websockets==9.1` (PFC Python environment constraint)
- toyoura-nagisa requires `websockets>=15.0.1` (modern features)
- Different runtime environments → separate dependency management

## File Structure

```
toyoura-nagisa/
├── packages/
│   ├── backend/
│   │   ├── app.py                      # Main FastAPI application
│   │   ├── presentation/               # API routes and WebSocket handlers
│   │   ├── api/
│   │   │   ├── profiles.py        # Agent profile API
│   │   │   └── file_search.py     # File mention search API
│   │   ├── websocket/             # WebSocket connection management
│   │   ├── handlers/              # Request handlers
│   │   │   ├── chat_request_handler.py  # Chat request processing
│   │   └── streaming/             # Response streaming handlers
│   ├── application/                # Business logic orchestration
│   │   └── services/              # Business services
│   │       ├── agent.py           # Main Agent class
│   │       ├── chat_service.py    # Chat message processing
│   │       ├── streaming_models.py # StreamingState and models
│   │       ├── contents/          # Content processing
│   │       ├── notifications/     # Tool confirmation, notifications
│   │       ├── pfc/               # PFC console service
│   │       └── shell/             # Shell execution service
│   ├── domain/                     # Core business logic
│   │   └── models/                # Domain models
│   │       ├── streaming.py       # StreamingChunk unified format
│   │       ├── messages.py        # BaseMessage, AssistantMessage
│   │       └── message_factory.py # Message factory functions
│   ├── infrastructure/             # External system integrations
│   │   ├── llm/                   # LLM provider integrations
│   │   │   ├── base/              # Common abstractions
│   │   │   │   ├── client.py      # LLMClientBase ABC
│   │   │   │   └── response_processor.py  # BaseStreamingProcessor
│   │   │   ├── providers/         # Provider implementations
│   │   │   │   ├── google/
│   │   │   │   ├── anthropic/
│   │   │   │   ├── openai/
│   │   │   │   ├── moonshot/
│   │   │   │   ├── zhipu/
│   │   │   │   ├── openrouter/
│   │   │   │   └── local/
│   │   │   └── shared/
│   │   ├── mcp/                   # Model Context Protocol system
│   │   │   ├── mcp_server.py            # Main MCP server
│   │   │   ├── tools/             # Tool implementations
│   │   │   │   ├── builtin/
│   │   │   │   ├── coding/
│   │   │   │   ├── lifestyle/
│   │   │   │   ├── pfc/           # PFC simulation tools
│   │   │   │   ├── planning/      # Task planning (todo_write)
│   │   │   │   └── agent/         # SubAgent invocation (invoke_agent)
│   │   │   └── utils/
│   │   │       └── tool_result.py # Unified tool response format
│   │   ├── monitoring/            # Status monitoring system
│   │   │   ├── status_monitor.py  # Unified coordinator
│   │   │   └── monitors/          # Specialized monitors
│   │   │       ├── iteration_monitor.py  # Iteration limit warnings
│   │   │       ├── todo_monitor.py       # Todo reminders
│   │   │       ├── bash_monitor.py       # Background bash processes
│   │   │       └── pfc_monitor.py        # PFC task tracking
│   │   ├── file_mention/          # File mention processing
│   │   │   └── file_mention_processor.py  # Safe file reading and injection
│   │   ├── pfc/
│   │   │   └── websocket_client.py # PFC WebSocket client
│   │   ├── memory/                # ChromaDB memory system
│   │   ├── storage/               # File and session storage
│   │   ├── websocket/             # WebSocket infrastructure
│   │   │   ├── connection_manager.py     # Connection management
│   │   │   └── notification_service.py   # WebSocket notifications
│   │   ├── shell/                 # Shell execution infrastructure
│   │   │   ├── executor.py        # ShellExecutor (foreground/background)
│   │   │   ├── shell_config.py    # Cross-platform shell detection
│   │   │   └── background_process_manager.py  # Background process lifecycle
│   │   ├── messaging/             # Message queue management
│   ├── config/                     # Configuration management
│   │   └── prompts/               # Agent system prompts
│   │       ├── pfc_explorer.md    # PFC Explorer SubAgent prompt
│   │       └── pfc_diagnostic.md  # PFC Diagnostic SubAgent prompt
│   ├── shared/                     # Common utilities and exceptions
│   │   ├── memory_db/                  # ChromaDB persistence
│   │   └── workspace/                  # Development workspace
│   ├── web/                        # React Web frontend
│   │   ├── src/
│   │   │   ├── components/            # React components
│   │   │   ├── contexts/              # React contexts
│   │   │   └── App.tsx               # Main application
│   │   └── package.json              # Frontend dependencies
│   ├── cli/                        # Terminal CLI frontend (React/Ink)
│   │   └── src/
│   │       └── ui/
│   │           ├── hooks/             # Hook-driven architecture (chat, session, profile)
│   │           ├── components/        # Terminal UI components
│   │           └── commands/          # Slash command system
│   └── core/                       # Shared TypeScript core
├── services/
│   └── pfc-server/                 # PFC WebSocket server (independent service)
│       ├── server/                    # Server implementation
│       │   ├── server.py              # WebSocket server + routing
│       │   ├── executor.py            # Command executor + task classification
│       │   ├── script_executor.py     # Script execution with output capture
│       │   ├── main_thread_executor.py # Queue-based main thread execution
│       │   ├── task_manager.py        # Long-running task tracking
│       │   └── diagnostic_executor.py # Non-blocking diagnostic script execution
│       ├── examples/                  # Example PFC projects
│       │   ├── scripts/               # Example simulation scripts
│       │   └── test_scripts/          # Test scripts
│       ├── start_server.py            # Startup script
│       ├── pyproject.toml             # Server dependencies
│       └── README.md                  # Independent server documentation
├── workspace/                      # UV workspace
├── memory_db/                      # ChromaDB storage
├── package.json                   # Root package.json (npm workspaces)
└── pyproject.toml                # Root Python configuration (uv workspace)
```

## Configuration

### Environment Setup
- Copy configuration examples from `packages/backend/config_example/` to `packages/backend/config/`
- Main config files: `base.py`, `llm.py`
- Database locations:
  - Memory DB: `memory_db/` (root level)
  - Session data: `data/` (root level)

### Google Services Integration
Many tools integrate with Google services via OAuth:
- Authentication tokens stored in `packages/backend/infrastructure/mcp/tools/google_auth/tokens/`
- Supports Gmail, Google Calendar, and Google Contacts
- Use `packages/backend/infrastructure/mcp/tools/google_auth/init_google_token.py` to set up authentication

## CLI Commands

- **Shell** (`!` prefix): `! git status` - Execute bash, results injected to LLM context
- **PFC Console** (`>` prefix): `> ball.count()` - Execute in PFC Python environment

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
- Configure preferred provider in `packages/backend/config/llm.py`
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
- **Not a workspace member**: pfc-server runs in PFC's Python environment
- **Dependency installation**: Run `pip install websockets==9.1` in PFC GUI
- **Server port**: Runs on port 9001 (WebSocket)
- **Startup**: Must be started in PFC GUI before using PFC tools
- **Long tasks**: Return task_id immediately for non-blocking operation
- **Troubleshooting**: Check `services/pfc-server/README.md`

## Code Modification Guidelines

When using batch commands (sed, find, etc.):
- Consider the context: Will regex affect type annotations, decorators, or critical syntax?
- Verify results: Check `git diff` samples and run imports/type checks on modified files
- For Pydantic models and base classes: prefer manual Edit to preserve structure

## Related Guides

- `.claude/guides/typescript-guide.md` - TypeScript/React patterns
- `.claude/guides/code-standards.md` - Code quality standards
- `services/pfc-server/README.md` - PFC integration details

## Git Commit Format

```
feat: brief description

Co-authored-with: Nagisa Toyoura <nagisa.toyoura@gmail.com>
```
