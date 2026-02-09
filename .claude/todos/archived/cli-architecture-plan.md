# toyoura-nagisa CLI Architecture Plan

**Date**: 2025-11-25
**Status**: Ready for Implementation
**Goal**: Build a modern CLI frontend based on @toyoura-nagisa/core, referencing Gemini CLI v0.19.0 architecture
**Reference**: `_third_party/gemini-cli-src/` (Gemini CLI v0.19.0-nightly.20251125)

---

## Executive Summary

Based on the latest Gemini CLI architecture (v0.19.0), we will build toyoura-nagisa CLI with:
- **Ink + React 19** for terminal UI (proven by Gemini CLI)
- **Command System** with `SlashCommand` + `CommandContext` pattern
- **Stream-style Output** using Ink's Static component for history
- **Full Tool Confirmation** support with interactive UI

### Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| UI Framework | **Ink + React 19** | Gemini CLI continues using it, mature and stable |
| Output Style | **Stream Output** | Use Ink Static for history, match Claude Code style |
| Command System | **Gemini-style** | Adopt `SlashCommand` + `CommandContext` pattern |
| Tool Confirmation | **Full Interactive** | Custom RadioSelect component |
| Architecture | **Incremental** | Phase 6.1 → 6.2 → 6.3 → 6.4 |

---

## 1. Architecture Overview

### 1.1 Directory Structure

```
packages/cli/src/
├── index.tsx                    # Entry point
├── cli.tsx                      # Main entry logic (init, config)
├── ui/
│   ├── App.tsx                  # Root component
│   ├── AppContainer.tsx         # Main app container (core logic)
│   ├── types.ts                 # UI type definitions
│   ├── colors.ts                # Color constants
│   ├── semantic-colors.ts       # Semantic colors
│   ├── commands/                # Slash command system
│   │   ├── types.ts             # CommandContext, SlashCommand types
│   │   ├── sessionCommand.ts    # /session command group
│   │   ├── helpCommand.ts       # /help command
│   │   ├── clearCommand.ts      # /clear command
│   │   ├── quitCommand.ts       # /quit command
│   │   └── profileCommand.ts    # /profile command
│   ├── components/
│   │   ├── Header.tsx           # Top status bar
│   │   ├── Footer.tsx           # Bottom info bar
│   │   ├── InputPrompt.tsx      # Input component
│   │   ├── Composer.tsx         # Multiline editor
│   │   ├── LoadingIndicator.tsx # Loading spinner
│   │   ├── Help.tsx             # Help display
│   │   ├── DialogManager.tsx    # Dialog manager
│   │   ├── messages/
│   │   │   ├── HistoryItemDisplay.tsx  # History item router
│   │   │   ├── UserMessage.tsx
│   │   │   ├── AssistantMessage.tsx
│   │   │   ├── ToolMessage.tsx
│   │   │   ├── ToolConfirmationMessage.tsx
│   │   │   └── ThinkingMessage.tsx
│   │   └── shared/
│   │       ├── RadioButtonSelect.tsx
│   │       ├── TextBuffer.tsx
│   │       └── MaxSizedBox.tsx
│   ├── hooks/
│   │   ├── useWebSocket.ts
│   │   ├── useStreamHandler.ts
│   │   ├── useHistoryManager.ts
│   │   ├── useInputHistory.ts
│   │   ├── useKeypress.ts
│   │   ├── useTerminalSize.ts
│   │   └── useSlashCommandProcessor.ts
│   └── contexts/
│       ├── SessionContext.tsx
│       └── StreamingContext.tsx
├── services/
│   ├── CommandService.ts
│   └── BuiltinCommandLoader.ts
└── config/
    └── settings.ts
```

### 1.2 Dependency Graph

```
@toyoura-nagisa/cli
    |
    +-- @toyoura-nagisa/core (business logic)
    |     |-- ConnectionManager
    |     |-- SessionManager
    |     |-- ChatService, SessionService
    |     |-- Types, Utils
    |
    +-- @jrichman/ink@6.4.6 (fork version, ref Gemini)
    +-- react@^19.2.0
    +-- ws (Node.js WebSocket)
    +-- zod (config validation)
```

---

## 2. Command System Architecture

### 2.1 Core Types (Reference: Gemini CLI)

