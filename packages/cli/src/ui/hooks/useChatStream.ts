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
 * Key Architecture:
 * - pendingHistoryItems: Items currently being streamed (rendered outside <Static>)
 * - history: Committed items that won't change (rendered in <Static>)
 * - When streaming completes, pending items are committed to history
 *
 * Tool Pair Model:
 * - Tool calls and results are stored as pairs to maintain order
 * - When a tool_use arrives, a pair is created with result=null (placeholder)
 * - When a tool_result arrives, the corresponding pair's result is filled
 * - Rendering: show all tool calls, show results as they arrive (non-blocking)
 * - Commit: when stream ends, commit all pairs in original order
 */

import { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import type { ConnectionManager } from '@toyoura-nagisa/core';
import { StreamingState } from '../contexts/StreamingContext.js';
import {
  MessageType,
  type HistoryItemWithoutId,
  type AssistantHistoryItemWithoutId,
  type ToolCallHistoryItemWithoutId,
  type ToolResultHistoryItemWithoutId,
  type ContentBlock,
  type AgentProfileType,
} from '../types.js';
import type { UseHistoryManagerReturn } from './useHistoryManager.js';

/**
 * Pending tool pair: tool call with its result (or placeholder)
 * Maintains order when tools execute/complete out of order
 */
interface PendingToolPair {
  toolCallId: string;
  toolCall: ToolCallHistoryItemWithoutId;
  toolResult: ToolResultHistoryItemWithoutId | null;  // null = waiting for result
}

// Type for streaming update events from ConnectionManager
interface StreamingUpdateEvent {
  messageId: string;
  content: ContentBlock[];
  streaming: boolean;
  interrupted?: boolean;  // True if streaming was interrupted by user (backend authority)
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    tokens_left: number;
  };
}

// Type for message create events
interface MessageCreateEvent {
  messageId: string;
  role: string;
  initialText: string;
  streaming: boolean;
}

// Type for tool confirmation events
interface ToolConfirmationEvent {
  message_id: string;
  tool_call_id: string;
  tool_name: string;
  command?: string;
  description?: string;
  // New fields for edit confirmation with diff display
  confirmation_type?: 'edit' | 'exec' | 'info';
  file_name?: string;
  file_path?: string;
  file_diff?: string;
  original_content?: string;
  new_content?: string;
}

