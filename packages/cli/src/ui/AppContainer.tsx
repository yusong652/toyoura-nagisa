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
  apiClient,
  type TokenUsage,
} from '@toyoura-nagisa/core';
import { App } from './App.js';
import {
  AppStateContext,
  AppActionsContext,
  type AppState,
  type AppActions,
} from './contexts/AppStateContext.js';
import { useHistoryManager } from './hooks/useHistoryManager.js';
import { useChatStream } from './hooks/useChatStream.js';
import { useConnectionState } from './hooks/useConnectionState.js';
import { useSessionManagement } from './hooks/useSessionManagement.js';
import { useProfileManager } from './hooks/useProfileManager.js';
import { useTodoStatus } from './hooks/useTodoStatus.js';
import { useKeypress, type Key } from './hooks/useKeypress.js';
import { MessageType } from './types.js';
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
  const [isQuitting, setIsQuitting] = useState(false);
  const [memoryEnabled, setMemoryEnabled] = useState(false);
  const [sessionTokenUsage, setSessionTokenUsage] = useState<TokenUsage | null>(null);

  // Ctrl+C confirmation state
  const [ctrlCPending, setCtrlCPending] = useState(false);
  const ctrlCTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Full context mode (Ctrl+O toggle)
  const [isFullContextMode, setIsFullContextMode] = useState(false);

  // ========== Hooks ==========

  // Connection state management
  const { connectionStatus } = useConnectionState({
    connectionManager,
  });

  // History management
  const historyManager = useHistoryManager();

  // Profile management
  const {
    currentProfile,
    availableProfiles,
    isProfileLoading,
    setProfile,
    refreshProfiles,
  } = useProfileManager({ defaultProfile: 'pfc' });

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
    currentProfile,
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
  });

  // Todo status (current in-progress task)
  const { currentTodo } = useTodoStatus({
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
        // Initialize session manager (loads stored session ID and session list from backend)
        await sessionManager.initialize();

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
          // Initial connection failed, WebSocketManager will auto-reconnect
          // Listen for successful reconnection
          console.log('[AppContainer] Initial connection failed, waiting for reconnection...');

          await new Promise<void>((resolve, reject) => {
            const onConnected = () => {
              cleanup();
              resolve();
            };

            const onMaxRetries = () => {
              cleanup();
              reject(new Error('Max reconnection attempts reached'));
            };

            const cleanup = () => {
              connectionManager.off('connected', onConnected);
              connectionManager.off('maxReconnectAttemptsReached', onMaxRetries);
            };

            connectionManager.once('connected', onConnected);
            connectionManager.once('maxReconnectAttemptsReached', onMaxRetries);
          });

          console.log('[AppContainer] Reconnected successfully');
        }

        // Fetch available profiles
        refreshProfiles();
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

    // Ctrl+O: toggle full context mode (show full thinking/tool results)
    // Only handle here when NOT in full context mode (FullContextView handles its own Ctrl+O)
    if (key.ctrl && key.name === 'o' && !isFullContextMode) {
      toggleFullContextMode();
    }
  }, [quit, isStreaming, cancelRequest, ctrlCPending, clearCtrlCPending, historyManager, toggleFullContextMode, isFullContextMode]);

  useKeypress(handleGlobalKeypress, { isActive: true });

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (ctrlCTimeoutRef.current) {
        clearTimeout(ctrlCTimeoutRef.current);
      }
    };
  }, []);

  // ========== Context Values ==========

  const appState: AppState = useMemo(() => ({
    connectionStatus,
    error,
    currentSessionId,
    currentProfile,
    availableProfiles,
    isProfileLoading,
    memoryEnabled,
    history: historyManager.history,
    pendingHistoryItems,
    streamingState: {
      state: streamingStateEnum,
      thinkingContent,
    },
    isStreaming,
    pendingConfirmation,
    isQuitting,
    isInputActive: connectionStatus === 'connected' && !isQuitting,
    // Token usage: streaming update takes priority, fallback to session usage
    tokenUsage: tokenUsage || sessionTokenUsage,
    currentTodo,
    isFullContextMode,
  }), [
    connectionStatus,
    error,
    currentSessionId,
    currentProfile,
    availableProfiles,
    isProfileLoading,
    memoryEnabled,
    historyManager.history,
    pendingHistoryItems,
    streamingStateEnum,
    thinkingContent,
    isStreaming,
    pendingConfirmation,
    isQuitting,
    tokenUsage,
    sessionTokenUsage,
    currentTodo,
    isFullContextMode,
  ]);

  const appActions: AppActions = useMemo(() => ({
    addHistoryItem: historyManager.addItem,
    updateHistoryItem: historyManager.updateItem,
    clearHistory: historyManager.clearItems,
    switchSession,
    createSession,
    setProfile,
    refreshProfiles,
    setMemoryEnabled,
    sendMessage,
    cancelRequest,
    confirmTool,
    quit,
    clearScreen,
    toggleFullContextMode,
    clearError,
  }), [
    historyManager.addItem,
    historyManager.updateItem,
    historyManager.clearItems,
    switchSession,
    createSession,
    setProfile,
    refreshProfiles,
    setMemoryEnabled,
    sendMessage,
    cancelRequest,
    confirmTool,
    quit,
    clearScreen,
    toggleFullContextMode,
    clearError,
  ]);

  return (
    <AppStateContext.Provider value={appState}>
      <AppActionsContext.Provider value={appActions}>
        <App />
      </AppActionsContext.Provider>
    </AppStateContext.Provider>
  );
};
