# Gemini Context: toyoura-nagisa Project

This document provides comprehensive architectural, philosophical, and development context for the Gemini AI agent to effectively understand, analyze, and contribute to the `toyoura-nagisa` project.

## 1. Core Philosophy & Value Proposition

**toyoura-nagisa** is a production-grade AI agent platform designed to bridge the gap between conversational AI and professional scientific computing. It is built on a foundation of architectural elegance, scalability, and deep domain expertise.

- **Agent Specialization**: The platform's core innovation is its **Agent Profile System**, which dynamically configures the AI's capabilities (i.e., available tools) based on the task domain (e.g., Coding, Scientific Simulation, Lifestyle). This optimizes context token usage and improves the relevance of the AI's responses.
- **SubAgent Delegation**: The platform extends specialization through a SubAgent system, where a primary agent can delegate specific, isolated tasks (like documentation lookup or code analysis) to specialized, lightweight agents. This preserves the primary agent's context and improves efficiency.
- **Clean Architecture**: The backend strictly adheres to a **Clean Architecture**, ensuring separation of concerns between the domain logic, application logic, and infrastructure. This makes the system highly maintainable, testable, and adaptable.
- **Unified LLM & Tooling**: A sophisticated abstraction layer allows for seamless switching between different LLM providers (Gemini, Anthropic, OpenAI, local models) and ensures that all tools adhere to a unified contract, regardless of the underlying provider.
- **Expert Workflows**: For specialized domains like scientific computing, the platform defines expert workflows and mental models (e.g., the PFC three-phase workflow) that guide the AI to behave like a domain expert, not just a tool executor.

## 2. Agent Philosophy & Expert Workflows

Understanding the project requires adopting specific mental models, especially for complex domains like the PFC integration.

### 2.1. The PFC Expert: A State-Evolution Mental Model

The `PFC Expert` profile operates on a principle fundamentally different from typical file-based coding tasks.

**CRITICAL INSIGHT: A PFC simulation is a STATEFUL DYNAMIC SYSTEM.**

- **Static Mindset (for code)**: Files are static. Reading a file gives the same content. Order of operations is flexible.
- **Dynamic Mindset (for PFC)**: The simulation is a timeline. Every command permanently changes the state. Order of operations is critical. The agent's primary context is the **evolution of the simulation state**.

### 2.2. The Script-Only PFC Workflow

To manage this stateful interaction, the agent follows a documentation-driven, script-based workflow.

- **Phase 1: QUERY (`pfc_query_command`/`pfc_query_python_api`)**: Look up command syntax and Python API examples from documentation.
- **Phase 2: TEST (`pfc_execute_task` with small scale)**: Write and execute a small-scale test script to validate the approach.
- **Phase 3: PRODUCTION (`pfc_execute_task` with `run_in_background=True`)**: Execute a full-scale simulation with git snapshot for reproducibility.

## 3. System Architecture

### 3.1. Backend: Clean Architecture

The backend follows a strict dependency rule where dependencies point inwards towards the `Domain`.

- **`Presentation` (`/backend/presentation`)**: Handles HTTP requests and WebSocket connections. It calls services in the `Application` layer.
- **`Application` (`/backend/application`)**: Contains the application-specific business logic (Services/Use Cases). It orchestrates the `Domain` models to perform tasks.
- **`Domain` (`/backend/domain`)**: Contains the core, enterprise-wide business models (Entities). It is pure and has no dependencies on any other layer.
- **`Infrastructure` (`/backend/infrastructure`)**: Implements logic for interacting with external systems (LLMs, databases, tool servers). It depends on the `Domain` and implements interfaces used by the `Application` layer.

### 3.2. The Unified LLM Abstraction

This architecture allows the application to treat all LLM providers identically. The system uses a clean separation between infrastructure and application layers.

- **Infrastructure Layer** (`backend/infrastructure/llm/base/client.py`): The `LLMClientBase` abstract class provides stateless API interfaces (`call_api_with_context`, `call_api_with_context_streaming`). Provider-specific subclasses implement the low-level details (API calls, data formatting).
- **Application Layer** (`backend/application/services/agent.py`): The `Agent` class implements business logic including the tool calling loop, streaming orchestration, and conversation management. This separation follows the **Inversion of Control** pattern.

