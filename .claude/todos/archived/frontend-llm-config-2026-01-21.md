# Frontend LLM Configuration Feature

**Date**: 2026-01-21
**Status**: Planning
**Estimated Effort**: 3-4 weeks

## Overview

Enable users to configure LLM provider and model through the frontend UI (Web/CLI), while keeping advanced configuration options in config files. This provides a more elegant user experience and eliminates the need for users to manually edit configuration files for basic settings.

## Design Goals

1. **Lower barrier to entry** - Users can configure LLM through UI without understanding config file structure
2. **Real-time switching** - Dynamic provider/model switching without service restart
3. **Immediate validation** - Frontend provides API key validation and model availability checks
4. **Configuration layering** - Common settings in UI, advanced settings (timeout, retry) in files
5. **Per-session flexibility** - Different sessions can use different LLM providers/models

## Architecture Analysis

### Current Configuration Flow

```
Environment Variables (.env)
    ↓
LLMSettings (backend/config/llm.py)
    ↓
LLMFactory (backend/infrastructure/llm/base/factory.py)
    ↓
LLMClientBase (provider-specific implementation)
    ↓
Agent/AgentService
```

**Current Limitation**: LLM configuration is global and requires server restart to change.

### Proposed Configuration Flow

```
Frontend UI Configuration
    ↓
Session Metadata (per-session storage)
    ↓
Runtime LLM Client Creation (factory.create_client_with_config)
    ↓
Agent uses session-specific LLM client

Config File (.env) → Fallback + API keys + Advanced options
```

### Configuration Priority

```
Frontend UI Config > Config File > System Defaults
```

## Key Technical Decisions

### 1. Storage Strategy

**Session Metadata Extension**:
```json
{
  "session_id": "uuid",
  "name": "Session Name",
  "mode": "build",
  "llm_config": {
    "provider": "anthropic",
    "model": "claude-sonnet-4-5-20250929",
    "temperature": 0.7,
    "max_tokens": 8000
  }
}
```

**Existing Pattern**: The `mode` field demonstrates this extensibility pattern is already proven.

### 2. Security Approach

**Recommended**: Store non-sensitive parameters in session, API keys from .env

```python
# Session stores:
- provider (string)
- model (string)
- temperature (float)
- max_tokens (int)

# .env stores:
- OPENAI_API_KEY
- ANTHROPIC_API_KEY
- GOOGLE_API_KEY
- etc.

# Runtime merge:
session_config + env_api_keys → LLM client
```

**Why**:
- ✅ API keys never stored in session data
- ✅ Flexible provider/model switching
- ✅ Backward compatible
- ✅ Secure by design

### 3. Validation Strategy

```python
# Before accepting config:
1. Validate provider is supported
2. Check API key exists in .env for that provider
3. Validate model is available for provider
4. Validate numeric parameters (temperature, tokens) are in valid ranges
```

## Implementation Plan

### Phase 1: Backend Foundation (Week 1-2)

#### Task 1: Extend SessionManager for per-session LLM config
**File**: `packages/backend/infrastructure/storage/session_manager.py`

```python
# Add functions:
def get_llm_config(session_id: str) -> Optional[Dict[str, Any]]
def update_llm_config(session_id: str, config: Dict[str, Any]) -> None

# Extend metadata structure:
metadata = {
    "llm_config": {
        "provider": str,
        "model": str,
        "temperature": float,
        "max_tokens": int
    }
}
```

#### Task 2: Add LLMFactory.create_client_with_config()
**File**: `packages/backend/infrastructure/llm/base/factory.py`

```python
def create_client_with_config(
    self,
    provider: str,
    model: str,
    **kwargs
) -> LLMClientBase:
    """Create LLM client with runtime configuration.

    API keys still sourced from .env, only provider/model/params override.
    """
    # 1. Get provider config from .env (for API keys)
    # 2. Override model and other parameters
    # 3. Return provider-specific client
```

#### Task 3: Modify AgentService to support optional llm_config
**File**: `packages/backend/application/services/agent_service.py`

```python
async def process_chat(
    self,
    agent_profile: AgentProfile,
    llm_config: Optional[Dict[str, Any]] = None,  # NEW
    ...
) -> StreamingResponse:
    # If llm_config provided, create custom client
    if llm_config:
        llm_client = self.llm_factory.create_client_with_config(**llm_config)
    else:
        llm_client = self.llm_client  # Use default
```

