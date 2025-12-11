/**
 * Chat Stream Hook
 * Reference: Gemini CLI ui/hooks/useGeminiStream.ts (simplified for WebSocket)
 *
 * Manages the chat stream including:
 * - WebSocket message handling
 * - Streaming state management
 * - History updates (with pending/committed separation)
 * - Tool call processing
 *
 * Architecture:
 * This hook composes several smaller hooks:
 * - usePendingItems: Manages pending assistant messages and tool pairs
 * - useToolConfirmation: Handles tool confirmation flow
 * - useStreamHandlers: Event handlers for WebSocket events
 */

import { useState, useCallback, useEffect } from 'react';
import type { ConnectionManager, TokenUsage } from '@toyoura-nagisa/core';
import { StreamingState } from '../contexts/StreamingContext.js';
import {
  MessageType,
  type HistoryItemWithoutId,
  type AgentProfileType,
} from '../types.js';
import type { UseHistoryManagerReturn } from './useHistoryManager.js';
import { usePendingItems } from './usePendingItems.js';
import { useToolConfirmation } from './useToolConfirmation.js';
import { useStreamHandlers } from './useStreamHandlers.js';

export interface UseChatStreamOptions {
  connectionManager: ConnectionManager;
  historyManager: UseHistoryManagerReturn;
  currentSessionId: string | null;
  currentProfile: AgentProfileType;
  memoryEnabled: boolean;
}

export interface UseChatStreamReturn {
  // State
  streamingState: StreamingState;
  isStreaming: boolean;
  thinkingContent: string | null;
  pendingConfirmation: any | null;
  error: string | null;
  pendingHistoryItems: HistoryItemWithoutId[];
  tokenUsage: TokenUsage | null;

  // Actions
  submitQuery: (text: string, mentionedFiles?: string[]) => void;
  cancelRequest: () => void;
  confirmTool: (outcome: 'approve' | 'reject' | 'reject_and_tell', message?: string) => void;
  clearError: () => void;
}

/**
 * Hook for managing chat streaming via WebSocket.
 * Handles message sending, response processing, and state management.
 *
 * Uses a pending/committed model:
 * - Streaming messages stay in pendingHistoryItems (can update in real-time)
 * - Completed messages are committed to history (rendered in <Static>)
 */
export function useChatStream({
  connectionManager,
  historyManager,
  currentSessionId,
  currentProfile,
  memoryEnabled,
}: UseChatStreamOptions): UseChatStreamReturn {
  // Core state
  const [streamingState, setStreamingState] = useState<StreamingState>(StreamingState.Idle);
  const [isStreaming, setIsStreaming] = useState(false);
  const [thinkingContent, setThinkingContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tokenUsage, setTokenUsage] = useState<TokenUsage | null>(null);

  // Clear error
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // Pending items management
  const pendingItems = usePendingItems({ historyManager });

  // Tool confirmation management
  const toolConfirmation = useToolConfirmation({
    connectionManager,
    onConfirmationStart: () => {
      // Commit assistant message before showing confirmation
      pendingItems.commitAssistantToHistory();
      setStreamingState(StreamingState.WaitingForConfirmation);
      setIsStreaming(false);
    },
    onConfirmationEnd: (outcome) => {
      // Handle based on outcome:
      // - approve/reject_and_tell: Resume streaming, agent continues
      // - reject: Stay in idle state, user will input via main input
      if (outcome === 'reject') {
        // User rejected - stay idle, user will provide new input
        setStreamingState(StreamingState.Idle);
        setIsStreaming(false);
      } else {
        // approve or reject_and_tell - agent continues execution
        setIsStreaming(true);
        setStreamingState(StreamingState.Responding);
      }
    },
  });

  // Stream event handlers
  const streamHandlers = useStreamHandlers({
    historyManager,
    pendingItems,
    setThinkingContent,
    setTokenUsage,
    setIsStreaming,
    setError,
    onStreamStart: () => {
      setStreamingState(StreamingState.Responding);
    },
    onStreamEnd: () => {
      setStreamingState(StreamingState.Idle);
    },
  });

  // Set up WebSocket event handlers
  useEffect(() => {
    connectionManager.on('message_create', streamHandlers.handleMessageCreate);
    connectionManager.on('streaming_update', streamHandlers.handleStreamingUpdate);
    connectionManager.on('tool_confirmation_request', toolConfirmation.handleToolConfirmationRequest);
    connectionManager.on('tool_result_update', streamHandlers.handleToolResultUpdate);
    connectionManager.on('subagent_tool_use', streamHandlers.handleSubagentToolUse);
    connectionManager.on('subagent_tool_result', streamHandlers.handleSubagentToolResult);
    connectionManager.on('error', streamHandlers.handleError);

    return () => {
      connectionManager.off('message_create', streamHandlers.handleMessageCreate);
      connectionManager.off('streaming_update', streamHandlers.handleStreamingUpdate);
      connectionManager.off('tool_confirmation_request', toolConfirmation.handleToolConfirmationRequest);
      connectionManager.off('tool_result_update', streamHandlers.handleToolResultUpdate);
      connectionManager.off('subagent_tool_use', streamHandlers.handleSubagentToolUse);
      connectionManager.off('subagent_tool_result', streamHandlers.handleSubagentToolResult);
      connectionManager.off('error', streamHandlers.handleError);
    };
  }, [connectionManager, streamHandlers, toolConfirmation]);

  // Submit a query (backend handles queuing if already streaming)
  const submitQuery = useCallback(
    async (text: string, mentionedFiles?: string[]) => {
      if (!text.trim()) return;

      // Commit any pending tool pairs to history before adding new user message
      pendingItems.commitAllPendingToHistory();

      // Add user message to history (committed immediately)
      historyManager.addItem({
        type: MessageType.USER,
        text,
      } as HistoryItemWithoutId);

      // Send via WebSocket
      const sent = await connectionManager.send({
        type: 'CHAT_MESSAGE',
        message: text,
        session_id: currentSessionId,
        timestamp: new Date().toISOString(),
        stream_response: true,
        agent_profile: currentProfile,
        enable_memory: memoryEnabled,
        tts_enabled: false,
        files: [],
        mentioned_files: mentionedFiles || [],
      });

      if (!sent) {
        historyManager.addItem({
          type: MessageType.ERROR,
          message: 'Failed to send message - WebSocket not connected',
        } as HistoryItemWithoutId);
        return;
      }

      // Only set streaming state if not already streaming
      if (!isStreaming) {
        setIsStreaming(true);
        setStreamingState(StreamingState.Responding);
      }
    },
    [
      currentSessionId,
      currentProfile,
      memoryEnabled,
      historyManager,
      isStreaming,
      connectionManager,
      pendingItems,
    ]
  );

  // Cancel current request
  const cancelRequest = useCallback(() => {
    // Send interrupt request to backend
    connectionManager.send({
      type: 'USER_INTERRUPT',
      timestamp: new Date().toISOString(),
    });

    // Add system message about interruption
    historyManager.addItem({
      type: MessageType.INFO,
      message: 'Request cancelled by user.',
    } as HistoryItemWithoutId);

    // State cleanup is handled by handleStreamingUpdate when backend responds
  }, [connectionManager, historyManager]);

  return {
    // State
    streamingState,
    isStreaming,
    thinkingContent,
    pendingConfirmation: toolConfirmation.pendingConfirmation,
    error,
    pendingHistoryItems: pendingItems.pendingHistoryItems,
    tokenUsage,

    // Actions
    submitQuery,
    cancelRequest,
    confirmTool: toolConfirmation.confirmTool,
    clearError,
  };
}