```typescript
// ui/commands/types.ts
export interface CommandContext {
  invocation?: {
    raw: string;      // Original input
    name: string;     // Command name
    args: string;     // Arguments
  };
  services: {
    sessionManager: SessionManager;
    connectionManager: ConnectionManager;
  };
  ui: {
    addItem: (item: HistoryItem) => void;
    clear: () => void;
    setPendingItem: (item: HistoryItem | null) => void;
  };
  session: {
    currentSessionId: string | null;
    stats: SessionStats;
  };
}

export type SlashCommandActionReturn =
  | { type: 'message'; messageType: 'info' | 'error'; content: string }
  | { type: 'quit'; messages: HistoryItem[] }
  | { type: 'dialog'; dialog: 'help' | 'profile' | 'session' }
  | { type: 'load_history'; history: Message[] };

export interface SlashCommand {
  name: string;
  altNames?: string[];
  description: string;
  hidden?: boolean;
  action?: (context: CommandContext, args: string) =>
    void | SlashCommandActionReturn | Promise<void | SlashCommandActionReturn>;
  completion?: (context: CommandContext, partialArg: string) =>
    Promise<string[]> | string[];
  subCommands?: SlashCommand[];
}
```

### 2.2 Command Examples

**Session Command Group** (ref: `chatCommand.ts`):
```typescript
// ui/commands/sessionCommand.ts
const listCommand: SlashCommand = {
  name: 'list',
  description: 'List all sessions',
  kind: CommandKind.BUILT_IN,
  action: async (context): Promise<void> => {
    const sessions = await context.services.sessionManager.loadSessions();
    // Display sessions...
  },
};

const createCommand: SlashCommand = {
  name: 'create',
  description: 'Create new session. Usage: /session create [name]',
  kind: CommandKind.BUILT_IN,
  action: async (context, args): Promise<SlashCommandActionReturn | void> => {
    const name = args.trim();
    const sessionId = await context.services.sessionManager.createSession(name || undefined);
    return {
      type: 'message',
      messageType: 'info',
      content: `Created session: ${sessionId}`,
    };
  },
};

export const sessionCommand: SlashCommand = {
  name: 'session',
  description: 'Manage sessions',
  kind: CommandKind.BUILT_IN,
  subCommands: [listCommand, createCommand, switchCommand, deleteCommand],
};
```

---

## 3. Key Components Reference

### 3.1 Gemini CLI Reference Files

| File | Learning Points |
|------|-----------------|
| `ui/App.tsx` | Root component, Provider organization |
| `ui/AppContainer.tsx` | **Core**: Main business logic, Static usage, state management |
| `ui/commands/types.ts` | **Command system types**: CommandContext, SlashCommand |
| `ui/commands/chatCommand.ts` | Command implementation (with subcommands) |
| `ui/components/InputPrompt.tsx` | Input handling, history navigation, autocomplete |
| `ui/components/Composer.tsx` | Multiline text editor |
| `ui/components/messages/ToolConfirmationMessage.tsx` | Tool confirmation UI |
| `ui/components/shared/RadioButtonSelect.tsx` | Custom radio select component |
| `ui/components/shared/TextBuffer.tsx` | Text buffer implementation |
| `ui/hooks/useHistoryManager.ts` | History management hook |
| `ui/hooks/useKeypress.ts` | Keyboard input handling |
| `services/CommandService.ts` | Command service architecture |
| `services/BuiltinCommandLoader.ts` | Built-in command loading |

### 3.2 @toyoura-nagisa/core Reference Files

| File | Purpose |
|------|---------|
| `packages/core/src/connection/ConnectionManager.ts` | WebSocket event API |
| `packages/core/src/session/SessionManager.ts` | Session management API |
| `packages/core/src/connection/adapters/NodeWebSocketAdapter.ts` | Node.js WebSocket adapter |
| `packages/core/src/session/adapters/FileStorageAdapter.ts` | File storage adapter |

---

## 4. Implementation Phases

### Phase 6.1 - Core Chat (Current Priority)

**Goal**: Refactor existing code, use @toyoura-nagisa/core, implement basic streaming chat

**Tasks**:

1. **Update package.json dependencies**
   ```json
   {
     "dependencies": {
       "@toyoura-nagisa/core": "*",
       "ink": "npm:@jrichman/ink@6.4.6",
       "react": "^19.2.0",
       "ws": "^8.14.0",
       "string-width": "^8.1.0",
       "strip-ansi": "^7.1.0",
       "wrap-ansi": "9.0.2",
       "zod": "^3.23.8"
     }
   }
   ```

2. **Restructure directories**
   - Move `components/` → `ui/components/`
   - Create `ui/commands/`
   - Create `ui/hooks/`

3. **Create ui/App.tsx** (root with Providers)
4. **Create ui/AppContainer.tsx** (main logic)
5. **Implement ui/hooks/useWebSocket.ts** (ConnectionManager wrapper)
6. **Implement ui/hooks/useHistoryManager.ts** (history management)
7. **Create ui/components/messages/HistoryItemDisplay.tsx** (message routing)
8. **Enhance ui/components/InputPrompt.tsx** (multiline, history)

