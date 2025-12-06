/**
 * Pending Items Hook
 * Manages pending assistant messages and tool pairs during streaming.
 *
 * Architecture:
 * - pendingAssistantItem: Currently streaming assistant message
 * - pendingToolPairs: Tool calls with their results (maintains order)
 * - Uses ref + version counter pattern for synchronous access with React re-renders
 */

import { useState, useRef, useCallback, useMemo } from 'react';
import {
  MessageType,
  type HistoryItemWithoutId,
  type AssistantHistoryItemWithoutId,
  type ToolCallHistoryItemWithoutId,
  type ToolResultHistoryItemWithoutId,
  type ContentBlock,
} from '../types.js';
import type { PendingToolPair, SubagentToolItem } from '../types/streamEvents.js';
import type { UseHistoryManagerReturn } from './useHistoryManager.js';

export interface UsePendingItemsOptions {
  historyManager: UseHistoryManagerReturn;
}

export interface UsePendingItemsReturn {
  // State
  pendingAssistantItem: AssistantHistoryItemWithoutId | null;
  pendingHistoryItems: HistoryItemWithoutId[];

  // Refs for synchronous access
  pendingAssistantItemRef: React.MutableRefObject<AssistantHistoryItemWithoutId | null>;
  pendingToolPairsRef: React.MutableRefObject<PendingToolPair[]>;
  seenToolCallIdsRef: React.MutableRefObject<Set<string>>;
  confirmedToolCallIdsRef: React.MutableRefObject<Set<string>>;

  // Actions
  createAssistantItem: () => void;
  updateAssistantContent: (content: ContentBlock[], isStreaming?: boolean) => void;
  stopAssistantStreaming: () => void;
  addToolPair: (toolCall: ToolCallHistoryItemWithoutId) => void;
  fillToolResult: (toolCallId: string, result: ToolResultHistoryItemWithoutId) => boolean;
  addSubagentTool: (parentToolCallId: string, tool: SubagentToolItem) => void;
  commitAssistantToHistory: () => void;
  commitAllPendingToHistory: () => void;
  clearAll: () => void;
  triggerRerender: () => void;
}

/**
 * Hook for managing pending items during chat streaming.
 * Separates pending (streaming) items from committed history.
 */
