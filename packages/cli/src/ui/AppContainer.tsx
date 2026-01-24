/**
 * App Container Component
 * Reference: Gemini CLI ui/AppContainer.tsx
 *
 * This is the main container that:
 * - Initializes core services (ConnectionManager, SessionManager)
 * - Composes hooks for business logic
 * - Provides contexts to child components
 *
 * Following gemini-cli's hook-driven architecture pattern:
 * - AppContainer orchestrates hooks at the top level
 * - Each hook manages a specific concern
 * - Context values are assembled from hook returns
 */

import React, { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { useApp } from 'ink';
import {
  ConnectionManager,
  NodeWebSocketAdapter,
  SessionManager,
  SessionEvent,
  FileStorageAdapter,
  SessionService,
  sessionService,
  apiClient,
  llmConfigService,
  type TokenUsage,
  type ChatSession,
  type SessionLlmConfigUpdateMessage,
} from '@toyoura-nagisa/core';
import { App } from './App.js';
import {
  AppStateContext,
  AppActionsContext,
  type AppState,
  type AppActions,
} from './contexts/AppStateContext.js';
import { ConnectionProvider } from './contexts/ConnectionContext.js';
import { useHistoryManager } from './hooks/useHistoryManager.js';
import { useChatStream } from './hooks/useChatStream.js';
import { useConnectionState } from './hooks/useConnectionState.js';
import { useSessionManagement } from './hooks/useSessionManagement.js';
import { useTodoStatus } from './hooks/useTodoStatus.js';
import { useBackgroundProcesses } from './hooks/useBackgroundProcesses.js';
import { usePfcTasks } from './hooks/usePfcTasks.js';
import { useKeypress, type Key } from './hooks/useKeypress.js';
import { MessageType, type SessionMode } from './types.js';
import type { Config } from '../config/settings.js';

interface AppContainerProps {
  config: Config;
  initialSessionId?: string;
}

export const AppContainer: React.FC<AppContainerProps> = ({
  config,
  initialSessionId,
}) => {
  const { exit } = useApp();

  // ========== Service Initialization ==========
  // Initialize core services (refs to persist across renders)
  const connectionManagerRef = useRef<ConnectionManager | null>(null);
  const sessionManagerRef = useRef<SessionManager | null>(null);

  // Build URLs
  const wsBaseUrl = useMemo(() => {
    const protocol = config.server.secure ? 'wss' : 'ws';
    return `${protocol}://${config.server.host}:${config.server.port}`;
  }, [config.server]);

  const apiBaseUrl = useMemo(() => {
    const protocol = config.server.secure ? 'https' : 'http';
    return `${protocol}://${config.server.host}:${config.server.port}`;
  }, [config.server]);

  // Configure API client
  if (apiClient.getBaseURL() !== apiBaseUrl) {
    apiClient.setBaseURL(apiBaseUrl);
  }

  // Lazy initialization of services
  if (!connectionManagerRef.current) {
    const wsAdapter = new NodeWebSocketAdapter();
    connectionManagerRef.current = new ConnectionManager(wsAdapter, wsBaseUrl);
  }

  if (!sessionManagerRef.current) {
    const storageAdapter = new FileStorageAdapter('.toyoura-nagisa');
    const sessionService = new SessionService();
    sessionManagerRef.current = new SessionManager(sessionService, storageAdapter);
  }

  const connectionManager = connectionManagerRef.current;
  const sessionManager = sessionManagerRef.current;

  // ========== Local State ==========
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(initialSessionId || null);
  const [sessionMode, setSessionMode] = useState<SessionMode>('build');
  const [llmConfig, setLlmConfig] = useState<ChatSession['llm_config'] | null>(null);
  const [contextWindow, setContextWindow] = useState<number | null>(null);
  const [isQuitting, setIsQuitting] = useState(false);
  const [memoryEnabled, setMemoryEnabled] = useState(false);
  const [sessionTokenUsage, setSessionTokenUsage] = useState<TokenUsage | null>(null);

  // Ctrl+C confirmation state
  const [ctrlCPending, setCtrlCPending] = useState(false);
  const ctrlCTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Full context mode (Ctrl+O toggle)
  const [isFullContextMode, setIsFullContextMode] = useState(false);

  // User shell execution state (for Ctrl+B backgrounding)
  const [isShellExecuting, setShellExecuting] = useState(false);

  // User PFC console execution state (for Ctrl+B backgrounding)
  const [isPfcExecuting, setPfcExecuting] = useState(false);

  // System Notification
  const [notification, setNotification] = useState<AppState['notification']>(null);
  const notificationTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // ========== Hooks ==========

  // Connection state management
  const { connectionStatus } = useConnectionState({
    connectionManager,
  });

  // History management
  const historyManager = useHistoryManager();

  // Chat stream (message handling, streaming state)
  const {
    streamingState: streamingStateEnum,
    isStreaming,
    thinkingContent,
    pendingConfirmation,
    error,
    pendingHistoryItems,
    tokenUsage,
    submitQuery,
    cancelRequest,
    confirmTool,
    clearError,
  } = useChatStream({
    connectionManager,
    historyManager,
    currentSessionId,
    memoryEnabled,
  });

  // Session management (switch, create, history loading)
  const {
    switchSession,
    createSession,
    loadHistory,
  } = useSessionManagement({
    connectionManager,
    sessionManager,
    historyManager,
    setCurrentSessionId,
    setSessionMode,
    setLlmConfig,
  });

  // Todo status (current in-progress task)
  const { currentTodo } = useTodoStatus({
    connectionManager,
  });

  // Background processes (running bash tasks)
  const { activeTasks: backgroundTasks, activeCount: activeBackgroundTaskCount } = useBackgroundProcesses({
    connectionManager,
  });

  // PFC task (single running simulation)
  const { currentTask: pfcTask } = usePfcTasks({
    connectionManager,
  });

  // ========== SessionManager Event Listeners ==========
  // Listen for token usage updates from SessionManager (triggered on session switch)
  useEffect(() => {
    const handleTokenUsageUpdate = ({ usage }: { usage: TokenUsage }) => {
      setSessionTokenUsage(usage);
    };

    const handleSessionCreated = () => {
      // New session has no token usage
      setSessionTokenUsage(null);
    };

    sessionManager.on(SessionEvent.TOKEN_USAGE_UPDATED, handleTokenUsageUpdate);
    sessionManager.on(SessionEvent.SESSION_CREATED, handleSessionCreated);

    return () => {
      sessionManager.off(SessionEvent.TOKEN_USAGE_UPDATED, handleTokenUsageUpdate);
      sessionManager.off(SessionEvent.SESSION_CREATED, handleSessionCreated);
    };
  }, [sessionManager]);

  // ========== Session Initialization ==========
  // Use ref to access loadHistory without adding it to deps
  const loadHistoryRef = useRef(loadHistory);
  loadHistoryRef.current = loadHistory;

  useEffect(() => {
    const initSession = async () => {
      try {
        // Initialize session manager with retry (backend might not be ready yet)
        let initRetryCount = 0;
        const maxInitRetries = 10;
        const initRetryDelay = 2000;

        while (initRetryCount < maxInitRetries) {
          try {
            await sessionManager.initialize();
            break;
          } catch (err) {
            initRetryCount++;
            if (initRetryCount >= maxInitRetries) {
              throw err;
            }
            await new Promise(resolve => setTimeout(resolve, initRetryDelay));
          }
        }

        // Priority: CLI arg > stored session > create new
        let sessionId = currentSessionId || sessionManager.getCurrentSessionId();
        let isExistingSession = false;

        // Validate stored session exists in backend
        if (sessionId) {
          const sessions = sessionManager.getSessions();
          const sessionExists = sessions.some(s => s.id === sessionId);
          if (sessionExists) {
            isExistingSession = true;
          } else {
            // Stored session no longer exists, clear it
            sessionId = null;
          }
        }

        // Create new session if none exists
        if (!sessionId) {
          sessionId = await sessionManager.createSession();
          setSessionMode('build');
          
          const sessions = sessionManager.getSessions();
          const session = sessions.find(s => s.id === sessionId);
          if (session) {
            setLlmConfig(session.llm_config || null);
          }
        }

        setCurrentSessionId(sessionId);

        // Load chat history and token usage for existing sessions
        if (isExistingSession) {
          await loadHistoryRef.current(sessionId);
          // Load token usage (triggers TOKEN_USAGE_UPDATED event)
          await sessionManager.loadTokenUsage(sessionId);
        }

        // Connect WebSocket with retry handling
        try {
          await connectionManager.connectToSession(sessionId);
        } catch (err) {
          console.error('[AppContainer] WebSocket connection error:', err);
        }
      } catch (err) {
        console.error('[AppContainer] Session initialization error:', err);
      }
    };

    initSession();

    return () => {
      connectionManager.disconnect();
    };
  }, []);  // Only run once on mount

  // ========== Actions ==========

  // Send message (backend handles queuing if streaming)
  const sendMessage = useCallback((text: string, mentionedFiles?: string[]) => {
    if (!text.trim()) return;
    submitQuery(text, mentionedFiles);
  }, [submitQuery]);

  const updateSessionMode = useCallback(async (mode: SessionMode) => {
    if (!currentSessionId) return;

    try {
      const response = await sessionService.updateSessionMode(currentSessionId, mode);
      setSessionMode(response.mode || mode);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to update session mode';
      historyManager.addItem({
        type: MessageType.ERROR,
        message,
      });
    }
  }, [currentSessionId, historyManager]);

  const cycleSessionMode = useCallback((_direction: 1 | -1) => {
    const nextMode: SessionMode = sessionMode === 'build' ? 'plan' : 'build';
    updateSessionMode(nextMode);
    return nextMode;
  }, [sessionMode, updateSessionMode]);

  const quit = useCallback(() => {
    setIsQuitting(true);
    connectionManager.disconnect();
    // Farewell message is printed in index.tsx after exiting alternate buffer
    setTimeout(() => {
      exit();
    }, 100);
  }, [connectionManager, exit]);

  const clearScreen = useCallback(() => {
    historyManager.clearItems();
  }, [historyManager]);

  const toggleFullContextMode = useCallback(() => {
    setIsFullContextMode(prev => !prev);
  }, []);

  // ========== Global Keypress Handling ==========

  // Clear Ctrl+C pending state
  const clearCtrlCPending = useCallback(() => {
    if (ctrlCTimeoutRef.current) {
      clearTimeout(ctrlCTimeoutRef.current);
      ctrlCTimeoutRef.current = null;
    }
    setCtrlCPending(false);
  }, []);

  // Handle global keys: Ctrl+C to quit (with confirmation), ESC to interrupt
  const handleGlobalKeypress = useCallback((key: Key) => {
    // Ctrl+C: quit application (requires double-tap within 2 seconds)
    if (key.ctrl && key.name === 'c') {
      if (ctrlCPending) {
        // Second Ctrl+C within timeout - quit
        clearCtrlCPending();
        quit();
      } else {
        // First Ctrl+C - show warning and start timeout
        setCtrlCPending(true);
        historyManager.addItem({
          type: MessageType.INFO,
          message: 'Press Ctrl+C again to quit',
        });

        // Clear pending state after 2 seconds
        ctrlCTimeoutRef.current = setTimeout(() => {
          setCtrlCPending(false);
          ctrlCTimeoutRef.current = null;
        }, 2000);
      }
      return;
    }

    // Any other key press cancels the Ctrl+C pending state
    if (ctrlCPending) {
      clearCtrlCPending();
    }

    // ESC: interrupt streaming or reject pending confirmation
    if (key.name === 'escape') {
      if (isStreaming) {
        // Interrupt ongoing LLM response
        cancelRequest();
      }
      // Note: pendingConfirmation ESC is handled by ToolConfirmationPrompt component
    }

    // Ctrl+B: move foreground bash/pfc to background
    // Supports agent bash (during isStreaming), user shell (! prefix), and user PFC console (> prefix)
    if (key.ctrl && key.name === 'b') {
      if ((isStreaming || isShellExecuting || isPfcExecuting) && currentSessionId) {
        // Send move-to-background signal to backend
        connectionManager.send({
          type: 'MOVE_TO_BACKGROUND',
          session_id: currentSessionId,
        });
      }
    }

    // Ctrl+O: toggle full context mode (show full thinking/tool results)
    // Only handle here when NOT in full context mode (FullContextView handles its own Ctrl+O)
    if (key.ctrl && key.name === 'o' && !isFullContextMode) {
      toggleFullContextMode();
    }
  }, [quit, isStreaming, isShellExecuting, isPfcExecuting, cancelRequest, ctrlCPending, clearCtrlCPending, historyManager, toggleFullContextMode, isFullContextMode, currentSessionId, connectionManager]);

  useKeypress(handleGlobalKeypress, { isActive: true });

  useEffect(() => {
    const handleSessionModeUpdate = (message: { payload?: { session_id?: string; mode?: SessionMode } }) => {
      const payload = message?.payload;
      if (!payload?.session_id || !payload?.mode) return;
      if (payload.session_id !== currentSessionId) return;
      setSessionMode(payload.mode);
    };

    connectionManager.on('session_mode_update', handleSessionModeUpdate);

    const handleLlmConfigUpdate = (message: SessionLlmConfigUpdateMessage) => {
      const payload = message?.payload;
      if (!payload?.session_id || !payload?.llm_config) return;
      if (payload.session_id !== currentSessionId) return;
      setLlmConfig(payload.llm_config);
    };

    connectionManager.on('session_llm_config_update', handleLlmConfigUpdate);

    return () => {
      connectionManager.off('session_mode_update', handleSessionModeUpdate);
      connectionManager.off('session_llm_config_update', handleLlmConfigUpdate);
    };
  }, [connectionManager, currentSessionId]);

  // Sync context window when model changes
  useEffect(() => {
    if (!llmConfig?.provider || !llmConfig?.model) {
      setContextWindow(null);
      return;
    }

    const fetchModelDetails = async () => {
      try {
        const details = await llmConfigService.getModelDetails(llmConfig.provider, llmConfig.model);
        if (details && details.context_window) {
          setContextWindow(details.context_window);
        } else {
          setContextWindow(null);
        }
      } catch (err) {
        console.error('[AppContainer] Failed to fetch model details:', err);
        setContextWindow(null);
      }
    };

    fetchModelDetails();
  }, [llmConfig]);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (ctrlCTimeoutRef.current) {
        clearTimeout(ctrlCTimeoutRef.current);
      }
    };
  }, []);

  // Notification actions
  const showNotification = useCallback((message: string, type: 'info' | 'success' | 'error' = 'info', duration = 3000) => {
    // Clear existing timeout
    if (notificationTimeoutRef.current) {
      clearTimeout(notificationTimeoutRef.current);
    }

    setNotification({
      id: Date.now().toString(),
      message,
      type,
    });

    notificationTimeoutRef.current = setTimeout(() => {
      setNotification(null);
      notificationTimeoutRef.current = null;
    }, duration);
  }, []);

  const clearNotification = useCallback(() => {
    if (notificationTimeoutRef.current) {
      clearTimeout(notificationTimeoutRef.current);
      notificationTimeoutRef.current = null;
    }
    setNotification(null);
  }, []);

  // ========== Context Values ==========

  const appState: AppState = useMemo(() => ({
    connectionStatus,
    error,
    currentSessionId,
    sessionMode,
    llmConfig,
    contextWindow,
    memoryEnabled,
    history: historyManager.history,
    pendingHistoryItems,
    streamingState: {
      state: streamingStateEnum,
      thinkingContent,
    },
    isStreaming,
    isShellExecuting,
    isPfcExecuting,
    pendingConfirmation,
    isQuitting,
    isInputActive: connectionStatus === 'connected' && !isQuitting,
    // Token usage: streaming update takes priority, fallback to session usage
    tokenUsage: tokenUsage || sessionTokenUsage,
    currentTodo,
    isFullContextMode,
    backgroundTasks,
    activeBackgroundTaskCount,
    pfcTask,
    notification,
  }), [
    connectionStatus,
    error,
    currentSessionId,
    sessionMode,
    llmConfig,
    contextWindow,
    memoryEnabled,
    historyManager.history,
    pendingHistoryItems,
    streamingStateEnum,
    thinkingContent,
    isStreaming,
    isShellExecuting,
    isPfcExecuting,
    pendingConfirmation,
    isQuitting,
    tokenUsage,
    sessionTokenUsage,
    currentTodo,
    isFullContextMode,
    backgroundTasks,
    activeBackgroundTaskCount,
    pfcTask,
    notification,
  ]);

  const appActions: AppActions = useMemo(() => ({
    addHistoryItem: historyManager.addItem,
    updateHistoryItem: historyManager.updateItem,
    clearHistory: historyManager.clearItems,
    switchSession,
    createSession,
    setSessionMode: updateSessionMode,
    cycleSessionMode,
    setMemoryEnabled,
    sendMessage,
    cancelRequest,
    confirmTool,
    quit,
    clearScreen,
    toggleFullContextMode,
    setShellExecuting,
    setPfcExecuting,
    clearError,
    showNotification,
    clearNotification,
  }), [
    historyManager.addItem,
    historyManager.updateItem,
    historyManager.clearItems,
    switchSession,
    createSession,
    updateSessionMode,
    cycleSessionMode,
    setMemoryEnabled,
    sendMessage,
    cancelRequest,
    confirmTool,
    quit,
    clearScreen,
    toggleFullContextMode,
    setShellExecuting,
    setPfcExecuting,
    clearError,
    showNotification,
    clearNotification,
  ]);

  return (
    <ConnectionProvider value={connectionManager}>
      <AppStateContext.Provider value={appState}>
        <AppActionsContext.Provider value={appActions}>
          <App />
        </AppActionsContext.Provider>
      </AppStateContext.Provider>
    </ConnectionProvider>
  );
};