// Type for tool result update events
interface ToolResultUpdateEvent {
  message_id: string;
  session_id: string;
  content: Array<{
    type: 'tool_result';
    tool_use_id: string;
    tool_name: string;
    content: any;  // llm_content format from backend
    is_error: boolean;
    data?: {
      diff?: {
        content: string;
        additions: number;
        deletions: number;
        file_path: string;
      };
      [key: string]: any;
    };
  }>;
}

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

  // Actions
  submitQuery: (text: string, mentionedFiles?: string[]) => void;
  cancelRequest: () => void;
  confirmTool: (approved: boolean, message?: string) => void;
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
  // State
  const [streamingState, setStreamingState] = useState<StreamingState>(StreamingState.Idle);
  const [isStreaming, setIsStreaming] = useState(false);
  const [thinkingContent, setThinkingContent] = useState<string | null>(null);
  const [pendingConfirmation, setPendingConfirmation] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Pending history items (items currently being streamed - not in <Static>)
  const [pendingAssistantItem, setPendingAssistantItem] = useState<AssistantHistoryItemWithoutId | null>(null);

  // Tool pairs: maintains order of tool calls and their results
  // Using ref to avoid stale closure issues, with version counter to trigger re-renders
  const pendingToolPairsRef = useRef<PendingToolPair[]>([]);
  const [toolPairsVersion, setToolPairsVersion] = useState(0);

  // Refs for tracking seen IDs (avoid duplicates)
  const seenToolCallIdsRef = useRef<Set<string>>(new Set());
  // Track confirmed tool calls (already committed to history)
  const confirmedToolCallIdsRef = useRef<Set<string>>(new Set());

  // Clear error
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // Handle MESSAGE_CREATE event from ConnectionManager
  const handleMessageCreate = useCallback((event: MessageCreateEvent) => {
    const isUser = event.role === 'user';
    if (isUser) {
      // User message echoed back from server (usually we add it locally first)
      // Skip if we already added it
    } else {
      // New assistant message starting - commit any pending items from previous round
      // This happens when tool calling triggers a new LLM round

      // First, commit pending assistant item if it has content
      // Use functional update to get the latest state
      // Keep both text and thinking blocks in history
      setPendingAssistantItem((prevAssistant) => {
        if (prevAssistant && prevAssistant.content.length > 0) {
          const validContent = prevAssistant.content.filter(
            (block) => (block.type === 'text' && block.text.trim().length > 0) || block.type === 'thinking'
          );
          if (validContent.length > 0) {
            historyManager.addItem({
              ...prevAssistant,
              content: validContent,
              isStreaming: false,
            });
          }
        }
        // Return new pending item
        return {
          type: MessageType.ASSISTANT,
          content: [],
          isStreaming: true,
        };
      });

      // Then commit pending tool pairs (in order)
      if (pendingToolPairsRef.current.length > 0) {
        for (const pair of pendingToolPairsRef.current) {
          historyManager.addItem(pair.toolCall);
          if (pair.toolResult) {
            historyManager.addItem(pair.toolResult);
          }
        }
        pendingToolPairsRef.current = [];
        seenToolCallIdsRef.current.clear();
        confirmedToolCallIdsRef.current.clear();
        setToolPairsVersion((v) => v + 1);
      }

      setStreamingState(StreamingState.Responding);
      setIsStreaming(true);
    }
  }, [historyManager]);

  // Handle STREAMING_UPDATE event from ConnectionManager
  const handleStreamingUpdate = useCallback((event: StreamingUpdateEvent) => {
    // Backend sends accumulated content array
    if (event.content && Array.isArray(event.content)) {
      // Extract thinking content
      const thinkingBlock = event.content.find((b) => b.type === 'thinking');
      if (thinkingBlock && thinkingBlock.type === 'thinking') {
        setThinkingContent(thinkingBlock.thinking || null);
      }

      // Update pending assistant item with text and thinking content blocks
      // Skip if streaming is ending - backend sends accumulated content but we may have
      // already committed the assistant message during tool confirmation
      const textAndThinkingContent = event.content.filter(
        (b): b is ContentBlock => b.type === 'text' || b.type === 'thinking'
      );
      if (event.streaming !== false) {
        setPendingAssistantItem((prev) => {
          if (!prev) {
            // Don't create new assistant item if there's no content
            // (e.g., after confirmation, only tool results arrive)
            if (textAndThinkingContent.length === 0) {
              return null;
            }
            return {
              type: MessageType.ASSISTANT,
              content: textAndThinkingContent,
              isStreaming: true,
            };
          }
          return {
            ...prev,
            content: textAndThinkingContent,
          };
        });
      }

      // Handle tool calls - create pairs with result=null (placeholder)
      const toolUseBlocks = event.content.filter((b) => b.type === 'tool_use');
      let pairsUpdated = false;

      // If tool calls are present, stop streaming indicator on assistant message
      if (toolUseBlocks.length > 0) {
        setPendingAssistantItem((prev) => prev ? { ...prev, isStreaming: false } : prev);
      }

      for (const block of toolUseBlocks) {
        if (block.type !== 'tool_use') continue;

        if (!seenToolCallIdsRef.current.has(block.id)) {
          seenToolCallIdsRef.current.add(block.id);
          // Create pair with toolResult=null (placeholder)
          pendingToolPairsRef.current.push({
            toolCallId: block.id,
            toolCall: {
              type: MessageType.TOOL_CALL,
              toolName: block.name,
              toolInput: block.input || {},
              toolCallId: block.id,
            },
            toolResult: null,
          });
          pairsUpdated = true;
        }
      }

      // Handle tool results from streaming_update - fill corresponding pair
      const toolResultBlocks = event.content.filter((b) => b.type === 'tool_result');
      for (const block of toolResultBlocks) {
        if (block.type !== 'tool_result') continue;

        // Find the pair and fill the result
        const pair = pendingToolPairsRef.current.find((p) => p.toolCallId === block.tool_use_id);
        if (pair && !pair.toolResult) {
          pair.toolResult = {
            type: MessageType.TOOL_RESULT,
            toolCallId: block.tool_use_id,
            content: typeof block.content === 'string' ? block.content : JSON.stringify(block.content),
            isError: block.is_error,
          };
          pairsUpdated = true;
        }
      }

      if (pairsUpdated) {
        setToolPairsVersion((v) => v + 1);
      }
    }

    // Check if streaming is complete
    if (event.streaming === false) {
      // Use backend's interrupted flag as the authority (eliminates race condition)
      // Backend sets interrupted=true when user interrupt was processed
      if (event.interrupted) {
        // Stream was interrupted by user - don't commit, just clean up
        setIsStreaming(false);
        setStreamingState(StreamingState.Idle);
        setThinkingContent(null);
        setPendingAssistantItem(null);
        pendingToolPairsRef.current = [];
        seenToolCallIdsRef.current.clear();
        confirmedToolCallIdsRef.current.clear();
        setToolPairsVersion((v) => v + 1);
        return;
      }

      // Normal completion - commit all pending items to history
      const currentPairs = [...pendingToolPairsRef.current];

      // Update state first
      setIsStreaming(false);
      setStreamingState(StreamingState.Idle);
      setThinkingContent(null);

      // Commit pending assistant item if it exists
      // Note: Don't use event.content here - it may contain already-committed content
      // (e.g., if handleToolConfirmationRequest already committed the assistant message)
      // Using functional update to get the latest state and avoid duplicate commits
      setPendingAssistantItem((prevAssistant) => {
        if (prevAssistant) {
          historyManager.addItem({
            ...prevAssistant,
            isStreaming: false,
          });
        }
        return null;
      });

      // Commit tool pairs in order
      for (const pair of currentPairs) {
        historyManager.addItem(pair.toolCall);
        if (pair.toolResult) {
          historyManager.addItem(pair.toolResult);
        }
      }

      // Clear pending state
      pendingToolPairsRef.current = [];
      seenToolCallIdsRef.current.clear();
      confirmedToolCallIdsRef.current.clear();
      setToolPairsVersion((v) => v + 1);
    }
  }, [historyManager]);

  // Handle TOOL_CONFIRMATION_REQUEST event from ConnectionManager
  const handleToolConfirmationRequest = useCallback((event: ToolConfirmationEvent) => {
    // Commit any pending assistant message to history
    // This ensures the assistant message appears before the tool confirmation
    // Note: Do NOT commit tool pairs here - they stay in pending for rendering
    // and will be committed when stream ends
    // Using functional update to avoid race condition with handleStreamingUpdate
    setPendingAssistantItem((prevAssistant) => {
      if (prevAssistant) {
        historyManager.addItem({
          ...prevAssistant,
          isStreaming: false,
        });
      }
      return null;
    });

    // Build confirmation data based on confirmation type
    const confirmationType = event.confirmation_type || 'info';

    if (confirmationType === 'edit' && event.file_diff) {
      // Edit confirmation with diff display
      setPendingConfirmation({
        type: 'edit',
        tool_call_id: event.tool_call_id,
        tool_name: event.tool_name,
        tool_input: {
          command: event.command,
          description: event.description,
        },
        description: event.description,
        fileName: event.file_name || 'unknown',
        filePath: event.file_path || '',
        fileDiff: event.file_diff,
        originalContent: event.original_content || '',
        newContent: event.new_content || '',
      });
    } else if (confirmationType === 'exec') {
      // Exec confirmation (bash commands)
      setPendingConfirmation({
        type: 'exec',
        tool_call_id: event.tool_call_id,
        tool_name: event.tool_name,
        tool_input: {
          command: event.command,
          description: event.description,
        },
        description: event.description,
        rootCommand: event.tool_name,
        command: event.command || '',
      });
    } else {
      // Info confirmation (generic)
      setPendingConfirmation({
        type: 'info',
        tool_call_id: event.tool_call_id,
        tool_name: event.tool_name,
        tool_input: {
          command: event.command,
          description: event.description,
        },
        command: event.command,
        description: event.description,
      });
    }

    setStreamingState(StreamingState.WaitingForConfirmation);
    setIsStreaming(false);
  }, [historyManager]);

  // Handle ERROR event from ConnectionManager
  const handleError = useCallback((err: Error) => {
    const errorMessage = err.message || 'Unknown error';
    setError(errorMessage);
    historyManager.addItem({
      type: MessageType.ERROR,
      message: errorMessage,
    } as HistoryItemWithoutId);
    setIsStreaming(false);
    setStreamingState(StreamingState.Idle);

    // Clear pending items on error
    setPendingAssistantItem(null);
    pendingToolPairsRef.current = [];
    seenToolCallIdsRef.current.clear();
    confirmedToolCallIdsRef.current.clear();
    setToolPairsVersion((v) => v + 1);
  }, [historyManager]);

  // Handle TOOL_RESULT_UPDATE event from ConnectionManager
  // This provides real-time tool result display without API refresh
  const handleToolResultUpdate = useCallback((event: ToolResultUpdateEvent) => {
    let pairsUpdated = false;

    for (const block of event.content) {
      if (block.type !== 'tool_result') continue;

      // Extract text content from llm_content
      let contentText = '';
      const llmContent = block.content;
      if (typeof llmContent === 'string') {
        contentText = llmContent;
      } else if (llmContent && typeof llmContent === 'object') {
        if ('parts' in llmContent && Array.isArray(llmContent.parts)) {
          contentText = llmContent.parts
            .filter((part: any) => part.type === 'text')
            .map((part: any) => part.text || '')
            .join('\n');
        }
      }

      // Extract diff info from data field (for edit/write tools)
      const diff = block.data?.diff;

      const toolResult: ToolResultHistoryItemWithoutId = {
        type: MessageType.TOOL_RESULT,
        toolCallId: block.tool_use_id,
        toolName: block.tool_name,
        content: contentText,
        isError: block.is_error,
        diff: diff,
      };

      // Check if this tool call was already confirmed (committed to history)
      if (confirmedToolCallIdsRef.current.has(block.tool_use_id)) {
        // Tool call already in history, commit result directly to history
        historyManager.addItem(toolResult);
        continue;
      }

      // Find the corresponding pair in pending
      const pair = pendingToolPairsRef.current.find((p) => p.toolCallId === block.tool_use_id);
      if (!pair || pair.toolResult) continue;  // Skip if no pair or already filled

      // Fill the pair's result
      pair.toolResult = toolResult;
      pairsUpdated = true;
    }

    // Trigger re-render if any pairs were updated
    if (pairsUpdated) {
      setToolPairsVersion((v) => v + 1);
    }
  }, [historyManager]);

  // Set up WebSocket event handlers
  // ConnectionManager emits specific events after processing raw WebSocket messages
  useEffect(() => {
    // Listen to ConnectionManager's processed events (not raw 'message')
    connectionManager.on('message_create', handleMessageCreate);
    connectionManager.on('streaming_update', handleStreamingUpdate);
    connectionManager.on('tool_confirmation_request', handleToolConfirmationRequest);
    connectionManager.on('tool_result_update', handleToolResultUpdate);
    connectionManager.on('error', handleError);

    return () => {
      connectionManager.off('message_create', handleMessageCreate);
      connectionManager.off('streaming_update', handleStreamingUpdate);
      connectionManager.off('tool_confirmation_request', handleToolConfirmationRequest);
      connectionManager.off('tool_result_update', handleToolResultUpdate);
      connectionManager.off('error', handleError);
    };
  }, [connectionManager, handleMessageCreate, handleStreamingUpdate, handleToolConfirmationRequest, handleToolResultUpdate, handleError]);

  // Submit a query (backend handles queuing if already streaming)
  const submitQuery = useCallback(async (text: string, mentionedFiles?: string[]) => {
    if (!text.trim()) return;

    // Commit any pending tool pairs to history before adding new user message
    // This ensures tool results appear before the new user message
    if (pendingToolPairsRef.current.length > 0) {
      for (const pair of pendingToolPairsRef.current) {
        historyManager.addItem(pair.toolCall);
        if (pair.toolResult) {
          historyManager.addItem(pair.toolResult);
        }
      }
      pendingToolPairsRef.current = [];
      seenToolCallIdsRef.current.clear();
      setToolPairsVersion((v) => v + 1);
    }

    // Add user message to history (committed immediately)
    historyManager.addItem({
      type: MessageType.USER,
      text,
    } as HistoryItemWithoutId);

    // Send via WebSocket (format matches backend ChatMessageRequest schema)
    // Backend's SessionQueueManager handles queuing if already processing
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
      // Message wasn't sent - connection might not be ready
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
  }, [currentSessionId, currentProfile, memoryEnabled, historyManager, isStreaming, connectionManager]);

  // Cancel current request
  // Note: State cleanup is handled by handleStreamingUpdate when it receives
  // the backend's streaming=false, interrupted=true message.
  // This eliminates race conditions by using backend as the authority.
  const cancelRequest = useCallback(() => {
    // Send interrupt request to backend
    connectionManager.send({
      type: 'USER_INTERRUPT',
      timestamp: new Date().toISOString(),
    });

    // Add system message about interruption (immediate feedback to user)
    historyManager.addItem({
      type: MessageType.INFO,
      message: 'Request cancelled by user.',
    } as HistoryItemWithoutId);

    // Note: Don't clear state here - let handleStreamingUpdate do it
    // when it receives the backend's interrupted=true response.
    // This ensures proper synchronization with backend state.
  }, [connectionManager, historyManager]);

  // Confirm or reject tool execution
  const confirmTool = useCallback((approved: boolean, message?: string) => {
    if (!pendingConfirmation) return;

    const toolCallId = pendingConfirmation.tool_call_id;

    // Note: No info message here - tool result will show rejection status (red error)
    // Adding an info message immediately would cause it to appear before tool results
    // because info goes to committed history while tool results are in pending state

    connectionManager.send({
      type: 'TOOL_CONFIRMATION_RESPONSE',
      tool_call_id: toolCallId,
      approved,
      user_message: message,
      timestamp: new Date().toISOString(),
    });

    // End pending state for this specific tool call:
    // 1. Find and remove the pair from pending
    // 2. Commit tool call to history
    // 3. Track as confirmed (so result goes directly to history when it arrives)
    const pairIndex = pendingToolPairsRef.current.findIndex((p) => p.toolCallId === toolCallId);
    if (pairIndex !== -1) {
      const pair = pendingToolPairsRef.current[pairIndex];
      // Commit tool call to history (no longer pending/blinking)
      historyManager.addItem(pair.toolCall);
      // Remove from pending pairs
      pendingToolPairsRef.current.splice(pairIndex, 1);
      // Track as confirmed
      confirmedToolCallIdsRef.current.add(toolCallId);
      setToolPairsVersion((v) => v + 1);
    }

    setPendingConfirmation(null);

    // Always keep streaming state until backend returns results
    // For approved: backend will execute tool and return results
    // For rejected: backend will return rejection results (and cascade blocked results)
    // State will be set to Idle when handleStreamingUpdate receives streaming=false
    setIsStreaming(true);
    setStreamingState(StreamingState.Responding);
  }, [pendingConfirmation, connectionManager, historyManager]);

  // Compute pending history items for rendering outside <Static>
  // Flatten tool pairs: show all tool calls, show results as they arrive (non-blocking)
  const pendingHistoryItems: HistoryItemWithoutId[] = useMemo(() => {
    const items: HistoryItemWithoutId[] = [];

    if (pendingAssistantItem) {
      items.push(pendingAssistantItem);
    }

    // Flatten pairs: toolCall always shown, toolResult shown if available
    for (const pair of pendingToolPairsRef.current) {
      items.push(pair.toolCall);
      if (pair.toolResult) {
        items.push(pair.toolResult);
      }
    }

    return items;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingAssistantItem, toolPairsVersion]);

  return {
    // State
    streamingState,
    isStreaming,
    thinkingContent,
    pendingConfirmation,
    error,
    pendingHistoryItems,

    // Actions
    submitQuery,
    cancelRequest,
    confirmTool,
    clearError,
  };
}
