/**
 * History Manager Hook
 * Reference: Gemini CLI ui/hooks/useHistoryManager.ts
 *
 * Manages chat history state with add, update, and clear operations
 */

import { useState, useRef, useCallback, useMemo } from 'react';
import type { HistoryItem, HistoryItemWithoutId } from '../types.js';

// Type for the updater function - uses any for flexibility
type HistoryItemUpdater = (prevItem: HistoryItem) => Record<string, any>;

export interface UseHistoryManagerReturn {
  history: HistoryItem[];
  addItem: (itemData: HistoryItemWithoutId, timestamp?: number) => string;
  updateItem: (id: string, updates: Record<string, any> | HistoryItemUpdater) => void;
  clearItems: () => void;
  loadHistory: (newHistory: HistoryItem[]) => void;
}

/**
 * Custom hook to manage chat history state
 */
export function useHistoryManager(): UseHistoryManagerReturn {
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const messageIdCounterRef = useRef(0);

  // Generate unique ID
  const generateId = useCallback((): string => {
    messageIdCounterRef.current += 1;
    return `msg-${Date.now()}-${messageIdCounterRef.current}`;
  }, []);

  // Load existing history
  const loadHistory = useCallback((newHistory: HistoryItem[]) => {
    setHistory(newHistory);
    // Update counter based on loaded history
    if (newHistory.length > 0) {
      messageIdCounterRef.current = newHistory.length;
    }
  }, []);

  // Add new item to history
  const addItem = useCallback((
    itemData: HistoryItemWithoutId,
    timestamp?: number,
  ): string => {
    const id = generateId();
    const newItem: HistoryItem = {
      ...itemData,
      id,
      timestamp: timestamp || Date.now(),
    } as HistoryItem;

    setHistory((prevHistory) => {
      // Prevent duplicate consecutive user messages
      if (prevHistory.length > 0) {
        const lastItem = prevHistory[prevHistory.length - 1];
        if (
          lastItem.type === 'user' &&
          newItem.type === 'user' &&
          'text' in lastItem &&
          'text' in newItem &&
          lastItem.text === newItem.text
        ) {
          return prevHistory;
        }
      }
      return [...prevHistory, newItem];
    });

    return id;
  }, [generateId]);

  // Update existing item
  const updateItem = useCallback((
    id: string,
    updates: Record<string, any> | HistoryItemUpdater,
  ) => {
    setHistory((prevHistory) =>
      prevHistory.map((item) => {
        if (item.id === id) {
          const newUpdates = typeof updates === 'function'
            ? updates(item)
            : updates;
          return { ...item, ...newUpdates } as HistoryItem;
        }
        return item;
      }),
    );
  }, []);

  // Clear all history
  const clearItems = useCallback(() => {
    setHistory([]);
    messageIdCounterRef.current = 0;
  }, []);

  return useMemo(() => ({
    history,
    addItem,
    updateItem,
    clearItems,
    loadHistory,
  }), [history, addItem, updateItem, clearItems, loadHistory]);
}
