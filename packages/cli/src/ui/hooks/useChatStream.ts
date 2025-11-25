/**
 * Chat Stream Hook
 * Reference: Gemini CLI ui/hooks/useGeminiStream.ts (simplified for WebSocket)
 *
 * Manages the chat stream including:
 * - WebSocket message handling
 * - Streaming state management
 * - History updates
 * - Tool call processing
 */

import { useState, useRef, useCallback, useEffect } from 'react';
import type { ConnectionManager } from '@aiNagisa/core';
import { StreamingState } from '../contexts/StreamingContext.js';
import {
  MessageType,
  type ToolCallHistoryItem,
  type ToolResultHistoryItem,
  type HistoryItemWithoutId,
} from '../types.js';
import type { UseHistoryManagerReturn } from './useHistoryManager.js';

export interface UseChatStreamOptions {
  connectionManager: ConnectionManager;
  historyManager: UseHistoryManagerReturn;
  currentSessionId: string | null;
}

export interface UseChatStreamReturn {
  // State
  streamingState: StreamingState;
  isStreaming: boolean;
  thinkingContent: string | null;
  pendingConfirmation: any | null;
  error: string | null;

  // Actions
  submitQuery: (text: string) => void;
  cancelRequest: () => void;
  confirmTool: (approved: boolean, message?: string) => void;
  clearError: () => void;
}

/**
 * Hook for managing chat streaming via WebSocket.
 * Handles message sending, response processing, and state management.
 */