### 3.3. SubAgent Delegation

A key architectural feature is the ability for the main agent (the "MainAgent") to delegate tasks to specialized, lightweight "SubAgents". This is achieved via the `invoke_agent` tool. This pattern is critical for optimizing context window usage and focusing the MainAgent on its core task.

- **Core Principle**: Instead of loading the MainAgent's context with extensive documentation or file content, it can spawn a SubAgent to perform the research and return a concise summary.

- **Example: `pfc_explorer`**: A prime example is the `pfc_explorer` SubAgent. It is a read-only agent designed to search PFC documentation and workspace files. It can find relevant information without modifying any files or simulation states, and without cluttering the MainAgent's thought process.

**SubAgent Characteristics:**

- **Invocation**: SubAgents are invoked by the MainAgent using the `invoke_agent` tool, specifying a `subagent_type` (e.g., `"pfc_explorer"`) and a `prompt` for the task.
- **Stateless & Non-Persistent**: SubAgents are designed for one-off tasks. They do not have persistent sessions, and their work is stored in-memory, which is cleared upon completion.
- **Non-Streaming & Synchronous**: To improve efficiency and simplify the flow, SubAgents execute their tasks synchronously and do not stream responses back to the MainAgent. They return a single, final result.
- **Isolated & Read-Only**: SubAgents operate in an isolated context. They are generally read-only and are prevented from using destructive tools like `write` or `pfc_execute_task`. Crucially, they cannot use `invoke_agent` themselves, preventing recursive loops.
- **Configuration**: SubAgent behaviors are defined in `SubAgentConfig` classes within `packages/backend/domain/models/agent_profiles.py`. This is where their tools, prompts, and iteration limits are set.
- **Observability**: The frontend can monitor SubAgent progress. The backend emits `SUBAGENT_TOOL_USE` events via WebSockets, allowing the UI to display nested tool calls in real-time.
- **Secondary Models**: The system can be configured to use smaller, faster, and more cost-effective LLM models for SubAgents, reserving the more powerful primary model for the MainAgent's complex reasoning tasks.

## 4. Deep Dive: Model Context Protocol (MCP) Architecture

The MCP system is the heart of the agent's tool-use capability. It is a highly modular and scalable system for defining, registering, and executing tools.

### 4.1. The End-to-End Tool Flow

1.  **Registration**: On startup, the `smart_mcp_server.py` imports registration functions from each tool category (e.g., `register_coding_tools`) and registers *all* available tools with a central `FastMCP` instance.
2.  **Profile Definition**: The `ToolProfileManager` defines which tool *names* belong to which agent profile (`CODING`, `PFC`, etc.). This now also includes `SubAgentConfig` definitions.
3.  **Dynamic Selection**: When an LLM call is made:
    a. The `BaseToolManager` gets the list of tool names for the active profile from the `ToolProfileManager`.
    b. It queries the `FastMCP` server to get the standardized schemas for only those tools.
4.  **Provider Formatting**: The provider-specific tool manager (e.g., `GeminiToolManager`) converts the standardized schemas into the exact format required by the target LLM API.

### 4.2. Anatomy of a Tool

The `write` tool (`backend/infrastructure/mcp/tools/coding/tools/write.py`) is a perfect example of the standard tool implementation pattern:

1.  **The Tool Function**: A standard Python function whose arguments are type-hinted with Pydantic's `Field` to define the input schema. The function's docstring serves as its description for the LLM.
    ```python
    def write(
        file_path: str = Field(..., description="..."),
        content: str = Field(..., description="..."),
    ) -> Dict[str, Any]:
        # ... implementation ...
    ```

2.  **Security & Validation**: The function body includes robust security checks (e.g., ensuring paths are within the workspace) and detailed error handling.

3.  **Unified Response**: The function returns a standardized dictionary by calling `success_response` or `error_response` from `backend/infrastructure/mcp/utils/tool_result.py`. This ensures all tools have a consistent return format.

4.  **The Registration Helper**: A simple function that uses the `@mcp.tool` decorator to register the tool function with the `FastMCP` instance.
    ```python
    def register_write_tool(mcp: FastMCP):
        mcp.tool(tags={...}, annotations={...})(write)
    ```

