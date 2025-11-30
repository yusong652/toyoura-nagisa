# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

toyoura-nagisa is an extensible, voice-enabled AI assistant with long-term memory and a dynamic tool-use framework. The project combines a Python FastAPI backend with a React frontend and features a sophisticated MCP (Model Context Protocol) for tool orchestration. The system follows clean architecture principles with clear separation of concerns.

## Development Commands

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

## Architecture Overview

### Backend Architecture (Clean Architecture)

- **Presentation Layer**: FastAPI routes, WebSocket handlers, and API models at `backend/presentation/`
- **Domain Layer**: Core business logic and models at `backend/domain/`
- **Infrastructure Layer**: External concerns at `backend/infrastructure/`:
  - **LLM Infrastructure**: Multi-provider LLM clients (Gemini, Anthropic, OpenAI, Local) with pluggable architecture
  - **MCP Server**: Dynamic tool orchestration system at `backend/infrastructure/mcp/smart_mcp_server.py`
  - **Memory System**: ChromaDB-based long-term memory
  - **TTS System**: Text-to-speech with local and remote providers
  - **Storage**: Image storage and session management
- **Configuration**: Environment-specific configs at `backend/config/`
- **Shared**: Common utilities and exceptions at `backend/shared/`

### LLM Infrastructure

- **Base Layer**: Common abstractions and interfaces at `backend/infrastructure/llm/base/`
- **Providers**: Specific LLM implementations at `backend/infrastructure/llm/providers/`:
  - `gemini/`: Google Gemini integration
  - `anthropic/`: Anthropic Claude integration  
  - `openai/`: OpenAI integration
  - `local/`: Local LLM support (vLLM, Ollama)
- **Shared Components**: Common utilities and constants at `backend/infrastructure/llm/shared/`

### Tool System

Modular tool architecture with categories in `backend/infrastructure/mcp/tools/`:

- `builtin`: Web search and core system tools
- `coding`: File operations, shell commands, Python execution
- `calendar`: Google Calendar integration
- `email_tools`: Email management via Gmail
- `contact_tools`: Google Contacts management
- `text_to_image`: Image generation tools
- `memory_tools`: Memory management operations
- `weather_tool`: Weather information services
- `time_tool`: Time and date utilities
- `calculator_tool`: Mathematical calculations
- `location_tool`: Geolocation services
- `places_tools`: Location and places services
- `meta_tool`: Tool discovery and management

### Frontend Architecture

- **React 19**: Modern React with TypeScript
- **Material-UI**: Component library for consistent UI
- **Live2D Integration**: Interactive character display
- **WebSocket**: Real-time communication with backend
- **Vite**: Development and build tooling

### Key Technologies

- **Python**: Backend with FastAPI, uvicorn, ChromaDB
- **React**: Frontend with TypeScript, Material-UI
- **FastMCP**: Model Context Protocol implementation
- **ChromaDB**: Vector database for memory and tool vectorization
- **WebSocket**: Real-time communication
- **Live2D**: Interactive character animations

## Configuration

### Environment Setup

- Copy `backend/config.example.py` to `backend/config.py`
- Set up LLM provider credentials (primarily Gemini)
- Configure TTS providers if needed
- Set up database paths and API keys

### LLM Configuration

The system supports multiple LLM providers with a pluggable architecture:

- **Gemini**: Primary provider with full feature support
- **Anthropic**: Claude integration with tool calling support
- **OpenAI**: GPT models with comprehensive API integration
- **Local**: vLLM and Ollama support for self-hosted models
- Configuration files in `backend/config/llm.py`

## Tool System

### Tool Vectorization

The system uses ChromaDB to vectorize tool descriptions for semantic search and dynamic tool selection:

- Tools are embedded into vector space for semantic matching
- LLM can query tool database to find relevant tools for tasks
- Dynamic tool loading based on user requests

### Tool Categories

Tools are organized into categories and can be loaded on-demand:

- `builtin`: Web search tools
- `calculator_tool`: Mathematical calculations
- `calendar`: Google Calendar integration
- `coding`: File operations, shell commands, Python execution
- `contact_tools`: Contact management
- `email_tools`: Email operations
- `location_tool`: Geolocation services
- `memory_tools`: Memory management
- `meta_tool`: Tool discovery and management
- `places_tools`: Location and places services
- `text_to_image`: Image generation
- `time_tool`: Time utilities
- `weather_tool`: Weather information

