# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

aiNagisa is an extensible, voice-enabled AI assistant with long-term memory and a dynamic tool-use framework. The project combines a Python FastAPI backend with a React frontend and features a sophisticated MCP (Model Context Protocol) for tool orchestration. The system follows clean architecture principles with clear separation of concerns.

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
- `lifestyle`: Lifestyle and productivity tools including:
  - `calendar`: Google Calendar integration
  - `contacts`: Google Contacts management
  - `email`: Email management via Gmail
  - `location`: Geolocation services
  - `places`: Location and places services
  - `text_to_image`: Image generation tools
  - `time`: Time and date utilities

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
- **ChromaDB**: Vector database for long-term memory
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

### Agent-Based Tool Loading
The system uses agent types to automatically load appropriate tool sets:
- Tools are organized by category (coding, communication, media, etc.)
- Agent types determine which tool categories to load
- Dynamic tool activation based on agent specialization

### Tool Categories
Tools are organized into categories and can be loaded on-demand:
- `builtin`: Web search tools
- `coding`: File operations, shell commands, Python execution
- `lifestyle`: Lifestyle and productivity tools including:
  - `calendar`: Google Calendar integration
  - `contacts`: Contact management
  - `email`: Email operations
  - `location`: Geolocation services
  - `places`: Location and places services
  - `text_to_image`: Image generation
  - `time`: Time utilities

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
- ChromaDB handles conversation memory and long-term context
- Session-based memory isolation
- Memory cleanup on session deletion

## File Structure Highlights

