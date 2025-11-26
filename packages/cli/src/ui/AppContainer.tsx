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
  FileStorageAdapter,
  SessionService,
  apiClient,
} from '@aiNagisa/core';
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
import { useKeypress, type Key } from './hooks/useKeypress.js';
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
    const storageAdapter = new FileStorageAdapter('.ainagisa');
    const sessionService = new SessionService();
    sessionManagerRef.current = new SessionManager(sessionService, storageAdapter);
  }

  const connectionManager = connectionManagerRef.current;
  const sessionManager = sessionManagerRef.current;

  // ========== Local State ==========
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(initialSessionId || null);
  const [isQuitting, setIsQuitting] = useState(false);
  const [memoryEnabled, setMemoryEnabled] = useState(false);

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
  } = useSessionManagement({
    connectionManager,
    sessionManager,
    historyManager,
    setCurrentSessionId,
  });

  // ========== Session Initialization ==========
  useEffect(() => {
    const initSession = async () => {
      try {
        let sessionId = currentSessionId;

        // Create new session if none exists
        if (!sessionId) {
          sessionId = await sessionManager.createSession();
          setCurrentSessionId(sessionId);
        }

        // Connect WebSocket
        await connectionManager.connectToSession(sessionId);

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
    setTimeout(() => {
      exit();
    }, 100);
  }, [connectionManager, exit]);

  const clearScreen = useCallback(() => {
    historyManager.clearItems();
  }, [historyManager]);

  // ========== Global Keypress Handling ==========

  // Handle Ctrl+C to quit
  const handleGlobalKeypress = useCallback((key: Key) => {
    if (key.ctrl && key.name === 'c') {
      quit();
    }
  }, [quit]);

  useKeypress(handleGlobalKeypress, { isActive: true });

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