**Success Criteria**:
- [ ] Connect to backend WebSocket
- [ ] Send messages and receive streaming responses
- [ ] Display text, thinking, tool_use, tool_result content blocks
- [ ] Show connection status correctly
- [ ] Handle Ctrl+C properly

### Phase 6.2 - Session Management

**Goal**: Complete Session CRUD functionality

**Commands**:
```
/new [name]     - Create new Session
/list           - List all Sessions
/switch <id>    - Switch Session
/delete <id>    - Delete Session
/rename <name>  - Rename current Session
/help           - Show help
/quit           - Exit
```

**Success Criteria**:
- [ ] All slash commands work correctly
- [ ] History loads correctly on session switch
- [ ] Current session persists to file
- [ ] Restore last session on startup

### Phase 6.3 - Tool Confirmation

**Goal**: Complete tool confirmation UI with y/n/always options

**Shortcuts**:
- `y` - Allow once
- `n` - Reject
- `a` - Always allow
- `Esc` - Cancel/Reject

**Success Criteria**:
- [ ] Tool confirmation dialog displays correctly
- [ ] Shortcuts y/n/a/Esc work
- [ ] Confirmation/rejection response sent correctly
- [ ] Streaming pauses during confirmation

### Phase 6.4 - Advanced Features (Future)

**Planned Features**:
1. **Agent Profile Selection**
   - `--profile <name>` CLI argument
   - `/profile` command to switch
   - Display current profile info

2. **File Mention (@file)**
   - Use core `FileMentionParser`
   - Tab completion for file paths
   - Support relative/absolute paths

3. **Token Usage Statistics**
   - Footer shows current session token usage
   - `/usage` command for detailed stats

4. **Theme Support**
   - Reference Gemini CLI theme system
   - `/theme` command to switch

---

## 5. Key Code Patterns

### 5.1 WebSocket Hook

```typescript
// hooks/useWebSocket.ts
import { ConnectionManager, NodeWebSocketAdapter } from '@toyoura-nagisa/core'

export function useWebSocket(host: string, port: number) {
  const [connectionManager] = useState(() => {
    const adapter = new NodeWebSocketAdapter()
    return new ConnectionManager(adapter)
  })
  const [status, setStatus] = useState<ConnectionState>('DISCONNECTED')

  useEffect(() => {
    connectionManager.on('stateChanged', setStatus)
    connectionManager.on('message_create', handleMessageCreate)
    connectionManager.on('streaming_update', handleStreamingUpdate)
    connectionManager.on('tool_confirmation_request', handleToolConfirmation)

    return () => connectionManager.removeAllListeners()
  }, [connectionManager])

  const connect = async (sessionId: string) => {
    await connectionManager.connectToSession(sessionId)
  }

  return { connectionManager, status, connect }
}
```

### 5.2 Stream Handler

```typescript
// hooks/useStreamHandler.ts
export function useStreamHandler(connectionManager: ConnectionManager) {
  const [messages, setMessages] = useState<Message[]>([])
  const [currentStreamingId, setCurrentStreamingId] = useState<string | null>(null)

  useEffect(() => {
    connectionManager.on('message_create', (data) => {
      const newMessage = createMessage(data)
      setMessages(prev => [...prev, newMessage])
      if (data.role === 'assistant') {
        setCurrentStreamingId(data.message_id)
      }
    })

    connectionManager.on('streaming_update', (data) => {
      setMessages(prev => prev.map(msg =>
        msg.id === data.message_id
          ? updateMessageContent(msg, data.content, data.streaming)
          : msg
      ))
      if (!data.streaming) {
        setCurrentStreamingId(null)
      }
    })
  }, [connectionManager])

  return { messages, currentStreamingId }
}
```

### 5.3 Tool Confirmation Component

```typescript
// components/messages/ToolConfirmation.tsx
interface ToolConfirmationProps {
  data: ToolConfirmationData
  onConfirm: (approved: boolean, alwaysAllow?: boolean) => void
  isFocused: boolean
}

export const ToolConfirmation: React.FC<ToolConfirmationProps> = ({
  data, onConfirm, isFocused
}) => {
  const options = [
    { label: 'Yes, allow once', value: 'once' },
    { label: 'Yes, always allow', value: 'always' },
    { label: 'No, reject (esc)', value: 'reject' }
  ]

  useInput((input, key) => {
    if (!isFocused) return
    if (input === 'y') onConfirm(true, false)
    if (input === 'a') onConfirm(true, true)
    if (input === 'n' || key.escape) onConfirm(false)
  })

  return (
    <Box flexDirection="column" borderStyle="round" borderColor="yellow">
      <Text bold color="yellow">Tool Confirmation Required</Text>
      <Box marginY={1}>
        <Text>Tool: </Text>
        <Text color="cyan">{data.tool_name}</Text>
      </Box>
      {data.command && (
        <Box marginBottom={1}>
          <Text dimColor>{data.command}</Text>
        </Box>
      )}
      <RadioSelect items={options} onSelect={handleSelect} />
    </Box>
  )
}
```

