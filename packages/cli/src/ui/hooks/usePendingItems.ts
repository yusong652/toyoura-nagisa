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
import type { PendingToolPair } from '../types/streamEvents.js';
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
  commitAssistantToHistory: () => void;
  commitAllPendingToHistory: () => void;
  commitToolPairToHistory: (toolCallId: string, result: ToolResultHistoryItemWithoutId) => void;
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

  // Trigger re-render when tool pairs change
  const triggerRerender = useCallback(() => {
    setToolPairsVersion((v) => v + 1);
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
      triggerRerender();
      return true;
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

  // Commit a specific tool pair to history (used when tool result arrives)
  const commitToolPairToHistory = useCallback(
    (toolCallId: string, result: ToolResultHistoryItemWithoutId) => {
      // Check if already confirmed
      if (confirmedToolCallIdsRef.current.has(toolCallId)) {
        // Tool call already in history, commit result directly
        historyManager.addItem(result);
        return;
      }

      // Find the pair
      const pairIndex = pendingToolPairsRef.current.findIndex((p) => p.toolCallId === toolCallId);
      if (pairIndex === -1) return;

      const pair = pendingToolPairsRef.current[pairIndex];

      // Commit assistant message first if exists
      commitAssistantToHistory();

      // Commit all pairs before this one (maintains order)
      while (pendingToolPairsRef.current.length > 0 && pendingToolPairsRef.current[0] !== pair) {
        const prevPair = pendingToolPairsRef.current.shift()!;
        historyManager.addItem(prevPair.toolCall);
        if (prevPair.toolResult) {
          historyManager.addItem(prevPair.toolResult);
        }
        confirmedToolCallIdsRef.current.add(prevPair.toolCallId);
      }

      // Commit current pair
      historyManager.addItem(pair.toolCall);
      historyManager.addItem(result);
      pendingToolPairsRef.current.shift();
      confirmedToolCallIdsRef.current.add(toolCallId);
      triggerRerender();
    },
    [historyManager, commitAssistantToHistory, triggerRerender]
  );

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
    commitAssistantToHistory,
    commitAllPendingToHistory,
    commitToolPairToHistory,
    clearAll,
    triggerRerender,
  };
}