```
aiNagisa/
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
│   │   │   ├── tools/             # Tool implementations
│   │   │   └── utils/             # MCP utilities
│   │   ├── memory/                # ChromaDB memory system
│   │   ├── storage/               # File and session storage
│   │   └── tts/                   # Text-to-speech engines
│   ├── config/                     # Configuration management
│   ├── shared/                     # Common utilities and exceptions
│   ├── memory_db/                  # ChromaDB persistence
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
- **Memory Architecture**: Multi-layer memory with ChromaDB for conversation history and context
- **Character Animation**: Live2D integration using PIXI.js for interactive UI
- **UI Framework**: Material-UI for consistent React component styling
- **TTS Flexibility**: Support for both local (GPT-SoVITS) and remote (Fish Audio) TTS providers

## Code Quality Guidelines

### TypeScript Development Guidelines

When creating or refactoring TypeScript code in the frontend, provide comprehensive explanations to help the user systematically learn TypeScript principles through hands-on project work.

#### Core Learning Objectives

**IMPORTANT**: Every TypeScript file creation/modification should be a learning opportunity. Always provide detailed explanations covering:

1. **Type System Mastery**: Deep understanding of TypeScript's type system
2. **React Integration**: Mastery of React-TypeScript patterns
3. **Component Architecture**: Advanced component design principles
4. **Hook Patterns**: Custom hooks with proper typing
5. **Error Prevention**: Type safety best practices

#### Detailed Explanation Requirements

##### 1. Type System Concepts
When implementing any type construct, explain in detail:

- **Interfaces vs Types**: 
  ```typescript
  // Interface (extensible, declaration merging)
  interface UserProps {
    name: string
    age: number
  }
  
  // Type alias (more flexible, union types)
  type Status = 'loading' | 'success' | 'error'
  ```
  Explain: "Interface is preferred for object shapes that might be extended, while type aliases work better for unions and computed types."

- **Generic Types**: 
  ```typescript
  function useApi<T>(endpoint: string): ApiResponse<T>
  ```
  Explain: "Generic `<T>` allows this hook to work with any data type while preserving type safety. The actual type is determined at call-site."

- **Union and Intersection Types**:
  ```typescript
  type MessageSender = 'user' | 'bot'  // Union
  type EnhancedMessage = Message & { metadata: any }  // Intersection
  ```
  Explain: "Union types represent 'OR' relationships, intersection types represent 'AND' relationships."

- **Conditional Types**:
  ```typescript
  type ApiResponse<T> = T extends string ? { text: T } : { data: T }
  ```
  Explain: "Conditional types enable type logic - different return types based on input type conditions."

##### 2. React-TypeScript Patterns
For every React component, explain:

- **Component Typing**:
  ```typescript
  // Functional Component with Props
  const MessageItem: React.FC<MessageItemProps> = ({ message, onSelect }) => {
    // React.FC provides: children?, displayName, defaultProps
    // Automatically infers return type as JSX.Element | null
  }
  
  // Alternative (more explicit)
  const MessageItem = ({ message, onSelect }: MessageItemProps): JSX.Element => {
    // More explicit about return type, no automatic children prop
  }
  ```
  Explain: "React.FC is convenient but adds implicit children prop. Explicit typing gives more control."

- **Props Interface Design**:
  ```typescript
  interface MessageItemProps {
    message: Message                          // Required object
    onSelect: (id: string | null) => void     // Function signature
    selectedId?: string | null               // Optional prop
    children?: React.ReactNode               // Explicit children when needed
  }
  ```
  Explain: "Props interface defines the contract. Optional props use `?`, functions include full signature for type safety."

- **Event Handler Typing**:
  ```typescript
  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    // e has all button-specific mouse event properties
    e.preventDefault()  // TypeScript knows this method exists
  }
  
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value  // TypeScript knows target is HTMLInputElement
  }
  ```
  Explain: "Generic event types provide element-specific properties and methods."

##### 3. Hook Patterns and Custom Hooks
For every hook implementation, explain:

- **Custom Hook Typing**:
  ```typescript
  // Return type interface for clarity
  interface UseMessageStateReturn {
    displayText: string
    isLoading: boolean
    error: string | null
  }
  
  const useMessageState = (messageId: string): UseMessageStateReturn => {
    const [displayText, setDisplayText] = useState<string>('')
    // useState<string> is explicit - TypeScript could infer from initial value
    
    return {
      displayText,
      isLoading,
      error
    }
  }
  ```
  Explain: "Custom hooks should have clear return type interfaces. State typing can be explicit or inferred."

- **Hook Dependencies and Callbacks**:
  ```typescript
  const useMessageEvents = (
    message: Message,
    onSelect: (id: string | null) => void
  ): MessageEventHandlers => {
    
    // useCallback with dependency typing
    const handleClick = useCallback((e: React.MouseEvent) => {
      onSelect(message.id)
    }, [message.id, onSelect])  // Dependencies must match types used inside
    
    return { handleClick }
  }
  ```
  Explain: "useCallback dependencies array must include all values used inside the callback. TypeScript helps catch missing dependencies."

##### 4. Component Architecture Patterns
For component design, explain:

- **Composition Patterns**:
  ```typescript
  // Base props that can be extended
  interface BaseComponentProps {
    className?: string
    children?: React.ReactNode
  }
  
  // Extended props using intersection
  interface MessageTextProps extends BaseComponentProps {
    content: string
    variant?: 'default' | 'streaming'
  }
  ```
  Explain: "Extending interfaces creates component hierarchies. Base props provide common functionality."

- **Render Props Pattern**:
  ```typescript
  interface RenderProps<T> {
    data: T
    loading: boolean
    error: string | null
  }
  
  interface DataProviderProps<T> {
    render: (props: RenderProps<T>) => JSX.Element
    endpoint: string
  }
  ```
  Explain: "Render props pattern uses generics to provide type-safe data passing to render functions."

- **Discriminated Unions for Variants**:
  ```typescript
  type MessageVariant = 
    | { type: 'text'; content: string }
    | { type: 'file'; files: File[] }
    | { type: 'tool'; toolState: ToolState }
  
  const MessageRenderer = ({ variant }: { variant: MessageVariant }) => {
    switch (variant.type) {
      case 'text':
        return <TextMessage content={variant.content} />  // TypeScript knows content exists
      case 'file':
        return <FileMessage files={variant.files} />      // TypeScript knows files exists
      case 'tool':
        return <ToolMessage toolState={variant.toolState} /> // TypeScript knows toolState exists
    }
  }
  ```
  Explain: "Discriminated unions enable type-safe variant handling. TypeScript narrows types in each case."

##### 5. Advanced Type Techniques
Explain advanced patterns when encountered:

- **Mapped Types**:
  ```typescript
  // Make all properties optional
  type Partial<T> = {
    [P in keyof T]?: T[P]
  }
  
  // Make all properties required
  type Required<T> = {
    [P in keyof T]-?: T[P]
  }
  ```
  Explain: "Mapped types transform existing types. `keyof T` gets all property names, `T[P]` gets property type."

- **Template Literal Types**:
  ```typescript
  type EventName = 'click' | 'hover' | 'focus'
  type HandlerName = `on${Capitalize<EventName>}`  // 'onClick' | 'onHover' | 'onFocus'
  ```
  Explain: "Template literal types enable string manipulation at the type level."

- **Conditional Type Utilities**:
  ```typescript
  type NonNullable<T> = T extends null | undefined ? never : T
  type ReturnType<T> = T extends (...args: any[]) => infer R ? R : any
  ```
  Explain: "Utility types use conditional types and `infer` to extract or transform types."

#### Practical Learning Examples

When creating files, use these teaching moments:

##### Component Example with Full Explanation:
```typescript
import React, { useState, useCallback } from 'react'