#### Task 4: Integrate in chat_request_handler
**File**: `packages/backend/presentation/handlers/chat_request_handler.py`

```python
async def process_chat_request(...):
    # 1. Load session's LLM config
    llm_config = session_manager.get_llm_config(session_id)

    # 2. Pass to AgentService
    result = await agent_service.process_chat(
        agent_profile=profile,
        llm_config=llm_config,  # NEW
        ...
    )
```

#### Task 5: Add API endpoints
**File**: `packages/backend/presentation/api/sessions.py`

```python
@router.get("/history/{session_id}/llm-config")
async def get_session_llm_config(session_id: str) -> LLMConfigResponse:
    """Get current LLM configuration for session."""

@router.post("/history/{session_id}/llm-config")
async def update_session_llm_config(
    session_id: str,
    config: LLMConfigRequest
) -> ApiResponse:
    """Update LLM configuration for session."""
    # 1. Validate config
    # 2. Check API key exists for provider
    # 3. Save to session metadata
    # 4. Send WebSocket notification
```

#### Task 6: Extend ChatMessageRequest WebSocket message
**File**: `packages/backend/presentation/websocket/messages/chat.py`

```python
class ChatMessageRequest(BaseModel):
    type: Literal["CHAT_MESSAGE"]
    message: str
    agent_profile: str
    llm_config: Optional[Dict[str, Any]] = None  # NEW: Optional override
    enable_memory: bool = True
```

#### Task 7: Add configuration validation
**File**: `packages/backend/shared/utils/config_validator.py` (new)

```python
def validate_llm_config(config: Dict[str, Any]) -> ValidationResult:
    """Validate LLM configuration.

    Checks:
    - Provider is supported
    - API key exists in environment
    - Model is valid for provider
    - Numeric parameters in valid ranges
    """
```

### Phase 2: Frontend Integration (Week 2-3)

#### Task 8: Add TypeScript type definitions
**File**: `packages/web/src/types/llm.ts` (new)

```typescript
export type LLMProvider =
  | 'openai'
  | 'google'
  | 'anthropic'
  | 'moonshot'
  | 'zhipu'
  | 'openrouter'
  | 'local_llm';

export interface LLMConfig {
  provider: LLMProvider;
  model: string;
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
}

export interface ProviderInfo {
  provider: LLMProvider;
  name: string;
  icon: string;
  availableModels: ModelInfo[];
  requiresApiKey: boolean;
  description: string;
}

export interface ModelInfo {
  id: string;
  name: string;
  contextWindow: number;
  costPer1kTokens?: number;
}
```

#### Task 9: Add LLM config management to SessionContext
**File**: `packages/web/src/contexts/session/SessionContext.tsx`

```typescript
// Add to context:
interface SessionContextValue {
  // ... existing fields
  currentLLMConfig: LLMConfig | null;
  updateLLMConfig: (config: LLMConfig) => Promise<void>;
  resetLLMConfig: () => Promise<void>;
}

// API calls:
const updateLLMConfig = async (config: LLMConfig) => {
  await api.updateSessionLLMConfig(currentSessionId, config);
  setCurrentLLMConfig(config);
  // WebSocket will broadcast to other clients
};
```

#### Task 10: Create LLM configuration UI components
**Files**: `packages/web/src/components/LLMConfig/` (new directory)

Components to create:
1. `LLMProviderSelector.tsx` - Dropdown for provider selection
2. `ModelSelector.tsx` - Model selection based on provider
3. `AdvancedOptions.tsx` - Temperature, max_tokens sliders
4. `LLMConfigPanel.tsx` - Complete configuration panel
5. `QuickSwitch.tsx` - Quick switch button in toolbar

```typescript
// Example: LLMProviderSelector.tsx
export const LLMProviderSelector: React.FC<{
  value: LLMProvider;
  onChange: (provider: LLMProvider) => void;
  availableProviders: ProviderInfo[];
}> = ({ value, onChange, availableProviders }) => {
  return (
    <Select value={value} onChange={onChange}>
      {availableProviders.map(provider => (
        <MenuItem key={provider.provider} value={provider.provider}>
          <Box display="flex" alignItems="center">
            <img src={provider.icon} />
            <Typography>{provider.name}</Typography>
          </Box>
        </MenuItem>
      ))}
    </Select>
  );
};
```

#### Task 11: Integrate LLM config to ChatContext
**File**: `packages/web/src/contexts/chat/ChatContext.tsx`

