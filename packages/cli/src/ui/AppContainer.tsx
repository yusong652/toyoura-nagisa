/**
 * App Container Component
 * Reference: Gemini CLI ui/AppContainer.tsx (simplified)
 *
 * This is the main container that:
 * - Initializes core services (ConnectionManager, SessionManager)
 * - Manages application state
 * - Provides contexts to child components
 * - Handles WebSocket events
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
import {
  MessageType,
  type ConnectionStatus,
  type UserHistoryItem,
  type AssistantHistoryItem,
  type ToolCallHistoryItem,
  type ToolResultHistoryItem,
  type ErrorHistoryItem,
} from './types.js';
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

  // Initialize core services
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
    // Note: SessionService uses global apiClient, baseURL configured separately
    const sessionService = new SessionService();
    sessionManagerRef.current = new SessionManager(sessionService, storageAdapter);
  }

  const connectionManager = connectionManagerRef.current;
  const sessionManager = sessionManagerRef.current;

  // History management
  const historyManager = useHistoryManager();

  // App state
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected');
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(initialSessionId || null);
  const [error, setError] = useState<string | null>(null);
  const [isQuitting, setIsQuitting] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentStreamingMessageId, setCurrentStreamingMessageId] = useState<string | null>(null);
  const [thinkingContent, setThinkingContent] = useState<string | null>(null);
  const [pendingConfirmation, setPendingConfirmation] = useState<any>(null);

  // Set up WebSocket event handlers
  useEffect(() => {
    const handleStateChange = (data: { oldState: string; newState: string }) => {
      // ConnectionState enum values are lowercase: 'connected', 'disconnected', etc.
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

    const handleMessage = (message: any) => {
      switch (message.type) {
        case 'MESSAGE_CREATE': {
          const isUser = message.role === 'user';
          if (isUser) {
            historyManager.addItem({
              type: MessageType.USER,
              text: message.content || '',
            } as Omit<UserHistoryItem, 'id'>);
          } else {
            const msgId = historyManager.addItem({
              type: MessageType.ASSISTANT,
              content: [],
              isStreaming: true,
            } as any);
            setCurrentStreamingMessageId(msgId);
            setIsStreaming(true);
          }
          break;
        }

        case 'STREAMING_UPDATE': {
          // Backend sends accumulated content array: [{type: "thinking", thinking: "..."}, {type: "text", text: "..."}]
          if (message.content && Array.isArray(message.content)) {
            // Extract thinking content
            const thinkingBlock = message.content.find((b: any) => b.type === 'thinking');
            if (thinkingBlock) {
              setThinkingContent(thinkingBlock.thinking || null);
            }

            // Extract text content and update assistant message
            const textBlocks = message.content.filter((b: any) => b.type === 'text');
            if (textBlocks.length > 0 && currentStreamingMessageId) {
              historyManager.updateItem(currentStreamingMessageId, {
                content: textBlocks.map((b: any) => ({ type: 'text' as const, text: b.text })),
              });
            }

            // Handle tool calls
            const toolUseBlocks = message.content.filter((b: any) => b.type === 'tool_use');
            for (const block of toolUseBlocks) {
              // Check if we already added this tool call
              const existingToolCall = historyManager.history.find(
                (item) => item.type === MessageType.TOOL_CALL && (item as any).toolCallId === block.id
              );
              if (!existingToolCall) {
                historyManager.addItem({
                  type: MessageType.TOOL_CALL,
                  toolName: block.name,
                  toolInput: block.input || {},
                  toolCallId: block.id,
                } as Omit<ToolCallHistoryItem, 'id'>);
              }
            }

            // Handle tool results
            const toolResultBlocks = message.content.filter((b: any) => b.type === 'tool_result');
            for (const block of toolResultBlocks) {
              const existingResult = historyManager.history.find(
                (item) => item.type === MessageType.TOOL_RESULT && (item as any).toolCallId === block.tool_use_id
              );
              if (!existingResult) {
                historyManager.addItem({
                  type: MessageType.TOOL_RESULT,
                  toolCallId: block.tool_use_id,
                  content: typeof block.content === 'string' ? block.content : JSON.stringify(block.content),
                  isError: block.is_error,
                } as Omit<ToolResultHistoryItem, 'id'>);
              }
            }
          }

          // Check if streaming is complete
          if (message.streaming === false) {
            setIsStreaming(false);
            if (currentStreamingMessageId) {
              historyManager.updateItem(currentStreamingMessageId, { isStreaming: false });
            }
            setCurrentStreamingMessageId(null);
            setThinkingContent(null);
          }
          break;
        }

        case 'TOOL_CONFIRMATION_REQUEST':
          setPendingConfirmation(message);
          setIsStreaming(false);
          break;

        case 'ERROR':
          setError(message.message || 'Unknown error');
          historyManager.addItem({
            type: MessageType.ERROR,
            message: message.message || 'Unknown error',
          } as Omit<ErrorHistoryItem, 'id'>);
          break;
      }
    };

    const handleError = (err: Error) => {
      setError(err.message);
    };

    connectionManager.on('stateChanged', handleStateChange);
    connectionManager.on('message', handleMessage);
    connectionManager.on('error', handleError);

    return () => {
      connectionManager.off('stateChanged', handleStateChange);
      connectionManager.off('message', handleMessage);
      connectionManager.off('error', handleError);
    };
  }, [connectionManager, historyManager, currentStreamingMessageId]);

  // Connect to session on mount
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
        setError(err instanceof Error ? err.message : 'Failed to initialize session');
      }
    };

    initSession();

    return () => {
      connectionManager.disconnect();
    };
  }, []);  // Only run once on mount

  // Actions
  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isStreaming) return;

    // Add user message to history
    historyManager.addItem({
      type: MessageType.USER,
      text,
    } as Omit<UserHistoryItem, 'id'>);

    // Send via WebSocket (format matches backend ChatMessageRequest schema)
    connectionManager.send({
      type: 'CHAT_MESSAGE',
      message: text,  // Backend expects 'message' field, not 'content'
      session_id: currentSessionId,
      timestamp: new Date().toISOString(),
      stream_response: true,
      agent_profile: 'general',
      enable_memory: true,
      tts_enabled: false,
      files: [],
      mentioned_files: [],
    });

    setIsStreaming(true);
  }, [currentSessionId, historyManager, isStreaming, connectionManager]);

  const confirmTool = useCallback((approved: boolean, message?: string) => {
    if (!pendingConfirmation) return;

    connectionManager.send({
      type: 'TOOL_CONFIRMATION_RESPONSE',
      tool_call_id: pendingConfirmation.tool_call_id,
      approved,
      user_message: message,
      timestamp: new Date().toISOString(),
    });

    setPendingConfirmation(null);
    if (approved) {
      setIsStreaming(true);
    }
  }, [pendingConfirmation, connectionManager]);

  const cancelRequest = useCallback(() => {
    connectionManager.send({
      type: 'CANCEL_REQUEST',
      timestamp: new Date().toISOString(),
    });
    setIsStreaming(false);
    setCurrentStreamingMessageId(null);
    setThinkingContent(null);
  }, [connectionManager]);

  const switchSession = useCallback(async (sessionId: string) => {
    connectionManager.disconnect();
    setCurrentSessionId(sessionId);
    historyManager.clearItems();
    await connectionManager.connectToSession(sessionId);
  }, [connectionManager, historyManager]);

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

  // Build state and actions objects
  const appState: AppState = useMemo(() => ({
    connectionStatus,
    error,
    currentSessionId,
    history: historyManager.history,
    streamingState: {
      state: isStreaming
        ? StreamingState.Responding
        : pendingConfirmation
          ? StreamingState.WaitingForConfirmation
          : StreamingState.Idle,
      currentMessageId: currentStreamingMessageId,
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
    historyManager.history,
    isStreaming,
    currentStreamingMessageId,
    thinkingContent,
    pendingConfirmation,
    isQuitting,
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
  ]);

  return (
    <AppStateContext.Provider value={appState}>
      <AppActionsContext.Provider value={appActions}>
        <App />
      </AppActionsContext.Provider>
    </AppStateContext.Provider>
  );
};
