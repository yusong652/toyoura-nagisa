import { useState, useCallback, useMemo, useEffect } from 'react'
import useFileSearch from './useFileSearch'
import {
  findAtSignPosition,
  extractQuery,
  parseCurrentMention as parseCurrentMentionCore
} from '@toyoura-nagisa/core/utils'
import {
  FileMentionMatch,
  FileMentionSuggestion,
  FileMentionContext,
  FileMentionDetectionHookReturn
} from '../types'

/**
 * Hook for file mention detection and suggestion generation.
 *
 * This hook provides comprehensive @ file mention detection functionality including:
 * - Real-time detection of '@' trigger character
 * - Query extraction with cursor position tracking
 * - Intelligent file search with debouncing
 * - File suggestion management
 * - Selection and autocomplete handling
 *
 * The hook integrates seamlessly with the InputArea's message input system
 * while maintaining clean separation of concerns.
 *
 * Architecture Benefits:
 * - Real-time file detection without performance impact
 * - Type-safe file handling with full TypeScript support
 * - Intelligent suggestion ranking based on relevance
 * - Proper cursor position management for inline mentions
 *
 * Args:
 *     message: string - Current input message text
 *     cursorPosition: number - Current textarea cursor position
 *     agentProfile?: string - Agent profile for workspace resolution
 *     sessionId?: string - Session ID for workspace context
 *
 * Returns:
 *     FileMentionDetectionHookReturn: Complete file mention detection state and handlers
 *
 * TypeScript Learning Points:
 * - Advanced string parsing with regex patterns
 * - Context object composition for complex state
 * - Real-time search with debouncing
 * - Cursor position management in text inputs
 */

const useFileMentionDetection = (
  message: string,
  cursorPosition: number,
  agentProfile: string = 'pfc',
  sessionId?: string
): FileMentionDetectionHookReturn => {

  // File search hook
  const { searchFiles, results, isSearching, clearResults } = useFileSearch(agentProfile, sessionId)

  // Activation state management
  const [isActivated, setIsActivated] = useState<boolean>(false)
  // Suppress suggestions after ESC until user moves cursor to just-after @
  const [suppressSuggestions, setSuppressSuggestions] = useState<boolean>(false)
  const [prevCursorPosition, setPrevCursorPosition] = useState<number>(cursorPosition)

  /**
   * Parse current file mention from message and cursor position
   * Adapts core parsing logic to include file lookup from results
   */
  const parseCurrentMention = useCallback((
    text: string,
    cursor: number
  ): FileMentionMatch | null => {

    const coreMention = parseCurrentMentionCore(text, cursor)
    if (!coreMention) return null

    // Find exact match in results
    const exactMatch = results.find(file => file.path === coreMention.query)
    if (!exactMatch) return null

    return {
      file: exactMatch,
      fullMatch: `@${coreMention.query}`,
      position: {
        start: coreMention.atPosition,
        end: cursor
      }
    }

  }, [results])

  /**
   * Generate file suggestions based on search results
   */
  const generateSuggestions = useCallback((): FileMentionSuggestion[] => {

    if (!isActivated) {
      return []
    }

    const atPosition = findAtSignPosition(message, cursorPosition)
    if (atPosition === -1) return []

    const query = extractQuery(message, cursorPosition, atPosition)

    // Return empty array if no results yet (but show loading in UI)
    if (results.length === 0) {
      return []
    }

    // Convert search results to suggestions
    return results.map(file => ({
      file,
      relevanceScore: file.score,
      matchedText: query
    }))

  }, [isActivated, results, message, cursorPosition])

  /**
   * Trigger file search when query changes
   */
  useEffect(() => {
    const atPosition = findAtSignPosition(message, cursorPosition)

    if (atPosition !== -1 && isActivated && !suppressSuggestions) {
      const query = extractQuery(message, cursorPosition, atPosition)

      // Only search when user has typed at least one character after @
      // This prevents showing empty results when user just types @
      if (query.length > 0) {
        searchFiles(query)
      } else {
        // Clear results when query is empty (just typed @)
        // User needs to type at least one character to see suggestions
        clearResults()
      }
    } else {
      clearResults()
    }
  }, [message, cursorPosition, isActivated, suppressSuggestions, searchFiles, clearResults])

  /**
   * Auto-activation logic: activate when user types @ followed by characters
   */
  useEffect(() => {
    const atPosition = findAtSignPosition(message, cursorPosition)

    // Check if caret moved to just-after @ (re-arm condition)
    const movedToAfterAt = atPosition !== -1 && cursorPosition === atPosition + 1 && prevCursorPosition !== atPosition + 1

    // Clear suppression when:
    // - user moved caret to just-after @, or
    // - @ is no longer present before cursor
    if (suppressSuggestions) {
      if (movedToAfterAt || atPosition === -1) {
        setSuppressSuggestions(false)
      }
    }

    const shouldAutoActivate =
      atPosition !== -1 &&
      cursorPosition > atPosition &&
      !suppressSuggestions

    if (shouldAutoActivate && !isActivated) {
      setIsActivated(true)
    }

    // Track previous cursor for movement detection
    if (prevCursorPosition !== cursorPosition) {
      setPrevCursorPosition(cursorPosition)
    }
  }, [message, cursorPosition, isActivated, suppressSuggestions, prevCursorPosition])

  /**
   * Auto-deactivation: deactivate when @ is removed
   */
  useEffect(() => {
    const atPosition = findAtSignPosition(message, cursorPosition)

    if (isActivated && atPosition === -1) {
      setIsActivated(false)
      clearResults()
    }
  }, [message, cursorPosition, isActivated, clearResults])

  // Current mention context
  const context: FileMentionContext = useMemo(() => {
    const atPosition = findAtSignPosition(message, cursorPosition)
    const isTriggered = isActivated &&
                       atPosition !== -1 &&
                       cursorPosition > atPosition &&
                       !suppressSuggestions

    const query = atPosition !== -1 ? extractQuery(message, cursorPosition, atPosition) : ''
    const suggestions = generateSuggestions()

    return {
      currentText: message,
      cursorPosition,
      isTriggered,
      query,
      suggestions
    }
  }, [message, cursorPosition, isActivated, suppressSuggestions, generateSuggestions])

  // Active file mention match
  const activeMention = useMemo(() => {
    if (!context.isTriggered) return null
    return parseCurrentMention(message, cursorPosition)
  }, [context.isTriggered, message, cursorPosition, parseCurrentMention])

  // Select suggestion handler
  const selectSuggestion = useCallback((_suggestion: FileMentionSuggestion) => {
    // The parent component handles text replacement
  }, [])

  // Clear active mention - ESC handling
  const clearMention = useCallback(() => {
    if (isActivated) {
      setIsActivated(false)
      setSuppressSuggestions(true) // Prevent re-activation until re-armed
      clearResults()
    }
  }, [isActivated, clearResults])

  // Show dropdown when:
  // 1. User is actively typing after @ (isTriggered)
  // 2. AND (has results OR currently searching OR query exists but no results yet)
  const hasQuery = context.query.length > 0
  const isMentionActive = context.isTriggered && (context.suggestions.length > 0 || isSearching || hasQuery)

  return {
    context,
    activeMention,
    suggestions: context.suggestions,
    isMentionActive,
    selectSuggestion,
    clearMention,
    isSearching
  }
}