### Google Services Integration

Many tools integrate with Google services via OAuth:

- Authentication tokens stored in `backend/infrastructure/mcp/tools/google_auth/tokens/`
- Supports Gmail, Google Calendar, and Google Contacts
- Use `backend/infrastructure/mcp/tools/google_auth/init_google_token.py` to set up authentication

## Memory System

### Long-term Memory

- ChromaDB-based persistent memory
- Semantic similarity search for conversation context
- Session-based memory management
- Conversation history with image support

### Memory Database Location

- ChromaDB files stored in `backend/memory_db/`
- Tool vectorization DB in `backend/tool_db/`
- Session data in `backend/chat/data/`

## Development Patterns

### Message Handling

- Messages use factory pattern with `message_factory()` and `message_factory_no_thinking()`
- Support for text, image, and tool result messages
- Real-time streaming with WebSocket support

### Tool Integration

- Each tool category has its own registration function
- Tools follow FastMCP protocol
- Semantic search enables dynamic tool discovery

### Session Management

- UUID-based session identification
- Persistent chat history with metadata
- Session cleanup and tool cache management

## Testing

### Backend Testing

```bash
# Run all tests
uv run pytest

# Run tool vectorization tests
uv run python backend/infrastructure/mcp/test_vectorizer_search.py

# Check tool vectorization status
uv run python backend/infrastructure/mcp/check_tool_vectorization.py

# Initialize tool vectorization
uv run python backend/infrastructure/mcp/init_tool_vectorization.py
```

### Frontend Testing

The frontend uses standard React testing practices with Vite.

## Common Issues

### LLM Client Support

- **Gemini**: Full feature support with function calling and streaming
- **Anthropic**: Claude integration with tool calling and conversation context
- **OpenAI**: GPT models with complete API integration
- **Local**: vLLM and Ollama support for self-hosted deployments
- Configure preferred provider in `backend/config/llm.py`

### Tool Loading

- Tools are loaded dynamically based on session needs
- Tool cache is cleared when switching sessions
- MCP server runs on port 9000 for tool communication

### Memory Management

- ChromaDB handles both conversation memory and tool vectorization
- Session-based memory isolation
- Memory cleanup on session deletion

## File Structure Highlights

```
toyoura-nagisa/
├── backend/
│   ├── app.py                      # Main FastAPI application
│   ├── presentation/               # API routes and WebSocket handlers
│   │   ├── api/                   # REST API endpoints
│   │   ├── websocket/             # WebSocket connection management
│   │   └── streaming/             # Response streaming handlers
│   ├── domain/                     # Core business logic
│   │   └── models/                # Domain models and message factory
│   ├── infrastructure/             # External system integrations
│   │   ├── llm/                   # LLM provider integrations
│   │   │   ├── base/              # Common abstractions
│   │   │   ├── providers/         # Specific provider implementations
│   │   │   │   ├── gemini/        # Google Gemini client
│   │   │   │   ├── anthropic/     # Anthropic Claude client
│   │   │   │   ├── openai/        # OpenAI client
│   │   │   │   └── local/         # Local LLM support
│   │   │   └── shared/            # Common utilities
│   │   ├── mcp/                   # Model Context Protocol system
│   │   │   ├── smart_mcp_server.py # Main MCP server
│   │   │   ├── tool_vectorizer.py  # Tool semantic search
│   │   │   ├── tools/             # Tool implementations
│   │   │   └── utils/             # MCP utilities
│   │   ├── memory/                # ChromaDB memory system
│   │   ├── storage/               # File and session storage
│   │   └── tts/                   # Text-to-speech engines
│   ├── config/                     # Configuration management
│   ├── shared/                     # Common utilities and exceptions
│   ├── memory_db/                  # ChromaDB persistence
│   ├── tool_db/                    # Tool vectorization database
│   └── workspace/                  # Development workspace
├── frontend/
│   ├── src/
│   │   ├── components/            # React components
│   │   ├── contexts/              # React contexts
│   │   └── App.tsx               # Main application
│   └── package.json              # Frontend dependencies
└── pyproject.toml                # Python project configuration
```

## Development Notes

