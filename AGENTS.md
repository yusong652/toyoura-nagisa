# AGENTS.md

Updated guidance for Codex when working on **toyoura-nagisa**. This project is now PFC-first; other standalone agent experiments are legacy and should not drive new work.

## Project Snapshot
- PFC-focused AI agent platform: documentation-driven, script-only workflow for ITASCA PFC (Particle Flow Code).
- Core philosophy: **Script is Context**—PFC operations are versioned Python scripts that become long-term context.
- Clean Architecture backend (FastAPI + UV) with pluggable multi-LLM stack (Gemini, Claude, OpenAI, local), MCP tool system, and ChromaDB-based long-term memory.
- Frontends: React 19 + Vite web app (Live2D/voice/TTS), Ink/React terminal CLI; shared TypeScript core SDK for WebSocket/API.

## Repository & Architecture
```
packages/
  backend/       # FastAPI, Clean Architecture layers (presentation/application/domain/infrastructure/shared/tests)
  web/           # React UI (src/, public/)
  cli/           # Terminal UI (Ink)
  core/          # Shared TS SDK (session/connection/api clients)
  memory_db/     # Qdrant/Chroma persistence helpers
  pfc_workspace/ # PFC session artifacts, scripts, checkpoints (workspace data)
services/
  pfc-server/    # Standalone WebSocket server running inside PFC Python env
memory_db/, data/ # Runtime storage (conversation + memory)
docs/, examples/, scripts/ # Reference and helper assets
```

**Backend highlights**
- **Agent system** (`packages/backend/application/services/agent.py`): orchestrates LLM streaming + tool loop; profile-driven tool loading.
- **LLM abstraction** (`infrastructure/llm/`): unified streaming client + provider adapters.
- **MCP tool system** (`infrastructure/mcp/`): FastMCP server, standardized `ToolResult`, categories: builtin, coding, lifestyle (legacy), pfc, agent.
- **PFC integration**: WebSocket client (`infrastructure/pfc/websocket_client.py`), PFC tools under `infrastructure/mcp/tools/pfc/`.
- **Monitoring** (`infrastructure/monitoring/`): iteration/todo/bash/PFC status monitors.
- **Memory** (`infrastructure/memory/`, `memory_db/`): ChromaDB-powered semantic + session memory.

**Frontend highlights**
- React Live2D chat UI with voice input + TTS, geolocation, and streaming WebSocket handling.
- CLI frontend for terminal-first chat; shared logic lives in `packages/core`.

**PFC server (external dependency)**
- Lives at `services/pfc-server/`; runs inside the PFC GUI Python environment with `websockets==9.1`.
- Handles main-thread execution, task queueing, script execution with output capture, and task status queries over `ws://localhost:9001`.

## Agent Model & PFC Workflow
- Primary profile: **PFC Expert** (keep this path first-class). Other standalone agents are legacy; avoid expanding them.
- SubAgent: **PFC Explorer** (read-only) for documentation/file lookup without polluting main context.
- Tool categories to know:
  - `pfc_query_command`, `pfc_query_python_api` → get syntax/examples.
  - `pfc_execute_task` → run Python script (test vs production via `run_in_background`), `pfc_check_task_status`/`pfc_list_tasks` → monitor.
  - Coding tools (`read`, `write`, `edit`, `bash`, `glob`, `grep`) remain for code changes; lifestyle tools exist but treat as secondary.
- Standard PFC flow: **Query → Test (small scale) → Production (background) → Monitor**. Always emit scripts that call `itasca.command(...)` rather than ad-hoc CLI strings.

## Development Commands
- Install: `npm install` (root workspaces), `uv sync` (Python deps under `packages/backend`).
- Run backend: `npm run dev:backend` (uv FastAPI) or `uv run python packages/backend/run.py`.
- Run frontend: `npm run dev:web`; run both: `npm run dev:all`. CLI: `npm run dev:cli`.
- Tests: `uv run pytest` (backend, includes `packages/backend/tests` and `tests/`), `npm run test:web` (Vite), lint: `npm run lint:web`, build: `npm run build` or `npm run build:all`.
- PFC server: in PFC Python console install `websockets==9.1`, then `exec(open(r'<repo>/services/pfc-server/start_server.py', encoding='utf-8').read())`.

## Coding Standards
- Python 3.10+, 4-space indent, aggressive type hints. Follow Clean Architecture boundaries: presentation → application → domain → infrastructure only.
- Use Ruff for checks/formatting when available; keep modules snake_case, classes PascalCase.
- TypeScript/React: components PascalCase, hooks/utilities camelCase. React 19 + Vite + MUI + PIXI Live2D.
- Keep system prompts/config in `packages/backend/config/`; copy from `config_example/` before running.
- Maintain standardized tool responses via `success_response`/`error_response` helpers.

## Testing & Quality
- Prefer `pytest` with descriptive names (`test_<feature>_<condition>`); cover tool flows, memory behavior, PFC task orchestration, and error paths.
- Frontend at minimum lint; add focused tests for rendering/interaction when touching UI logic.
- PFC integration tests require a running PFC server; document any manual runs in PR/notes.

## Security & Ops Notes
- Never commit secrets; keep API keys in env or untracked config. Ensure Live2D assets/memory snapshots stay out of VCS.
- pfc-server uses older websockets; do not mix its environment with the main UV workspace.
- Long-running/background work should use task IDs + status polling; avoid blocking calls in tools or handlers.
