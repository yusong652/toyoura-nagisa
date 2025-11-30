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
 */

import { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import type { ConnectionManager } from '@toyoura-nagisa/core';
import { StreamingState } from '../contexts/StreamingContext.js';
import {
  MessageType,
  type HistoryItemWithoutId,
  type AssistantHistoryItemWithoutId,
  type ContentBlock,
  type AgentProfileType,
} from '../types.js';
import type { UseHistoryManagerReturn } from './useHistoryManager.js';

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
  const [pendingToolItems, setPendingToolItems] = useState<HistoryItemWithoutId[]>([]);

  // Refs for tracking seen IDs (avoid duplicates)
  const seenToolCallIdsRef = useRef<Set<string>>(new Set());
  const seenToolResultIdsRef = useRef<Set<string>>(new Set());

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

      // Then commit pending tool items
      setPendingToolItems((prevToolItems) => {
        if (prevToolItems.length > 0) {
          for (const toolItem of prevToolItems) {
            historyManager.addItem(toolItem);
          }
          seenToolCallIdsRef.current.clear();
          seenToolResultIdsRef.current.clear();
        }
        return [];
      });

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
      const textAndThinkingContent = event.content.filter(
        (b): b is ContentBlock => b.type === 'text' || b.type === 'thinking'
      );
      setPendingAssistantItem((prev) => {
        if (!prev) {
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

      // Handle tool calls - use Set to track seen IDs, add to pending
      const toolUseBlocks = event.content.filter((b) => b.type === 'tool_use');
      const newToolItems: HistoryItemWithoutId[] = [];

      // If tool calls are present, stop streaming indicator on assistant message
      if (toolUseBlocks.length > 0) {
        setPendingAssistantItem((prev) => prev ? { ...prev, isStreaming: false } : prev);
      }

      for (const block of toolUseBlocks) {
        if (block.type !== 'tool_use') continue;

        if (!seenToolCallIdsRef.current.has(block.id)) {
          seenToolCallIdsRef.current.add(block.id);
          newToolItems.push({
            type: MessageType.TOOL_CALL,
            toolName: block.name,
            toolInput: block.input || {},
            toolCallId: block.id,
          } as HistoryItemWithoutId);
        }
      }

      // Handle tool results - use Set to track seen IDs, add to pending
      const toolResultBlocks = event.content.filter((b) => b.type === 'tool_result');
      for (const block of toolResultBlocks) {
        if (block.type !== 'tool_result') continue;

        if (!seenToolResultIdsRef.current.has(block.tool_use_id)) {
          seenToolResultIdsRef.current.add(block.tool_use_id);
          newToolItems.push({
            type: MessageType.TOOL_RESULT,
            toolCallId: block.tool_use_id,
            content: typeof block.content === 'string' ? block.content : JSON.stringify(block.content),
            isError: block.is_error,
          } as HistoryItemWithoutId);
        }
      }

      if (newToolItems.length > 0) {
        setPendingToolItems((prev) => [...prev, ...newToolItems]);
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
        setPendingToolItems([]);
        seenToolCallIdsRef.current.clear();
        seenToolResultIdsRef.current.clear();
        return;
      }

      // Normal completion - commit all pending items to history
      const currentToolItems = [...pendingToolItems];

      // Update state first
      setIsStreaming(false);
      setStreamingState(StreamingState.Idle);
      setThinkingContent(null);

      // Commit to history - use the latest content from the event
      // Keep both text and thinking blocks in history for display
      if (event.content && Array.isArray(event.content)) {
        const finalContent = event.content.filter(
          (b): b is ContentBlock => b.type === 'text' || b.type === 'thinking'
        );
        if (finalContent.length > 0) {
          historyManager.addItem({
            type: MessageType.ASSISTANT,
            content: finalContent,
            isStreaming: false,
          });
        }
      }

      // Commit tool items
      for (const toolItem of currentToolItems) {
        historyManager.addItem(toolItem);
      }

      // Clear pending state
      setPendingAssistantItem(null);
      setPendingToolItems([]);
      seenToolCallIdsRef.current.clear();
      seenToolResultIdsRef.current.clear();
    }
  }, [pendingToolItems, historyManager]);

  // Handle TOOL_CONFIRMATION_REQUEST event from ConnectionManager
  const handleToolConfirmationRequest = useCallback((event: ToolConfirmationEvent) => {
    // First, commit any pending assistant message to history
    // This ensures the assistant message appears before the tool confirmation
    if (pendingAssistantItem) {
      historyManager.addItem({
        ...pendingAssistantItem,
        isStreaming: false,
      } as HistoryItemWithoutId);
      setPendingAssistantItem(null);
    }

    // Commit any pending tool items to history
    for (const toolItem of pendingToolItems) {
      historyManager.addItem(toolItem);
    }
    setPendingToolItems([]);

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
  }, [pendingAssistantItem, pendingToolItems, historyManager]);

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
    setPendingToolItems([]);
  }, [historyManager]);

  // Handle TOOL_RESULT_UPDATE event from ConnectionManager
  // This provides real-time tool result display without API refresh
  const handleToolResultUpdate = useCallback((event: ToolResultUpdateEvent) => {
    // Process each tool result in the content array
    const newToolResults: HistoryItemWithoutId[] = [];

    for (const block of event.content) {
      if (block.type !== 'tool_result') continue;

      // Skip if already seen
      if (seenToolResultIdsRef.current.has(block.tool_use_id)) continue;
      seenToolResultIdsRef.current.add(block.tool_use_id);

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

      newToolResults.push({
        type: MessageType.TOOL_RESULT,
        toolCallId: block.tool_use_id,
        toolName: block.tool_name,
        content: contentText,
        isError: block.is_error,
        diff: diff,
      } as HistoryItemWithoutId);
    }

    // Add to pending tool items (will be committed when streaming ends)
    if (newToolResults.length > 0) {
      setPendingToolItems((prev) => [...prev, ...newToolResults]);
    }
  }, []);

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

    // Note: No info message here - tool result will show rejection status (red error)
    // Adding an info message immediately would cause it to appear before tool results
    // because info goes to committed history while tool results are in pending state

    connectionManager.send({
      type: 'TOOL_CONFIRMATION_RESPONSE',
      tool_call_id: pendingConfirmation.tool_call_id,
      approved,
      user_message: message,
      timestamp: new Date().toISOString(),
    });

    setPendingConfirmation(null);

    // Always keep streaming state until backend returns results
    // For approved: backend will execute tool and return results
    // For rejected: backend will return rejection results (and cascade blocked results)
    // State will be set to Idle when handleStreamingUpdate receives streaming=false
    setIsStreaming(true);
    setStreamingState(StreamingState.Responding);
  }, [pendingConfirmation, connectionManager]);

  // Compute pending history items for rendering outside <Static>
  const pendingHistoryItems: HistoryItemWithoutId[] = useMemo(() => {
    const items: HistoryItemWithoutId[] = [];

    if (pendingAssistantItem) {
      items.push(pendingAssistantItem);
    }

    items.push(...pendingToolItems);

    return items;
  }, [pendingAssistantItem, pendingToolItems]);

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
