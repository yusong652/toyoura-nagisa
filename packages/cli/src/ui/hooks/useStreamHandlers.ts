/**
 * Stream Handlers Hook
 * Event handlers for WebSocket streaming events.
 *
 * Handles:
 * - MESSAGE_CREATE: New message started
 * - STREAMING_UPDATE: Content streaming updates
 * - TOOL_RESULT_UPDATE: Tool execution results
 * - ERROR: Error events
 */

import { useCallback } from 'react';
import type { TokenUsage } from '@toyoura-nagisa/core';
import {
  MessageType,
  type HistoryItemWithoutId,
  type ToolResultHistoryItemWithoutId,
} from '../types.js';
import type {
  MessageCreateEvent,
  StreamingUpdateEvent,
  ToolResultUpdateEvent,
  SubagentToolUseEvent,
} from '../types/streamEvents.js';
import type { UseHistoryManagerReturn } from './useHistoryManager.js';
import type { UsePendingItemsReturn } from './usePendingItems.js';

export interface UseStreamHandlersOptions {
  historyManager: UseHistoryManagerReturn;
  pendingItems: UsePendingItemsReturn;
  setThinkingContent: (content: string | null) => void;
  setTokenUsage: (usage: TokenUsage | null) => void;
  setIsStreaming: (streaming: boolean) => void;
  setError: (error: string | null) => void;
  onStreamStart?: () => void;
  onStreamEnd?: (interrupted: boolean) => void;
}

export interface UseStreamHandlersReturn {
  handleMessageCreate: (event: MessageCreateEvent) => void;
  handleStreamingUpdate: (event: StreamingUpdateEvent) => void;
  handleToolResultUpdate: (event: ToolResultUpdateEvent) => void;
  handleSubagentToolUse: (event: SubagentToolUseEvent) => void;
  handleError: (err: Error) => void;
}

/**
 * Hook for handling WebSocket streaming events.
 */