- **Clean Architecture**: Clear separation between presentation, domain, and infrastructure layers
- **Python Dependency Management**: Uses UV with `pyproject.toml` for modern Python packaging
- **Frontend Development**: Vite for fast development and building with TypeScript
- **Real-time Communication**: WebSocket for streaming responses and real-time features
- **LLM Flexibility**: Pluggable architecture supports multiple LLM providers seamlessly
- **Tool System**: Asynchronous MCP-based tools with semantic search and dynamic loading
- **Memory Architecture**: Multi-layer memory with ChromaDB for both conversation and tool vectorization
- **Character Animation**: Live2D integration using PIXI.js for interactive UI
- **UI Framework**: Material-UI for consistent React component styling
- **TTS Flexibility**: Support for both local (GPT-SoVITS) and remote (Fish Audio) TTS providers

## Configuration

### Environment Setup

- Copy configuration examples from `backend/config_example/` to `backend/config/`
- Main config files: `base.py`, `llm.py`, `tts.py`, `email.py`, `text_to_image.py`
- Database locations:
  - Memory DB: `backend/memory_db/`
  - Tool vectorization DB: `backend/tool_db/`
  - Session data: `backend/chat/data/`

## Code Quality Guidelines

### TypeScript Development Guidelines

When creating or refactoring TypeScript code in the frontend, provide explanations to help the user learn TypeScript principles:

- **Type System Explanations**: Explain TypeScript type concepts when implementing them (interfaces, types, generics, unions, etc.)
- **React TypeScript Patterns**: Explain React-specific TypeScript patterns (FC types, hook typing, event handlers, etc.)
- **Type Inference**: Explain when TypeScript can infer types vs when explicit typing is needed
- **Best Practices**: Explain why certain TypeScript patterns are preferred over others
- **Common Pitfalls**: Point out common TypeScript mistakes and how to avoid them

Example explanations:

- When using `React.FC<Props>`: "React.FC automatically provides children prop typing and return type"
- When using generics: "Generic type `<T>` allows this function to work with any data type while maintaining type safety"
- When using union types: "Union type `string | null` indicates this value can be either a string or null"

### Type Validation and Logic Redundancy

- **Avoid Redundant Validation**: Do not add type validation or existence checks for data structures that are already validated by our established logic flow
- **Trust Internal APIs**: Internal function calls within our controlled codebase should not re-validate data that has already been processed and validated
- **Readability Priority**: Excessive type checking and defensive programming significantly reduces code readability and maintainability
- **Focus on Business Logic**: Code should focus on the core business logic rather than redundant defensive checks
- **Example**: If a ToolResult object is passed from our standardized tool pipeline, trust that it contains the expected structure rather than re-validating every field

## Development Philosophy & Insights

### Recording Development Insights

We maintain a collection of insights and concepts in `.claude/insights/` to capture the evolution of our thinking during development. This approach allows us to:

- Version control our ideas alongside code
- Share team insights without external tools
- Search through concepts using standard text tools
- Track the progression of our architectural thinking

Key insights should be documented as they emerge during development discussions and code reviews.

### Tool System Evolution

Our tool system has evolved from dynamic discovery to static categorization based on real-world LLM limitations:

**Previous Approach**: Dynamic tool vectorization and semantic search

- Tools embedded in vector space for semantic matching
- LLM queries tool database to find relevant capabilities
- Complex but often imprecise tool selection

**Current Approach**: Static tool categories with intelligent composition

- Predetermined tool sets loaded by agent type
- Focus on creative combination rather than discovery
- Better reliability and performance with current LLM capabilities

**Rationale**: Current LLMs struggle with accurate tool discovery in large search spaces, leading to:

- Search precision issues
- Context pollution from too many tool descriptions
- Decision fatigue from excessive choices
- Semantic gaps between intent and tool descriptions

**Future Vision**: While static loading serves us now, true AGI will eventually enable:

- Accurate semantic tool discovery
- Dynamic tool creation for novel problems
- Self-improving tool selection strategies

This represents a pragmatic acknowledgment of current technology boundaries while maintaining vision for future capabilities.

## Git Configuration

When creating commits, do not use Claude's identity in commit messages. Instead of "Generated with Claude Code", use "Co-authored with Nagisa Toyoura" to reflect collaborative development. For example:

```
feat: improve tool extraction logic

Co-authored-with: Nagisa Toyoura <nagisa.toyoura@gmail.com>
```
