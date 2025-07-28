# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

aiNagisa is an extensible, voice-enabled AI assistant with long-term memory and a dynamic tool-use framework. The project combines a Python FastAPI backend with a React frontend and features a sophisticated MCP (Model Context Protocol) for tool orchestration.

## Development Commands

### Backend Development
```bash
# Start the backend server
uv run python backend/app.py

# Run the MCP server directly
uv run python backend/nagisa_mcp/smart_mcp_server.py

# Run tests
uv run pytest

# Install dependencies
uv sync
```

### Frontend Development
```bash
cd frontend-react

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

### Backend Architecture
- **FastAPI Application**: Main server at `backend/app.py`
- **MCP Server**: Dynamic tool orchestration system at `backend/nagisa_mcp/smart_mcp_server.py`
- **LLM Factory**: Multi-provider LLM support with focus on Gemini client
- **Memory System**: ChromaDB-based long-term memory at `backend/memory/`
- **TTS System**: Text-to-speech with multiple provider support
- **Tool System**: Modular tool architecture with categories:
  - builtin: Core system tools
  - email_tools: Email management
  - calendar: Calendar integration
  - coding: Code-related tools
  - text_to_image: Image generation
  - contact_tools: Contact management
  - places_tools: Location services
  - location_tool: Geolocation
  - memory_tools: Memory management
  - weather_tool: Weather information
  - time_tool: Time utilities
  - calculator_tool: Mathematical calculations
  - meta_tool: Tool discovery and management

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
The system primarily supports Gemini client. Other LLM clients have been deprecated in favor of the unified Gemini implementation.

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
- Authentication tokens stored in `backend/nagisa_mcp/tools/google_auth/tokens/`
- Supports Gmail, Google Calendar, and Google Contacts
- Use `init_google_token.py` to set up authentication

## Memory System

### Long-term Memory
- ChromaDB-based persistent memory
- Semantic similarity search for conversation context
- Session-based memory management
- Conversation history with image support

### Memory Database Location
- ChromaDB files stored in `backend/memory_db/`
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
uv run python backend/nagisa_mcp/test_vectorizer_search.py

# Test specific tools
uv run python backend/scripts/test_meta_tool_vector_search.py
uv run python backend/scripts/test_glob_tool.py
uv run python backend/scripts/test_grep_tool.py
uv run python backend/scripts/test_replace_tool.py

# Demo tool composition
uv run python backend/scripts/demo_tool_composition.py
```

### Frontend Testing
The frontend uses standard React testing practices with Vite.

## Common Issues

### LLM Client Support
- Gemini and Anthropic clients are fully supported in the current architecture
- OpenAI, Mistral, and local LLM (vLLM, Ollama) clients are also available
- Configure system to use preferred LLM client via config

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
aiNagisa/
├── backend/
│   ├── app.py                 # Main FastAPI application
│   ├── chat/                  # LLM clients and conversation management
│   │   ├── gemini/           # Gemini client implementation
│   │   └── llm_factory.py    # LLM client factory
│   ├── nagisa_mcp/           # MCP server and tool system
│   │   ├── smart_mcp_server.py # Main MCP server
│   │   ├── tool_vectorizer.py  # Tool semantic search
│   │   └── tools/            # Tool implementations
│   ├── memory/               # ChromaDB memory system
│   ├── tts/                  # Text-to-speech engines
│   └── config.py            # Configuration management
├── frontend-react/
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── contexts/         # React contexts
│   │   └── App.tsx          # Main application
│   └── package.json         # Frontend dependencies
└── pyproject.toml           # Python project configuration
```

## Development Notes

- The system uses UV for Python dependency management with `pyproject.toml`
- Frontend uses Vite for development and building with TypeScript
- WebSocket communication enables real-time features
- Tool system supports both synchronous and asynchronous operations
- Memory system provides both short-term (session) and long-term (persistent) storage
- Live2D integration for character animation using PIXI.js
- Material-UI for consistent React component styling
- ChromaDB for both conversation memory and tool vectorization

## Configuration

### Environment Setup
- Copy configuration examples from `backend/config_example/` to `backend/config/`
- Main config files: `base.py`, `llm.py`, `tts.py`, `email.py`, `text_to_image.py`
- Database locations:
  - Memory DB: `backend/memory_db/`
  - Tool vectorization DB: `backend/tool_db/`
  - Session data: `backend/chat/data/`

## Git Configuration

When creating commits, do not use Claude's identity in commit messages. Instead of "Generated with Claude Code", use "Co-authored with Nagisa Toyoura" to reflect collaborative development. For example:

```
feat: improve tool extraction logic

Co-authored-with: Nagisa Toyoura <nagisa.toyoura@gmail.com>
```