export default useFileMentionDetection

/**
 * TypeScript Concepts Demonstrated:
 *
 * 1. **Advanced String Parsing**:
 *    ```typescript
 *    for (let i = cursor - 1; i >= 0; i--) {
 *      if (text[i] === '@') return i
 *      if (text[i] === ' ') return -1  // Boundary
 *    }
 *    ```
 *    Manual character-by-character parsing with boundary detection
 *
 * 2. **Context Object Composition**:
 *    ```typescript
 *    const context: FileMentionContext = useMemo(() => ({
 *      currentText: message,
 *      query: extractQuery(...),
 *      suggestions: generateSuggestions()
 *    }), [dependencies])
 *    ```
 *    Computed context object combining multiple data sources
 *
 * 3. **Cursor Position Management**:
 *    ```typescript
 *    const atPosition = findAtSignPosition(text, cursor)
 *    const query = text.substring(atPosition + 1, cursor)
 *    ```
 *    Precise text selection and cursor position tracking
 *
 * 4. **Async Search Integration**:
 *    ```typescript
 *    useEffect(() => {
 *      if (query.length > 0) {
 *        searchFiles(query)  // Async API call
 *      }
 *    }, [query])
 *    ```
 *    Proper async search triggering with dependencies
 *
 * Architecture Benefits:
 * - **Real-time Processing**: Efficient parsing without blocking UI
 * - **Type Safety**: Full TypeScript coverage prevents runtime errors
 * - **Performance**: Optimized with useMemo and useCallback
 * - **Integration Ready**: Clean interface for InputArea integration
 *
 * Usage in InputArea:
 * ```typescript
 * const {
 *   isMentionActive,
 *   suggestions,
 *   selectSuggestion,
 *   clearMention
 * } = useFileMentionDetection(message, cursorPosition, agentProfile, sessionId)
 *
 * // Show suggestions dropdown when mention is active
 * {isMentionActive && suggestions.length > 0 && (
 *   <FileMentionSuggestions
 *     suggestions={suggestions}
 *     onSelect={selectSuggestion}
 *   />
 * )}
 *
 * // Handle ESC key
 * if (e.key === 'Escape' && isMentionActive) {
 *   clearMention()
 * }
 * ```
 */
