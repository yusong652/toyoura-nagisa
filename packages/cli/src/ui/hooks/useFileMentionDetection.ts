/**
 * useFileMentionDetection Hook
 *
 * Provides file mention detection and suggestion generation for CLI.
 * Detects @ trigger character and manages file search suggestions.
 */

import { useState, useCallback, useMemo, useEffect } from 'react';
import {
  findAtSignPosition,
  extractQuery,
} from '@toyoura-nagisa/core/utils';
import { useFileSearch, type FileSearchResult } from './useFileSearch.js';

export interface FileMentionSuggestion {
  file: FileSearchResult;
  relevanceScore: number;
  matchedText: string;
}

export interface FileMentionContext {
  currentText: string;
  cursorPosition: number;
  isTriggered: boolean;
  query: string;
  atPosition: number;
  suggestions: FileMentionSuggestion[];
}

// Maximum suggestions to show at once
const MAX_SUGGESTIONS_TO_SHOW = 8;

export interface UseFileMentionDetectionReturn {
  /** Current mention context */
  context: FileMentionContext;
  /** Current suggestions */
  suggestions: FileMentionSuggestion[];
  /** Whether mention dropdown should be shown */
  isMentionActive: boolean;
  /** Whether search is in progress */
  isSearching: boolean;
  /** Clear/dismiss mention suggestions (ESC handler) */
  clearMention: () => void;
  /** Selected suggestion index */
  selectedIndex: number;
  /** Scroll offset for visible window */
  scrollOffset: number;
  /** Move selection up */
  selectPrevious: () => void;
  /** Move selection down */
  selectNext: () => void;
  /** Get currently selected suggestion */
  getSelectedSuggestion: () => FileMentionSuggestion | null;
}

