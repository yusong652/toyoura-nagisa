/**
 * App Container Component
 * Reference: Gemini CLI ui/AppContainer.tsx
 *
 * This is the main container that:
 * - Initializes core services (ConnectionManager, SessionManager)
 * - Composes hooks for business logic
 * - Provides contexts to child components
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
import { StreamingState } from './contexts/StreamingContext.js';
import { useHistoryManager } from './hooks/useHistoryManager.js';
import { useChatStream } from './hooks/useChatStream.js';
import { useMessageQueue } from './hooks/useMessageQueue.js';
import { type ConnectionStatus } from './types.js';
import { type Config } from '../config/settings.js';

interface AppContainerProps {
  config: Config;
  initialSessionId?: string;
}

export const AppContainer: React.FC<AppContainerProps> = ({
  config,
  initialSessionId,
}) => {
  const { exit } = useApp();

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

  // ========== State ==========
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected');
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(initialSessionId || null);
  const [isQuitting, setIsQuitting] = useState(false);

  // ========== Hooks ==========

  // History management
  const historyManager = useHistoryManager();

  // Chat stream (message handling, streaming state)
  const {
    streamingState,
    isStreaming,
    thinkingContent,
    pendingConfirmation,
    error,
    submitQuery,
    cancelRequest,
    confirmTool,
    clearError,
  } = useChatStream({
    connectionManager,
    historyManager,
    currentSessionId,
  });

  // Message queue (queue messages during streaming)
  const {
    messageQueue,
    addMessage,
    clearQueue,
  } = useMessageQueue({
    isConnected: connectionStatus === 'connected',
    streamingState,
    submitQuery,
  });

  // ========== Connection State Handling ==========
  useEffect(() => {
    const handleStateChange = (data: { oldState: string; newState: string }) => {
      const statusMap: Record<string, ConnectionStatus> = {
        'disconnected': 'disconnected',
        'connecting': 'connecting',
        'connected': 'connected',
        'error': 'error',
        'reconnecting': 'connecting',
        'disconnecting': 'disconnected',
      };
      setConnectionStatus(statusMap[data.newState] || 'disconnected');
    };

    connectionManager.on('stateChanged', handleStateChange);

    return () => {
      connectionManager.off('stateChanged', handleStateChange);
    };
  }, [connectionManager]);

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

  // Send message (uses queue if streaming, otherwise direct submit)
  const sendMessage = useCallback((text: string) => {
    if (!text.trim()) return;

    if (isStreaming || streamingState !== StreamingState.Idle) {
      // Queue message if currently streaming
      addMessage(text);
    } else {
      // Direct submit
      submitQuery(text);
    }
  }, [isStreaming, streamingState, addMessage, submitQuery]);

  const switchSession = useCallback(async (sessionId: string) => {
    connectionManager.disconnect();
    setCurrentSessionId(sessionId);
    historyManager.clearItems();
    clearQueue();
    await connectionManager.connectToSession(sessionId);
  }, [connectionManager, historyManager, clearQueue]);

  const createSession = useCallback(async (name?: string) => {
    const sessionId = await sessionManager.createSession(name);
    await switchSession(sessionId);
    return sessionId;
  }, [sessionManager, switchSession]);

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

  // ========== Context Values ==========

  const appState: AppState = useMemo(() => ({
    connectionStatus,
    error,
    currentSessionId,
    history: historyManager.history,
    streamingState: {
      state: streamingState,
      currentMessageId: null,
      thinkingContent,
    },
    isStreaming,
    pendingConfirmation,
    isQuitting,
    isInputActive: connectionStatus === 'connected' && !isQuitting && !isStreaming,
    messageQueue,
  }), [
    connectionStatus,
    error,
    currentSessionId,
    historyManager.history,
    streamingState,
    thinkingContent,
    isStreaming,
    pendingConfirmation,
    isQuitting,
    messageQueue,
  ]);

  const appActions: AppActions = useMemo(() => ({
    addHistoryItem: historyManager.addItem,
    updateHistoryItem: historyManager.updateItem,
    clearHistory: historyManager.clearItems,
    switchSession,
    createSession,
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