// Props interface - define the contract
interface MessageTextProps {
  content: string                    // Required: message text content  
  className?: string                // Optional: CSS class for styling
  onContentChange?: (text: string) => void  // Optional: callback when content changes
}

/**
 * Message text display component with TypeScript best practices.
 * 
 * This component demonstrates:
 * - Interface-based props typing
 * - Optional vs required props  
 * - Event handler typing
 * - State management with explicit types
 * - Callback memoization with useCallback
 */
const MessageText: React.FC<MessageTextProps> = ({ 
  content, 
  className = 'message-text',  // Default value for optional prop
  onContentChange 
}) => {
  // State with explicit typing (could be inferred from initial value)
  const [isEditing, setIsEditing] = useState<boolean>(false)
  
  // Callback with proper dependencies for performance
  const handleEdit = useCallback(() => {
    setIsEditing(true)
    onContentChange?.(content)  // Optional chaining for optional callback
  }, [content, onContentChange])  // Dependencies ensure callback updates when props change
  
  return (
    <div className={className} onClick={handleEdit}>
      {content}
    </div>
  )
}

export default MessageText
```

**Learning Points Explained:**
- Interface design for component contracts
- Optional props with default values
- State typing strategies (explicit vs inferred)
- Callback memoization and dependency management
- Optional chaining for optional props

##### Hook Example with Full Explanation:
```typescript
import { useState, useEffect, useCallback } from 'react'

// Clear return type interface
interface UseApiReturn<T> {
  data: T | null
  loading: boolean
  error: string | null
  refetch: () => void
}

/**
 * Generic API hook demonstrating TypeScript patterns.
 * 
 * Generic type T allows this hook to work with any data type
 * while maintaining complete type safety throughout.
 */