5.  **Category Aggregation**: The `register_write_tool` function is then called by the aggregate `register_coding_tools` function in `backend/infrastructure/mcp/tools/coding/tools/__init__.py`, which is in turn called by the main `smart_mcp_server.py`.

This modular, registration-based pattern makes the system extremely easy to extend.

## 5. Development Workflow & Commands

The project is a monorepo. Commands should be run from the project root unless specified otherwise.

### 5.1. Running the Full Application (Web + Backend)

To run the web interface and the backend services together for standard development:

```bash
# From the project root
npm run dev:all
```

This uses `concurrently` to start both the React frontend and the Python backend.

### 5.2. Backend Development (Python)

- **Running Standalone**: `npm run dev:backend`
- **Package Management**: `uv` (`uv sync`)
- **Linting & Formatting**: `ruff` (`ruff check . && ruff format .` in `packages/backend`)
- **Testing**: `pytest` (`uv run pytest`)

### 5.3. Frontend Development (React)

- **Running Standalone**: `npm run dev:web`
- **Package Management**: `npm`
- **Linting**: `ESLint` (`npm run lint:web`)
- **Testing**: `npm run test:web`

### 5.4. CLI Development (React/Ink)

The CLI provides a terminal-based interface for interacting with the agent.

- **Running in Dev Mode**: `npm run dev:cli`
- **Building**: `npm run build:cli`
- **Running Compiled CLI**: After building, the CLI can be run with `npm -w @toyoura-nagisa/cli run start`. The compiled entry point is `packages/cli/dist/index.js`.

## 6. How to Contribute

### Adding a New Tool

1.  Create a new file for your tool (e.g., `my_tool.py`) inside the appropriate category in `backend/infrastructure/mcp/tools/`.
2.  In that file, define your tool function (with Pydantic-annotated arguments) and its registration helper function (e.g., `register_my_tool`).
3.  In the `__init__.py` for that tool category, import and call your new registration helper inside the aggregate registration function (e.g., `register_coding_tools`).
4.  Finally, add your new tool's name to the desired profiles in `backend/domain/models/agent_profiles.py`.

## 7. Guiding Principles for Analyzing `toyoura-nagisa`

To effectively contribute to `toyoura-nagisa`, the agent must move beyond surface-level documentation and conversational inference. It must adopt the mindset of a software archaeologist, digging into the codebase to uncover the ground truth. The following principles, derived from analyzing the project's structure, serve as a guide for this deep analysis.

### Principle 1: Assume Abstraction
The `toyoura-nagisa` architecture heavily favors abstraction (e.g., `LLMClientBase`, `mem0` for memory). When investigating a feature, do not search for direct, low-level implementation details (like a raw API call). Instead, assume an abstraction layer exists. The primary task is to **find the seam**: identify the key "manager," "client," or "service" module that acts as a facade over the underlying dependency.

### Principle 2: Configuration is the Source of Truth
Implementation logic can be complex and distributed. In contrast, configuration files provide direct, unambiguous evidence of what the system uses.
- **Prioritize Inspection**: Always inspect configuration files (`config/`, `config_example/`, `pyproject.toml`) early in the analysis.
- **Look For**: Model names (e.g., `gemini-embedding-001`), external service endpoints, API keys, and feature flags. These are often the most direct clues to how a feature is implemented.

### Principle 3: Employ a Hypothesis-Driven Search Strategy
Do not search blindly. Form a hypothesis and test it systematically.
1.  **Form Hypothesis**: Based on the architecture, make an educated guess (e.g., "The memory feature is likely implemented in `backend/infrastructure/memory/`").
2.  **Broad Search**: Use general terms (e.g., `embedding`, `memory`, `vector`) within the hypothesized directory to discover relevant files and modules.
3.  **Narrow Search**: Once a key module or configuration file is identified, use specific terms to pinpoint the exact lines of code or configuration values.

By adhering to these principles, the agent can build a resilient and accurate mental model of the project, grounded in verifiable evidence from the code itself, rather than relying on potentially incomplete or outdated secondary information.