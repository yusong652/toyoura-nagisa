# Project Separation Plan

## Overview

Separate toyoura-nagisa into two focused repositories:
- **toyoura-nagisa**: PFC Expert Agent (论文专用)
- **nagisa-assistant** (new): Lifestyle Assistant

---

## File Classification

### To REMOVE from toyoura-nagisa (migrate to nagisa-assistant)

#### 1. Lifestyle Tools (`packages/backend/infrastructure/mcp/tools/lifestyle/`)
```
tools/lifestyle/
├── tools/
│   ├── calendar/        # Google Calendar CRUD
│   ├── contacts/        # Google Contacts
│   ├── places/          # Google Places search
│   ├── location/        # Location services
│   ├── time/            # Time utilities
│   ├── text_to_image/   # ComfyUI image generation
│   └── image_to_video/  # ComfyUI video generation
└── __init__.py
```

#### 2. Google Auth Infrastructure (`packages/backend/infrastructure/auth/`)
```
infrastructure/auth/
├── google/
│   └── oauth.py         # Google OAuth for Gmail/Calendar/Contacts
└── __init__.py
```

#### 3. Lifestyle-specific Configs (`packages/backend/config/`)
```
config/
└── text_to_image.py     # ComfyUI configuration (if exists)
```

### To KEEP in toyoura-nagisa

#### 1. PFC Tools (`packages/backend/infrastructure/mcp/tools/pfc/`)
```
tools/pfc/
├── pfc_browse_commands.py
├── pfc_browse_python_api.py
├── pfc_browse_reference.py
├── pfc_query_command.py
├── pfc_query_python_api.py
├── pfc_execute_task.py
├── pfc_check_task_status.py
├── pfc_list_tasks.py
├── pfc_interrupt_task.py
└── pfc_capture_plot.py
```

#### 2. Coding Tools (`packages/backend/infrastructure/mcp/tools/coding/`)
```
tools/coding/
├── write.py
├── read.py
├── edit.py
├── bash.py
├── glob.py
└── grep.py
```

#### 3. Agent Tools (`packages/backend/infrastructure/mcp/tools/agent/`)
```
tools/agent/
└── invoke_agent.py      # SubAgent delegation
```

#### 4. Planning Tools (`packages/backend/infrastructure/mcp/tools/planning/`)
```
tools/planning/
└── todo_write.py
```

#### 5. Builtin Tools (`packages/backend/infrastructure/mcp/tools/builtin/`)
```
tools/builtin/
├── web_search.py
└── web_fetch.py
```

#### 6. PFC Bridge (standalone `pfc-mcp` repository)
```
pfc-mcp (external repo):
└── pfc-bridge/
├── server/              # WebSocket bridge runtime
├── workspace_template/  # Workspace bootstrap assets
├── start_bridge.py      # PFC GUI startup entry
└── README.md
```

#### 7. PFC Documentation (`packages/backend/infrastructure/pfc/`)
```
infrastructure/pfc/
├── commands/            # 115 command docs
├── python_api/          # 1006 API docs
├── reference/           # Reference materials
└── websocket_client.py
```

#### 8. Core Infrastructure (Shared, Keep)
```
infrastructure/
├── llm/                 # All LLM providers
├── mcp/mcp_server.py    # MCP server core
├── memory/              # ChromaDB memory
├── storage/             # Session storage
├── messaging/           # Message queue
├── websocket/           # WebSocket management
├── shell/               # Shell executor
├── monitoring/          # Status monitoring
└── file_mention/        # File mention processor
```

---

## Code Changes Required

### 1. Agent Configuration (`packages/backend/domain/models/agent_profiles.py`)

**Current state**:
- Single main agent config: `MAIN_AGENT_CONFIG` (PFC Expert)
- SubAgents: `pfc_explorer`, `pfc_diagnostic`
- Legacy profiles removed (no lifestyle/general/disabled)

### 2. Tool Manager

Update tool loading to skip non-existent lifestyle tools.

### 3. Configuration

Remove or make optional:
- Google Maps API key dependency
- ComfyUI configuration

### 4. Frontend (if needed)

Remove lifestyle-related UI components if any.

---

## Separation Steps

### Phase 1: Create New Repository

```bash
# 1. Create nagisa-assistant repository on GitHub
gh repo create nagisa-assistant --private --description "Personal lifestyle AI assistant"

# 2. Initialize with basic structure
mkdir nagisa-assistant
cd nagisa-assistant
git init
```

### Phase 2: Migrate Lifestyle Code

```bash
# 1. Copy lifestyle tools
cp -r toyoura-nagisa/packages/backend/infrastructure/mcp/tools/lifestyle nagisa-assistant/packages/backend/infrastructure/mcp/tools/

# 2. Copy auth infrastructure
cp -r toyoura-nagisa/packages/backend/infrastructure/auth nagisa-assistant/packages/backend/infrastructure/

# 3. Copy relevant configs
```

### Phase 3: Clean toyoura-nagisa

```bash
# 1. Remove lifestyle tools
rm -rf packages/backend/infrastructure/mcp/tools/lifestyle

# 2. Remove auth infrastructure (Google OAuth for lifestyle)
rm -rf packages/backend/infrastructure/auth

# 3. Confirm agent_profiles.py uses main config + SubAgents only

# 4. Update CLAUDE.md to reflect PFC-only focus
```

### Phase 4: Verify

```bash
# 1. Run tests
uv run pytest

# 2. Start backend
npm run dev:backend

# 3. Test main agent config
# Send a test message with the PFC Expert agent
```

---

## Timeline

| Step | Task | Estimated |
|------|------|-----------|
| 1 | Create nagisa-assistant repo | Quick |
| 2 | Migrate lifestyle code | Quick |
| 3 | Clean toyoura-nagisa | Quick |
| 4 | Update agent_profiles.py | Quick |
| 5 | Update CLAUDE.md | Quick |
| 6 | Verify backend works | Quick |
| 7 | Commit changes | Quick |

---

## Post-Separation

### toyoura-nagisa Focus
- PFC Expert Agent for paper
- Ablation experiments
- Model comparison
- Documentation

### nagisa-assistant Future
- Personal lifestyle assistant
- Email/Calendar/Contacts
- Image/Video generation
- Independent development

---

## Open Questions

1. **Repository visibility**: Private or public for nagisa-assistant?
2. **Shared dependencies**: Extract common infra to shared package later?
3. **Frontend split**: Does frontend need any changes?
