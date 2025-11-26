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
  sessionService,
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
import { MessageType, type ConnectionStatus, type AgentProfileType, type AgentProfileInfo, type ContentBlock } from './types.js';
import { type Config } from '../config/settings.js';
import { profileCommand } from './commands/profileCommand.js';
import { memoryCommand } from './commands/memoryCommand.js';

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

  // Agent profile state
  const [currentProfile, setCurrentProfile] = useState<AgentProfileType>('pfc');
  const [availableProfiles, setAvailableProfiles] = useState<AgentProfileInfo[]>([]);
  const [isProfileLoading, setIsProfileLoading] = useState(false);

  // Memory state (disabled by default)
  const [memoryEnabled, setMemoryEnabled] = useState(false);

  // ========== Hooks ==========

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

  // Message queue (queue messages during streaming)
  const {
    messageQueue,
    addMessage,
    clearQueue,
  } = useMessageQueue({
    isConnected: connectionStatus === 'connected',
    streamingState: streamingStateEnum,
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

  // Process slash commands
  const handleSlashCommand = useCallback((text: string): boolean => {
    const trimmed = text.trim();
    if (!trimmed.startsWith('/')) return false;

    // Parse command and args
    const spaceIndex = trimmed.indexOf(' ');
    const commandName = spaceIndex === -1
      ? trimmed.slice(1).toLowerCase()
      : trimmed.slice(1, spaceIndex).toLowerCase();
    const args = spaceIndex === -1 ? '' : trimmed.slice(spaceIndex + 1);

    // Add user message to history
    historyManager.addItem({
      type: MessageType.USER,
      text: trimmed,
    });

    // Handle built-in commands
    if (commandName === 'profile' || commandName === 'p') {
      const result = profileCommand.action?.({} as any, args);
      if (result && typeof result === 'object' && 'type' in result) {
        if (result.type === 'message') {
          historyManager.addItem({
            type: result.messageType === 'error' ? MessageType.ERROR : MessageType.INFO,
            message: result.content,
          });
        } else if (result.type === 'profile_switch') {
          const newProfile = result.profile as AgentProfileType;
          setCurrentProfile(newProfile);
          historyManager.addItem({
            type: MessageType.INFO,
            message: `Profile switched to: ${newProfile}`,
          });
        }
      }
      return true;
    }

    // Handle memory command
    if (commandName === 'memory' || commandName === 'm') {
      const result = memoryCommand.action?.({} as any, args);
      if (result && typeof result === 'object' && 'type' in result) {
        if (result.type === 'message') {
          historyManager.addItem({
            type: result.messageType === 'error' ? MessageType.ERROR : MessageType.INFO,
            message: result.content,
          });
        } else if (result.type === 'memory_toggle') {
          const enabled = (result as any).enabled as boolean;
          setMemoryEnabled(enabled);
          historyManager.addItem({
            type: MessageType.INFO,
            message: `Memory ${enabled ? 'enabled' : 'disabled'}`,
          });
        }
      }
      return true;
    }

    // Unknown command
    historyManager.addItem({
      type: MessageType.ERROR,
      message: `Unknown command: /${commandName}\n\nAvailable commands:\n  /profile, /p - View or switch agent profile\n  /memory, /m  - Toggle long-term memory`,
    });
    return true;
  }, [historyManager, setCurrentProfile, setMemoryEnabled]);

  // Send message (uses queue if streaming, otherwise direct submit)
  const sendMessage = useCallback((text: string) => {
    if (!text.trim()) return;

    // Check for slash commands first
    if (text.trim().startsWith('/')) {
      handleSlashCommand(text);
      return;
    }

    if (isStreaming || streamingStateEnum !== StreamingState.Idle) {
      // Queue message if currently streaming
      addMessage(text);
    } else {
      // Direct submit
      submitQuery(text);
    }
  }, [isStreaming, streamingStateEnum, addMessage, submitQuery, handleSlashCommand]);

  const switchSession = useCallback(async (sessionId: string) => {
    connectionManager.disconnect();
    setCurrentSessionId(sessionId);
    historyManager.clearItems();
    clearQueue();

    // Load chat history for the session
    try {
      const historyResponse = await sessionService.getSessionHistory(sessionId);
      if (historyResponse.history && historyResponse.history.length > 0) {
        // Convert backend messages to CLI history items
        for (const msg of historyResponse.history) {
          const timestamp = msg.timestamp ? new Date(msg.timestamp).getTime() : Date.now();

          if (msg.role === 'user') {
            // User message - extract text content
            let textContent = '';
            if (typeof msg.content === 'string') {
              textContent = msg.content;
            } else if (Array.isArray(msg.content)) {
              // Check for tool_result blocks (user messages can contain tool results)
              for (const block of msg.content) {
                if (block.type === 'text' && block.text) {
                  textContent += block.text;
                } else if (block.type === 'tool_result') {
                  // Add tool result as a separate history item
                  const resultContent = block.content?.parts
                    ?.map((p: any) => p.text || '')
                    .join('\n') || '';
                  historyManager.addItem({
                    type: MessageType.TOOL_RESULT,
                    toolCallId: block.tool_use_id || '',
                    content: resultContent,
                    isError: block.is_error || false,
                  }, timestamp);
                }
              }
            }
            // Only add user message if there's text content
            if (textContent.trim()) {
              historyManager.addItem({
                type: MessageType.USER,
                text: textContent,
              }, timestamp);
            }
          } else if (msg.role === 'assistant') {
            // Assistant message - process all content blocks
            const contentBlocks: ContentBlock[] = [];
            const toolCalls: Array<{ id: string; name: string; input: Record<string, unknown> }> = [];

            if (typeof msg.content === 'string') {
              contentBlocks.push({ type: 'text', text: msg.content });
            } else if (Array.isArray(msg.content)) {
              for (const block of msg.content) {
                if (block.type === 'text' && block.text) {
                  contentBlocks.push({ type: 'text', text: block.text });
                } else if (block.type === 'thinking' && block.thinking) {
                  contentBlocks.push({ type: 'thinking', thinking: block.thinking });
                } else if (block.type === 'tool_use') {
                  // Collect tool calls to add as separate items
                  toolCalls.push({
                    id: block.id || '',
                    name: block.name || '',
                    input: block.input || {},
                  });
                }
              }
            }

            // Add assistant message if there's text/thinking content
            if (contentBlocks.length > 0) {
              historyManager.addItem({
                type: MessageType.ASSISTANT,
                content: contentBlocks,
              }, timestamp);
            }

            // Add tool call items
            for (const tc of toolCalls) {
              historyManager.addItem({
                type: MessageType.TOOL_CALL,
                toolCallId: tc.id,
                toolName: tc.name,
                toolInput: tc.input,
              }, timestamp);
            }
          }
        }
      }
    } catch (err) {
      console.error('[AppContainer] Failed to load session history:', err);
    }

    await connectionManager.connectToSession(sessionId);
  }, [connectionManager, historyManager, clearQueue]);

  const createSession = useCallback(async (name?: string) => {
    const sessionId = await sessionManager.createSession(name);
    await switchSession(sessionId);
    return sessionId;
  }, [sessionManager, switchSession]);

  // Fetch available profiles from backend
  const refreshProfiles = useCallback(async () => {
    setIsProfileLoading(true);
    try {
      const response = await apiClient.get<{
        success: boolean;
        profiles: AgentProfileInfo[];
      }>('/api/profiles');
      if (response.success && response.profiles) {
        setAvailableProfiles(response.profiles);
      }
    } catch (err) {
      console.error('[AppContainer] Failed to fetch profiles:', err);
    } finally {
      setIsProfileLoading(false);
    }
  }, []);

  // Set current profile
  const setProfile = useCallback((profile: AgentProfileType) => {
    setCurrentProfile(profile);
  }, []);

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
    isInputActive: connectionStatus === 'connected' && !isQuitting && !isStreaming,
    messageQueue,
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
    messageQueue,
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