export function useStreamHandlers({
  historyManager,
  pendingItems,
  setThinkingContent,
  setTokenUsage,
  setIsStreaming,
  setError,
  onStreamStart,
  onStreamEnd,
}: UseStreamHandlersOptions): UseStreamHandlersReturn {
  const {
    pendingAssistantItemRef,
    pendingToolPairsRef,
    seenToolCallIdsRef,
    confirmedToolCallIdsRef,
    createAssistantItem,
    updateAssistantContent,
    stopAssistantStreaming,
    addToolPair,
    fillToolResult,
    addSubagentTool,
    commitAssistantToHistory,
    commitAllPendingToHistory,
    clearAll,
    triggerRerender,
  } = pendingItems;

  // Handle MESSAGE_CREATE event
  const handleMessageCreate = useCallback(
    (event: MessageCreateEvent) => {
      const isUser = event.role === 'user';
      if (isUser) {
        // User message echoed back from server (usually we add it locally first)
        return;
      }

      // New assistant message starting - commit any pending items from previous round
      // This happens when tool calling triggers a new LLM round

      // First, commit pending assistant item if it has content
      if (pendingAssistantItemRef.current && pendingAssistantItemRef.current.content.length > 0) {
        commitAssistantToHistory();
      }

      // Then commit pending tool pairs (in order)
      if (pendingToolPairsRef.current.length > 0) {
        for (const pair of pendingToolPairsRef.current) {
          historyManager.addItem(pair.toolCall);
          if (pair.toolResult) {
            historyManager.addItem(pair.toolResult);
          }
          // Track committed tool call IDs so late-arriving results can still be added
          confirmedToolCallIdsRef.current.add(pair.toolCallId);
        }
        pendingToolPairsRef.current = [];
        seenToolCallIdsRef.current.clear();
        // Don't clear confirmedToolCallIdsRef - late results need to find their tool calls
        triggerRerender();
      }

      // Create new assistant item
      createAssistantItem();
      setIsStreaming(true);
      onStreamStart?.();
    },
    [
      historyManager,
      pendingAssistantItemRef,
      pendingToolPairsRef,
      seenToolCallIdsRef,
      confirmedToolCallIdsRef,
      commitAssistantToHistory,
      createAssistantItem,
      setIsStreaming,
      onStreamStart,
      triggerRerender,
    ]
  );

  // Handle STREAMING_UPDATE event
  const handleStreamingUpdate = useCallback(
    (event: StreamingUpdateEvent) => {
      // Backend sends accumulated content array
      if (event.content && Array.isArray(event.content)) {
        // Extract thinking content
        const thinkingBlock = event.content.find((b) => b.type === 'thinking');
        if (thinkingBlock && thinkingBlock.type === 'thinking') {
          setThinkingContent(thinkingBlock.thinking || null);
        }

        // Update pending assistant item with text and thinking content blocks
        const textAndThinkingContent = event.content.filter(
          (b) => b.type === 'text' || b.type === 'thinking'
        );

        // Skip if streaming is ending or if assistant item was already committed
        // This prevents duplicate messages when tool confirmation interrupts streaming
        if (event.streaming !== false && pendingAssistantItemRef.current !== null) {
          updateAssistantContent(textAndThinkingContent, true);
        }

        // Handle tool calls - create pairs with result=null (placeholder)
        const toolUseBlocks = event.content.filter((b) => b.type === 'tool_use');

        // If tool calls are present, stop streaming indicator on assistant message
        if (toolUseBlocks.length > 0) {
          stopAssistantStreaming();
        }

        for (const block of toolUseBlocks) {
          if (block.type !== 'tool_use') continue;

          addToolPair({
            type: MessageType.TOOL_CALL,
            toolName: block.name,
            toolInput: block.input || {},
            toolCallId: block.id,
          });
        }

        // Handle tool results from streaming_update - fill corresponding pair
        const toolResultBlocks = event.content.filter((b) => b.type === 'tool_result');
        for (const block of toolResultBlocks) {
          if (block.type !== 'tool_result') continue;

          const pair = pendingToolPairsRef.current.find((p) => p.toolCallId === block.tool_use_id);
          if (pair && !pair.toolResult) {
            pair.toolResult = {
              type: MessageType.TOOL_RESULT,
              toolCallId: block.tool_use_id,
              content: typeof block.content === 'string' ? block.content : JSON.stringify(block.content),
              isError: block.is_error,
            };
            triggerRerender();
          }
        }
      }

      // Update token usage if available
      if (event.usage) {
        setTokenUsage(event.usage);
      }

      // Check if streaming is complete
      if (event.streaming === false) {
        // Use backend's interrupted flag as the authority
        if (event.interrupted) {
          // Stream was interrupted by user - don't commit, just clean up
          setIsStreaming(false);
          setThinkingContent(null);
          clearAll();
          onStreamEnd?.(true);
          return;
        }

        // Normal completion - commit all pending items to history
        setIsStreaming(false);
        setThinkingContent(null);
        commitAllPendingToHistory();
        onStreamEnd?.(false);
      }
    },
    [
      pendingToolPairsRef,
      setThinkingContent,
      setTokenUsage,
      setIsStreaming,
      updateAssistantContent,
      stopAssistantStreaming,
      addToolPair,
      commitAllPendingToHistory,
      clearAll,
      onStreamEnd,
      triggerRerender,
    ]
  );

  // Handle TOOL_RESULT_UPDATE event
  const handleToolResultUpdate = useCallback(
    (event: ToolResultUpdateEvent) => {
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

        // Check if this tool call was already committed to history
        if (confirmedToolCallIdsRef.current.has(block.tool_use_id)) {
          // Tool call already in history, add result directly
          historyManager.addItem(toolResult);
          continue;
        }

        // Fill the pending pair with result - it will display via pendingHistoryItems
        // Commit happens when streaming ends or new MESSAGE_CREATE arrives
        const filled = fillToolResult(block.tool_use_id, toolResult);
        if (!filled) {
          // Pair not found - add to history as fallback
          historyManager.addItem(toolResult);
        }
      }
    },
    [
      historyManager,
      confirmedToolCallIdsRef,
      fillToolResult,
    ]
  );

  // Handle ERROR event
  const handleError = useCallback(
    (err: Error) => {
      const errorMessage = err.message || 'Unknown error';
      setError(errorMessage);
      historyManager.addItem({
        type: MessageType.ERROR,
        message: errorMessage,
      } as HistoryItemWithoutId);
      setIsStreaming(false);
      clearAll();
    },
    [historyManager, setError, setIsStreaming, clearAll]
  );

  // Handle SUBAGENT_TOOL_USE event
  // Adds SubAgent tool to its parent invoke_agent tool pair for display
  const handleSubagentToolUse = useCallback(
    (event: SubagentToolUseEvent) => {
      addSubagentTool(event.parent_tool_call_id, {
        toolCallId: event.tool_call_id,
        toolName: event.tool_name,
        toolInput: event.tool_input,
      });
    },
    [addSubagentTool]
  );

  return {
    handleMessageCreate,
    handleStreamingUpdate,
    handleToolResultUpdate,
    handleSubagentToolUse,
    handleError,
  };
}