export function useChatStream({
  connectionManager,
  historyManager,
  currentSessionId,
}: UseChatStreamOptions): UseChatStreamReturn {
  // State
  const [streamingState, setStreamingState] = useState<StreamingState>(StreamingState.Idle);
  const [isStreaming, setIsStreaming] = useState(false);
  const [thinkingContent, setThinkingContent] = useState<string | null>(null);
  const [pendingConfirmation, setPendingConfirmation] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Refs for tracking current streaming message
  const currentStreamingMessageIdRef = useRef<string | null>(null);

  // Clear error
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // Handle MESSAGE_CREATE event
  const handleMessageCreate = useCallback((message: any) => {
    const isUser = message.role === 'user';
    if (isUser) {
      // User message echoed back from server (usually we add it locally first)
      // Skip if we already added it
    } else {
      // Assistant message - create placeholder
      const msgId = historyManager.addItem({
        type: MessageType.ASSISTANT,
        content: [],
        isStreaming: true,
      } as HistoryItemWithoutId);
      currentStreamingMessageIdRef.current = msgId;
      setStreamingState(StreamingState.Responding);
      setIsStreaming(true);
    }
  }, [historyManager]);

  // Handle STREAMING_UPDATE event
  const handleStreamingUpdate = useCallback((message: any) => {
    // Backend sends accumulated content array
    if (message.content && Array.isArray(message.content)) {
      // Extract thinking content
      const thinkingBlock = message.content.find((b: any) => b.type === 'thinking');
      if (thinkingBlock) {
        setThinkingContent(thinkingBlock.thinking || null);
      }

      // Extract text content and update assistant message
      const textBlocks = message.content.filter((b: any) => b.type === 'text');
      if (textBlocks.length > 0 && currentStreamingMessageIdRef.current) {
        historyManager.updateItem(currentStreamingMessageIdRef.current, {
          content: textBlocks.map((b: any) => ({ type: 'text' as const, text: b.text })),
        });
      }

      // Handle tool calls
      const toolUseBlocks = message.content.filter((b: any) => b.type === 'tool_use');
      for (const block of toolUseBlocks) {
        const existingToolCall = historyManager.history.find(
          (item) => item.type === MessageType.TOOL_CALL && (item as ToolCallHistoryItem).toolCallId === block.id
        );
        if (!existingToolCall) {
          historyManager.addItem({
            type: MessageType.TOOL_CALL,
            toolName: block.name,
            toolInput: block.input || {},
            toolCallId: block.id,
          } as HistoryItemWithoutId);
        }
      }

      // Handle tool results
      const toolResultBlocks = message.content.filter((b: any) => b.type === 'tool_result');
      for (const block of toolResultBlocks) {
        const existingResult = historyManager.history.find(
          (item) => item.type === MessageType.TOOL_RESULT && (item as ToolResultHistoryItem).toolCallId === block.tool_use_id
        );
        if (!existingResult) {
          historyManager.addItem({
            type: MessageType.TOOL_RESULT,
            toolCallId: block.tool_use_id,
            content: typeof block.content === 'string' ? block.content : JSON.stringify(block.content),
            isError: block.is_error,
          } as HistoryItemWithoutId);
        }
      }
    }

    // Check if streaming is complete
    if (message.streaming === false) {
      setIsStreaming(false);
      setStreamingState(StreamingState.Idle);
      if (currentStreamingMessageIdRef.current) {
        historyManager.updateItem(currentStreamingMessageIdRef.current, { isStreaming: false });
      }
      currentStreamingMessageIdRef.current = null;
      setThinkingContent(null);
    }
  }, [historyManager]);

  // Handle TOOL_CONFIRMATION_REQUEST event
  const handleToolConfirmationRequest = useCallback((message: any) => {
    setPendingConfirmation(message);
    setStreamingState(StreamingState.WaitingForConfirmation);
    setIsStreaming(false);
  }, []);

  // Handle ERROR event
  const handleError = useCallback((message: any) => {
    const errorMessage = message.message || message.error || 'Unknown error';
    setError(errorMessage);
    historyManager.addItem({
      type: MessageType.ERROR,
      message: errorMessage,
    } as HistoryItemWithoutId);
    setIsStreaming(false);
    setStreamingState(StreamingState.Idle);
  }, [historyManager]);

  // Set up WebSocket event handlers
  useEffect(() => {
    const handleMessage = (message: any) => {
      switch (message.type) {
        case 'MESSAGE_CREATE':
          handleMessageCreate(message);
          break;
        case 'STREAMING_UPDATE':
          handleStreamingUpdate(message);
          break;
        case 'TOOL_CONFIRMATION_REQUEST':
          handleToolConfirmationRequest(message);
          break;
        case 'ERROR':
          handleError(message);
          break;
      }
    };

    const handleConnectionError = (err: Error) => {
      setError(err.message);
      setIsStreaming(false);
      setStreamingState(StreamingState.Idle);
    };

    connectionManager.on('message', handleMessage);
    connectionManager.on('error', handleConnectionError);

    return () => {
      connectionManager.off('message', handleMessage);
      connectionManager.off('error', handleConnectionError);
    };
  }, [connectionManager, handleMessageCreate, handleStreamingUpdate, handleToolConfirmationRequest, handleError]);

  // Submit a query
  const submitQuery = useCallback((text: string) => {
    if (!text.trim() || isStreaming) return;

    // Add user message to history
    historyManager.addItem({
      type: MessageType.USER,
      text,
    } as HistoryItemWithoutId);

    // Send via WebSocket (format matches backend ChatMessageRequest schema)
    connectionManager.send({
      type: 'CHAT_MESSAGE',
      message: text,
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
    setStreamingState(StreamingState.Responding);
  }, [currentSessionId, historyManager, isStreaming, connectionManager]);

  // Cancel current request
  const cancelRequest = useCallback(() => {
    connectionManager.send({
      type: 'USER_INTERRUPT',
      timestamp: new Date().toISOString(),
    });
    setIsStreaming(false);
    setStreamingState(StreamingState.Idle);
    currentStreamingMessageIdRef.current = null;
    setThinkingContent(null);
  }, [connectionManager]);

  // Confirm or reject tool execution
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
      setStreamingState(StreamingState.Responding);
    } else {
      setStreamingState(StreamingState.Idle);
    }
  }, [pendingConfirmation, connectionManager]);

  return {
    // State
    streamingState,
    isStreaming,
    thinkingContent,
    pendingConfirmation,
    error,

    // Actions
    submitQuery,
    cancelRequest,
    confirmTool,
    clearError,
  };
}