---

## 6. Files to Modify

| File | Changes |
|------|---------|
| `packages/cli/package.json` | Add `ws` dependency, upgrade `ink` |
| `packages/cli/src/index.tsx` | Simplify entry, delegate to App |
| `packages/cli/src/components/ChatApp.tsx` | Rename to App.tsx, refactor architecture |
| `packages/cli/src/components/MessageList.tsx` | Split into message sub-components |
| `packages/cli/src/components/InputBox.tsx` | Enhance to InputPrompt |
| `packages/cli/src/components/StatusBar.tsx` | Enhance status display |

## 7. Files to Create

| File | Purpose |
|------|---------|
| `src/ui/hooks/useWebSocket.ts` | WebSocket connection management |
| `src/ui/hooks/useStreamHandler.ts` | Streaming message handling |
| `src/ui/hooks/useCommands.ts` | Slash command processing |
| `src/ui/hooks/useToolConfirmation.ts` | Tool confirmation logic |
| `src/ui/hooks/useInputHistory.ts` | Input history management |
| `src/ui/components/messages/AssistantMessage.tsx` | Assistant message component |
| `src/ui/components/messages/ToolMessage.tsx` | Tool message component |
| `src/ui/components/messages/ToolConfirmation.tsx` | Tool confirmation component |
| `src/ui/components/messages/ThinkingMessage.tsx` | Thinking block component |
| `src/ui/components/shared/RadioSelect.tsx` | Radio select component |
| `src/ui/components/LoadingIndicator.tsx` | Loading indicator |
| `src/ui/contexts/SessionContext.tsx` | Session context |
| `src/ui/commands/types.ts` | Command type definitions |

---

## 8. Risk & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Ink version compatibility | Medium | Medium | Keep 4.x, reference Gemini 6.x upgrade approach |
| WebSocket event loss | Low | High | Add reconnection logic, use ConnectionManager built-in reconnect |
| Tool confirmation state chaos | Medium | Medium | Use pending state machine, ensure single confirmation flow |
| Input history overflow | Low | Low | Limit history count, periodic cleanup |

---

## 9. Success Metrics

### Phase 6.1 Completion Criteria
- [ ] CLI can connect to backend and send messages
- [ ] Streaming responses display correctly
- [ ] All content block types render correctly
- [ ] No memory leaks, no crashes

### Phase 6.2 Completion Criteria
- [ ] All Session commands work correctly
- [ ] Session state persists correctly
- [ ] History loading works completely

### Phase 6.3 Completion Criteria
- [ ] Tool confirmation interaction complete
- [ ] Shortcuts respond correctly
- [ ] Backend confirmation protocol compatible

### Overall Completion Criteria
- [ ] CLI can complete same basic chat tasks as web frontend
- [ ] Code reuse rate 80%+ (via @toyoura-nagisa/core)
- [ ] Zero functional regression

---

## 10. Next Actions

### Immediate Start (Phase 6.1)

1. **Update Dependencies**
   - Upgrade ink to `@jrichman/ink@6.4.6`
   - Upgrade react to `^19.2.0`
   - Add necessary dependencies (string-width, wrap-ansi, zod)

2. **Restructure Directories**
   - Move existing `components/` to `ui/components/`
   - Create `ui/commands/` directory
   - Create `ui/hooks/` directory

3. **Implement Core Components**
   - Refactor to `App.tsx` + `AppContainer.tsx` pattern
   - Implement `useWebSocket` hook wrapping ConnectionManager
   - Implement `useHistoryManager` hook

4. **Test & Verify**
   - Ensure connection to backend
   - Ensure send/receive messages work
   - Ensure streaming responses display correctly

### Implementation Order

```
1. ui/App.tsx (Providers wrapper)
2. ui/AppContainer.tsx (core logic)
3. ui/hooks/useWebSocket.ts (WebSocket management)
4. ui/hooks/useHistoryManager.ts (history management)
5. ui/components/messages/HistoryItemDisplay.tsx (message routing)
6. ui/components/InputPrompt.tsx (input component)
```

---

**Related Documents**:
- `web-cli-architecture-refactoring-plan.md` - Overall refactoring plan (Phase 1-5 completed)
- `_third_party/gemini-cli-src/` - Gemini CLI reference implementation
