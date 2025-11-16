import { useState, useCallback, useMemo, useEffect } from 'react'
import useFileSearch from './useFileSearch'
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
  agentProfile: string = 'general',
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
   * Find @ character position before cursor
   */
  const findAtSignPosition = useCallback((text: string, cursor: number): number => {
    // Search backwards from cursor for @ character
    for (let i = cursor - 1; i >= 0; i--) {
      const char = text[i]

      // Found @ character
      if (char === '@') {
        return i
      }

      // Stop at whitespace or newline (@ mention boundary)
      if (char === ' ' || char === '\n' || char === '\t') {
        return -1
      }
    }

    return -1
  }, [])

  /**
   * Extract query string after @ character
   */
  const extractQuery = useCallback((
    text: string,
    cursor: number,
    atPosition: number
  ): string => {
    if (atPosition === -1) return ''

    // Extract text from @ to cursor
    const queryText = text.substring(atPosition + 1, cursor)

    return queryText
  }, [])

  /**
   * Parse current file mention from message and cursor position
   */
  const parseCurrentMention = useCallback((
    text: string,
    cursor: number
  ): FileMentionMatch | null => {

    const atPosition = findAtSignPosition(text, cursor)
    if (atPosition === -1) return null

    const query = extractQuery(text, cursor, atPosition)

    // No match if query is empty (just typed @)
    if (query === '') return null

    // Find exact match in results
    const exactMatch = results.find(file => file.path === query)
    if (!exactMatch) return null

    return {
      file: exactMatch,
      fullMatch: `@${query}`,
      position: {
        start: atPosition,
        end: cursor
      }
    }

  }, [findAtSignPosition, extractQuery, results])

  /**
   * Generate file suggestions based on search results
   */
  const generateSuggestions = useCallback((): FileMentionSuggestion[] => {

    if (!isActivated || results.length === 0) {
      return []
    }

    const atPosition = findAtSignPosition(message, cursorPosition)
    if (atPosition === -1) return []

    const query = extractQuery(message, cursorPosition, atPosition)

    // Convert search results to suggestions
    return results.map(file => ({
      file,
      relevanceScore: file.score,
      matchedText: query
    }))

  }, [isActivated, results, message, cursorPosition, findAtSignPosition, extractQuery])

  /**
   * Trigger file search when query changes
   */
  useEffect(() => {
    const atPosition = findAtSignPosition(message, cursorPosition)

    if (atPosition !== -1 && isActivated && !suppressSuggestions) {
      const query = extractQuery(message, cursorPosition, atPosition)

      // Search for files (debounced in practice via React rendering)
      if (query.length > 0) {
        searchFiles(query)
      } else {
        clearResults()
      }
    } else {
      clearResults()
    }
  }, [message, cursorPosition, isActivated, suppressSuggestions, findAtSignPosition, extractQuery, searchFiles, clearResults])

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
  }, [message, cursorPosition, isActivated, suppressSuggestions, prevCursorPosition, findAtSignPosition])

  /**
   * Auto-deactivation: deactivate when @ is removed
   */
  useEffect(() => {
    const atPosition = findAtSignPosition(message, cursorPosition)

    if (isActivated && atPosition === -1) {
      setIsActivated(false)
      clearResults()
    }
  }, [message, cursorPosition, isActivated, findAtSignPosition, clearResults])

  // Current mention context
  const context: FileMentionContext = useMemo(() => {
    const atPosition = findAtSignPosition(message, cursorPosition)
    const isTriggered = isActivated &&
                       atPosition !== -1 &&
                       cursorPosition > atPosition

    const query = atPosition !== -1 ? extractQuery(message, cursorPosition, atPosition) : ''
    const suggestions = generateSuggestions()

    return {
      currentText: message,
      cursorPosition,
      isTriggered,
      query,
      suggestions
    }
  }, [message, cursorPosition, isActivated, findAtSignPosition, extractQuery, generateSuggestions])

  // Active file mention match
  const activeMention = useMemo(() => {
    if (!context.isTriggered) return null
    return parseCurrentMention(message, cursorPosition)
  }, [context.isTriggered, message, cursorPosition, parseCurrentMention])

  // Select suggestion handler
  const selectSuggestion = useCallback((suggestion: FileMentionSuggestion) => {
    // This will be implemented when integrating with message input
    // The parent component should handle text replacement
    console.log('Selecting file suggestion:', suggestion.file.path)
  }, [])

  // Clear active mention - ESC handling
  const clearMention = useCallback(() => {
    if (isActivated) {
      setIsActivated(false)
      setSuppressSuggestions(true) // Prevent re-activation until re-armed
      clearResults()
      console.log('File mention suggestions deactivated via ESC')
    }
  }, [isActivated, clearResults])

  return {
    context,
    activeMention,
    suggestions: context.suggestions,
    isMentionActive: context.isTriggered && context.suggestions.length > 0,
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