function useApi<T>(endpoint: string): UseApiReturn<T> {
  // State with explicit generic typing
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  
  // Memoized fetch function
  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    
    try {
      const response = await fetch(endpoint)
      const result: T = await response.json()  // Type assertion based on generic
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }, [endpoint])
  
  useEffect(() => {
    fetchData()
  }, [fetchData])
  
  return {
    data,
    loading, 
    error,
    refetch: fetchData
  }
}
```

**Learning Points Explained:**
- Generic functions enable reusable, type-safe code
- State typing with union types (T | null)
- Error handling with type guards (instanceof Error)
- Effect dependencies and callback memoization
- Return type interfaces for clarity

#### Error Prevention and Best Practices

Always explain these critical concepts:

1. **Strict Type Checking**: Explain why strict mode helps catch errors
2. **Null Safety**: Show proper null/undefined handling  
3. **Type Guards**: Demonstrate runtime type checking
4. **Generic Constraints**: Use bounded generics when appropriate
5. **Import/Export Patterns**: Proper module typing

#### Assessment Questions

After explaining concepts, ask learning questions:
- "Why did we choose an interface over a type alias here?"
- "What would happen if we removed this generic constraint?"
- "How does TypeScript help prevent this runtime error?"
- "What are the trade-offs between these two typing approaches?"

This approach ensures every TypeScript interaction becomes a structured learning opportunity, building expertise through practical application in the aiNagisa project.

### Type Validation and Logic Redundancy
- **Avoid Redundant Validation**: Do not add type validation or existence checks for data structures that are already validated by our established logic flow
- **Trust Internal APIs**: Internal function calls within our controlled codebase should not re-validate data that has already been processed and validated
- **Readability Priority**: Excessive type checking and defensive programming significantly reduces code readability and maintainability
- **Focus on Business Logic**: Code should focus on the core business logic rather than redundant defensive checks
- **Example**: If a ToolResult object is passed from our standardized tool pipeline, trust that it contains the expected structure rather than re-validating every field

## Configuration

### Environment Setup
- Copy configuration examples from `backend/config_example/` to `backend/config/`
- Main config files: `base.py`, `llm.py`, `tts.py`, `email.py`, `text_to_image.py`
- Database locations:
  - Memory DB: `backend/memory_db/`
  - Session data: `backend/chat/data/`

## Code Documentation Standards

### Function Documentation Requirements

All functions MUST follow these documentation standards:

#### Type Annotations
- **Required**: All function parameters and return types must have explicit type annotations
- **Imports**: Import all required types from `typing` or appropriate modules
- **Specificity**: Use specific types (e.g., `CallToolResult`) rather than generic `Any` when possible

#### Docstring Format
```python
def function_name(param: SpecificType) -> ReturnType:
    """
    Brief function description in imperative mood.
    
    Detailed explanation of function behavior, including any important
    implementation details or architectural considerations.
    
    Args:
        param: Description with structure details when applicable:
            - field1: Description of nested field
            - field2: Description of nested field
    
    Returns:
        ReturnType: Description with complete structure:
            - field1: Type - Description
            - field2: Type - Description
            - field3: Optional[Type] - Description when optional
    
    Example:
        # Practical usage example when helpful
        result = function_name(example_param)
        
    Note:
        Important implementation notes or cross-references to related modules.
    """
```

#### Documentation Quality Standards
- **Language**: Professional English, concise and effective
- **Structure**: Clear Args/Returns sections with nested field descriptions
- **Cross-references**: Reference related modules/classes when relevant
- **Examples**: Include practical examples for complex functions
- **Return Structure**: Document complete return structure matching actual models (e.g., ToolResult schema)

#### Example Implementation
```python
from typing import Dict, Any
from mcp.types import CallToolResult

def extract_tool_result_from_mcp(result: CallToolResult) -> Dict[str, Any]:
    """
    Extract ToolResult object from MCP CallToolResult response.
    
    Parses standardized ToolResult JSON from MCP CallToolResult.content[0].text
    and applies MCP error flags when necessary.
    
    Args:
        result: MCP CallToolResult object with structure:
            - content: List[ContentBlock] containing TextContent
            - isError: bool indicating MCP-level error
    
    Returns:
        Dict[str, Any]: ToolResult dictionary with structure:
            - status: Literal["success", "error"] - Operation outcome
            - message: str - User-facing summary for display
            - llm_content: Optional[Any] - Structured data for LLM conversation
            - data: Optional[Dict[str, Any]] - Tool-specific payload and metadata
            - error: Optional[str] - Detailed error info when status="error"
            - is_error: bool - Added when MCP marks result as error
    
    Note:
        All tools return ToolResult.model_dump() as standardized JSON,
        ensuring consistent structure across the MCP ecosystem.
    """
```

## Git Configuration

### Commit Message Requirements

When creating commits, follow these guidelines for attribution and project identification:

1. **Project Attribution**: Always reference the aiNagisa project repository URL `https://github.com/yusong652/aiNagisa` in commit messages rather than external tools
2. **Co-authorship**: Use "Co-authored-with: Nagisa Toyoura" to reflect collaborative development instead of external tool attribution
3. **Project Context**: Ensure commit messages reflect the aiNagisa project context and goals

Example commit format:
```
feat: improve tool extraction logic

Enhance MCP tool result processing for better LLM integration
in the aiNagisa voice-enabled AI assistant.

https://github.com/yusong652/aiNagisa

Co-authored-with: Nagisa Toyoura <nagisa.toyoura@gmail.com>
```