export function useFileMentionDetection(
  message: string,
  cursorPosition: number,
  sessionId?: string
): UseFileMentionDetectionReturn {
  // File search hook
  const { searchFiles, results, isSearching, clearResults } = useFileSearch(
    sessionId
  );

  // Activation state
  const [isActivated, setIsActivated] = useState(false);
  const [suppressSuggestions, setSuppressSuggestions] = useState(false);
  const [prevCursorPosition, setPrevCursorPosition] = useState(cursorPosition);

  // Selection state for keyboard navigation
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [scrollOffset, setScrollOffset] = useState(0);

  // Generate suggestions from search results
  const generateSuggestions = useCallback((): FileMentionSuggestion[] => {
    if (!isActivated || results.length === 0) {
      return [];
    }

    const atPosition = findAtSignPosition(message, cursorPosition);
    if (atPosition === -1) return [];

    const query = extractQuery(message, cursorPosition, atPosition);

    return results.map((file) => ({
      file,
      relevanceScore: file.score,
      matchedText: query,
    }));
  }, [isActivated, results, message, cursorPosition]);

  // Trigger file search when query changes
  useEffect(() => {
    const atPosition = findAtSignPosition(message, cursorPosition);

    if (atPosition !== -1 && isActivated && !suppressSuggestions) {
      const query = extractQuery(message, cursorPosition, atPosition);

      if (query.length > 0) {
        searchFiles(query);
      } else {
        clearResults();
      }
    } else {
      clearResults();
    }
  }, [message, cursorPosition, isActivated, suppressSuggestions, searchFiles, clearResults]);

  // Auto-activation logic
  useEffect(() => {
    const atPosition = findAtSignPosition(message, cursorPosition);

    // Check if cursor moved to just-after @
    const movedToAfterAt =
      atPosition !== -1 &&
      cursorPosition === atPosition + 1 &&
      prevCursorPosition !== atPosition + 1;

    // Clear suppression when re-armed
    if (suppressSuggestions) {
      if (movedToAfterAt || atPosition === -1) {
        setSuppressSuggestions(false);
      }
    }

    const shouldAutoActivate =
      atPosition !== -1 && cursorPosition > atPosition && !suppressSuggestions;

    if (shouldAutoActivate && !isActivated) {
      setIsActivated(true);
      setSelectedIndex(0);
    }

    if (prevCursorPosition !== cursorPosition) {
      setPrevCursorPosition(cursorPosition);
    }
  }, [message, cursorPosition, isActivated, suppressSuggestions, prevCursorPosition]);

  // Auto-deactivation when @ is removed
  useEffect(() => {
    const atPosition = findAtSignPosition(message, cursorPosition);

    if (isActivated && atPosition === -1) {
      setIsActivated(false);
      clearResults();
      setSelectedIndex(0);
    }
  }, [message, cursorPosition, isActivated, clearResults]);

  // Reset selection and scroll when results change
  useEffect(() => {
    setSelectedIndex(0);
    setScrollOffset(0);
  }, [results]);

  // Build context
  const context: FileMentionContext = useMemo(() => {
    const atPosition = findAtSignPosition(message, cursorPosition);
    const isTriggered =
      isActivated && atPosition !== -1 && cursorPosition > atPosition && !suppressSuggestions;

    const query = atPosition !== -1 ? extractQuery(message, cursorPosition, atPosition) : '';
    const suggestions = generateSuggestions();

    return {
      currentText: message,
      cursorPosition,
      isTriggered,
      query,
      atPosition,
      suggestions,
    };
  }, [message, cursorPosition, isActivated, suppressSuggestions, generateSuggestions]);

  // Clear mention (ESC handler)
  const clearMention = useCallback(() => {
    if (isActivated) {
      setIsActivated(false);
      setSuppressSuggestions(true);
      clearResults();
      setSelectedIndex(0);
      setScrollOffset(0);
    }
  }, [isActivated, clearResults]);

  // Selection navigation with scroll adjustment
  const selectPrevious = useCallback(() => {
    const suggestions = generateSuggestions();
    if (suggestions.length === 0) return;

    setSelectedIndex((prev) => {
      const newIndex = prev <= 0 ? suggestions.length - 1 : prev - 1;
      // Adjust scroll
      setScrollOffset((prevScroll) => {
        if (newIndex === suggestions.length - 1) {
          // Wrapped to end - scroll to show last items
          return Math.max(0, suggestions.length - MAX_SUGGESTIONS_TO_SHOW);
        }
        if (newIndex < prevScroll) {
          // Selection moved above visible window
          return newIndex;
        }
        return prevScroll;
      });
      return newIndex;
    });
  }, [generateSuggestions]);

  const selectNext = useCallback(() => {
    const suggestions = generateSuggestions();
    if (suggestions.length === 0) return;

    setSelectedIndex((prev) => {
      const newIndex = prev >= suggestions.length - 1 ? 0 : prev + 1;
      // Adjust scroll
      setScrollOffset((prevScroll) => {
        if (newIndex === 0) {
          // Wrapped to beginning
          return 0;
        }
        const visibleEnd = prevScroll + MAX_SUGGESTIONS_TO_SHOW;
        if (newIndex >= visibleEnd) {
          // Selection moved below visible window
          return newIndex - MAX_SUGGESTIONS_TO_SHOW + 1;
        }
        return prevScroll;
      });
      return newIndex;
    });
  }, [generateSuggestions]);

  const getSelectedSuggestion = useCallback((): FileMentionSuggestion | null => {
    const suggestions = context.suggestions;
    if (suggestions.length === 0) return null;
    const idx = Math.min(selectedIndex, suggestions.length - 1);
    return suggestions[idx] || null;
  }, [context.suggestions, selectedIndex]);

  // Show dropdown when triggered and has query
  const hasQuery = context.query.length > 0;
  const isMentionActive =
    context.isTriggered && (context.suggestions.length > 0 || isSearching || hasQuery);

  return {
    context,
    suggestions: context.suggestions,
    isMentionActive,
    isSearching,
    clearMention,
    selectedIndex,
    scrollOffset,
    selectPrevious,
    selectNext,
    getSelectedSuggestion,
  };
}