export function usePendingItems({
  historyManager,
}: UsePendingItemsOptions): UsePendingItemsReturn {
  // Pending assistant item state
  const [pendingAssistantItem, setPendingAssistantItem] =
    useState<AssistantHistoryItemWithoutId | null>(null);

  // Ref for synchronous access (avoids async state issues)
  const pendingAssistantItemRef = useRef<AssistantHistoryItemWithoutId | null>(null);

  // Tool pairs: maintains order of tool calls and their results
  // Using ref to avoid stale closure issues, with version counter to trigger re-renders
  const pendingToolPairsRef = useRef<PendingToolPair[]>([]);
  const [toolPairsVersion, setToolPairsVersion] = useState(0);

  // Refs for tracking seen IDs (avoid duplicates)
  const seenToolCallIdsRef = useRef<Set<string>>(new Set());
  // Track confirmed tool calls (already committed to history)
  const confirmedToolCallIdsRef = useRef<Set<string>>(new Set());

  // Debounce ref to avoid too frequent re-renders (Ink rendering issue)
  const rerenderTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Trigger re-render when tool pairs change (debounced to avoid Ink artifacts)
  const triggerRerender = useCallback(() => {
    // Clear any pending rerender
    if (rerenderTimeoutRef.current) {
      clearTimeout(rerenderTimeoutRef.current);
    }
    // Debounce: wait 50ms before triggering rerender
    rerenderTimeoutRef.current = setTimeout(() => {
      setToolPairsVersion((v) => v + 1);
      rerenderTimeoutRef.current = null;
    }, 50);
  }, []);

  // Create a new assistant item
  const createAssistantItem = useCallback(() => {
    const newItem: AssistantHistoryItemWithoutId = {
      type: MessageType.ASSISTANT,
      content: [],
      isStreaming: true,
    };
    pendingAssistantItemRef.current = newItem;
    setPendingAssistantItem(newItem);
  }, []);

  // Update assistant content
  const updateAssistantContent = useCallback(
    (content: ContentBlock[], isStreaming = true) => {
      setPendingAssistantItem((prev) => {
        let newItem: AssistantHistoryItemWithoutId | null;
        if (!prev) {
          // Don't create new assistant item if there's no content
          if (content.length === 0) {
            newItem = null;
          } else {
            newItem = {
              type: MessageType.ASSISTANT,
              content,
              isStreaming,
            };
          }
        } else {
          newItem = {
            ...prev,
            content,
            isStreaming,
          };
        }
        // Sync ref with state
        pendingAssistantItemRef.current = newItem;
        return newItem;
      });
    },
    []
  );

  // Stop streaming indicator on assistant message
  const stopAssistantStreaming = useCallback(() => {
    setPendingAssistantItem((prev) => {
      const newItem = prev ? { ...prev, isStreaming: false } : prev;
      pendingAssistantItemRef.current = newItem;
      return newItem;
    });
  }, []);

  // Add a tool pair (tool call with result placeholder)
  const addToolPair = useCallback(
    (toolCall: ToolCallHistoryItemWithoutId) => {
      if (seenToolCallIdsRef.current.has(toolCall.toolCallId)) {
        return; // Already seen
      }
      seenToolCallIdsRef.current.add(toolCall.toolCallId);
      pendingToolPairsRef.current.push({
        toolCallId: toolCall.toolCallId,
        toolCall,
        toolResult: null,
      });
      triggerRerender();
    },
    [triggerRerender]
  );

  // Fill tool result for a pending pair
  const fillToolResult = useCallback(
    (toolCallId: string, result: ToolResultHistoryItemWithoutId): boolean => {
      const pair = pendingToolPairsRef.current.find((p) => p.toolCallId === toolCallId);
      if (!pair || pair.toolResult) {
        return false; // Not found or already filled
      }
      pair.toolResult = result;
      pair.toolCall.hasResult = true;  // Mark tool call as having result (stops executing indicator)
      pair.toolCall.isError = result.isError === true;  // Copy error status for display
      triggerRerender();
      return true;
    },
    [triggerRerender]
  );

  // Add a SubAgent tool to its parent invoke_agent tool pair
  const addSubagentTool = useCallback(
    (parentToolCallId: string, tool: SubagentToolItem) => {
      const pair = pendingToolPairsRef.current.find((p) => p.toolCallId === parentToolCallId);
      if (!pair) {
        // Parent tool call not found in pending - might be already committed
        // In this case, we silently ignore (SubAgent tools are ephemeral)
        return;
      }
      if (!pair.subagentTools) {
        pair.subagentTools = [];
      }
      // Avoid duplicates
      if (!pair.subagentTools.some((t) => t.toolCallId === tool.toolCallId)) {
        pair.subagentTools.push(tool);
        triggerRerender();
      }
    },
    [triggerRerender]
  );

  // Commit pending assistant to history (filters empty content)
  const commitAssistantToHistory = useCallback(() => {
    const assistantItem = pendingAssistantItemRef.current;
    if (assistantItem) {
      const validContent = assistantItem.content.filter(
        (blk) => (blk.type === 'text' && blk.text.trim().length > 0) || blk.type === 'thinking'
      );
      historyManager.addItem({
        ...assistantItem,
        content: validContent,
        isStreaming: false,
      });
    }
    pendingAssistantItemRef.current = null;
    setPendingAssistantItem(null);
  }, [historyManager]);

  // Commit all pending items to history (assistant + tool pairs)
  const commitAllPendingToHistory = useCallback(() => {
    // Commit assistant item first
    commitAssistantToHistory();

    // Commit tool pairs in order
    for (const pair of pendingToolPairsRef.current) {
      historyManager.addItem(pair.toolCall);
      if (pair.toolResult) {
        historyManager.addItem(pair.toolResult);
      }
    }

    // Clear pending state
    pendingToolPairsRef.current = [];
    seenToolCallIdsRef.current.clear();
    confirmedToolCallIdsRef.current.clear();
    triggerRerender();
  }, [historyManager, commitAssistantToHistory, triggerRerender]);

  // Clear all pending items (for interrupt/error)
  const clearAll = useCallback(() => {
    setPendingAssistantItem(null);
    pendingAssistantItemRef.current = null;
    pendingToolPairsRef.current = [];
    seenToolCallIdsRef.current.clear();
    confirmedToolCallIdsRef.current.clear();
    triggerRerender();
  }, [triggerRerender]);

  // Compute pending history items for rendering
  const pendingHistoryItems: HistoryItemWithoutId[] = useMemo(() => {
    const items: HistoryItemWithoutId[] = [];

    if (pendingAssistantItem) {
      items.push(pendingAssistantItem);
    }

    // Flatten pairs: toolCall always shown, toolResult shown if available
    for (const pair of pendingToolPairsRef.current) {
      // Copy subagentTools to toolCall for rendering
      const toolCallWithSubagent = {
        ...pair.toolCall,
        subagentTools: pair.subagentTools,
      };
      items.push(toolCallWithSubagent);
      if (pair.toolResult) {
        items.push(pair.toolResult);
      }
    }

    return items;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingAssistantItem, toolPairsVersion]);

  return {
    // State
    pendingAssistantItem,
    pendingHistoryItems,

    // Refs
    pendingAssistantItemRef,
    pendingToolPairsRef,
    seenToolCallIdsRef,
    confirmedToolCallIdsRef,

    // Actions
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
  };
}