```typescript
// Use LLM config from session:
const { currentLLMConfig } = useSession();

// Include in chat messages:
const sendMessage = (content: string) => {
  websocket.send({
    type: 'CHAT_MESSAGE',
    message: content,
    agent_profile: currentProfile,
    llm_config: currentLLMConfig,  // NEW
    enable_memory: true
  });
};
```

### Phase 3: Testing (Week 3-4)

#### Task 12: End-to-end testing
**File**: `packages/backend/tests/e2e/test_llm_config.py` (new)

Test scenarios:
1. Switch provider in session → next message uses new provider
2. Multiple sessions with different configs work independently
3. Invalid config rejected with proper error
4. Missing API key detected and reported
5. Config persists across session reload
6. WebSocket broadcasts config changes to all clients

```python
async def test_session_llm_config_persistence():
    """Test LLM config persists across session lifecycle."""
    # 1. Create session
    # 2. Set LLM config
    # 3. Send message (verify correct provider used)
    # 4. Reload session
    # 5. Verify config still active
```

## File Modification Summary

### Backend (7 files)

| File | Change Type | Description |
|------|-------------|-------------|
| `infrastructure/storage/session_manager.py` | Modify | Add LLM config storage functions |
| `infrastructure/llm/base/factory.py` | Modify | Add `create_client_with_config()` |
| `application/services/agent_service.py` | Modify | Accept optional `llm_config` param |
| `presentation/handlers/chat_request_handler.py` | Modify | Load and pass session LLM config |
| `presentation/api/sessions.py` | Modify | Add GET/POST endpoints |
| `presentation/websocket/messages/chat.py` | Modify | Add `llm_config` field |
| `shared/utils/config_validator.py` | New | Config validation utilities |

### Frontend Web (5+ files)

| File | Change Type | Description |
|------|-------------|-------------|
| `types/llm.ts` | New | TypeScript type definitions |
| `contexts/session/SessionContext.tsx` | Modify | Add LLM config state/API |
| `contexts/chat/ChatContext.tsx` | Modify | Use LLM config in messages |
| `components/LLMConfig/*.tsx` | New | UI components (5 files) |
| `api/sessions.ts` | Modify | Add LLM config API calls |

### Frontend CLI (2 files)

| File | Change Type | Description |
|------|-------------|-------------|
| `ui/contexts/AppStateContext.tsx` | Modify | Add LLM config state |
| `ui/components/LLMConfigPanel.tsx` | New | CLI config UI |

## Security Checklist

- [x] API keys never stored in session metadata
- [x] API keys never transmitted over WebSocket
- [x] API keys only read from .env file
- [x] Configuration validation before acceptance
- [x] Per-session isolation (users can't access other sessions' configs)
- [x] Audit logging for config changes
- [ ] Rate limiting on config update endpoint (future)
- [ ] Cost tracking per provider (future)

## Compatibility

### Backward Compatibility
- ✅ Sessions without `llm_config` use global default
- ✅ All new fields are optional
- ✅ Existing API routes unchanged
- ✅ Config file still works as before

### Forward Compatibility
- ✅ Easy to add new providers (just update type definitions)
- ✅ Can extend to per-message config later
- ✅ Can add cost tracking without breaking changes

## Success Metrics

1. **User Experience**: Users can switch LLM provider in <5 clicks
2. **Performance**: Config change takes effect immediately (no restart)
3. **Security**: Zero API key leaks in session data or logs
4. **Reliability**: 100% of sessions preserve their LLM config across reloads
5. **Adoption**: 80%+ of users prefer UI config over file editing

## Future Enhancements (Post-MVP)

1. **Per-message config**: Override LLM for single message
2. **Config presets**: Save/load common configurations
3. **Cost tracking**: Monitor spending per provider
4. **A/B testing**: Compare responses from different models
5. **Team sharing**: Share LLM configs across team members
6. **Auto-fallback**: Automatic failover if primary provider unavailable

## References

- Explore Agent Report: Task ID `a970ce5`
- Session Mode Implementation: `packages/backend/infrastructure/storage/session_manager.py`
- WebSocket Messages: `packages/backend/presentation/websocket/messages/`
- LLM Architecture: `packages/backend/infrastructure/llm/`

## Notes

- This feature follows the same pattern as the existing `mode` field in sessions
- All provider-specific logic already exists in `infrastructure/llm/providers/`
- The LLMFactory abstraction makes this implementation straightforward
- Security design ensures API keys remain in .env (not exposed to frontend)
