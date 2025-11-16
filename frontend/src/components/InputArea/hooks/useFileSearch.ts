import { useState, useCallback } from 'react'
import {
  FileSearchResult,
  FileSearchResponse,
  FileSearchHookReturn
} from '../types'

/**
 * Hook for searching files in workspace via REST API.
 *
 * This hook provides file search functionality for @ mention autocomplete.
 * It calls the backend REST API endpoint `/api/files/search` to retrieve
 * matching files based on fuzzy search.
 *
 * Features:
 * - Async file search with loading state
 * - Error handling for failed requests
 * - Result caching for current search
 * - Clean API with TypeScript support
 *
 * Args:
 *     agentProfile?: string - Agent profile for workspace resolution (default: 'general')
 *     sessionId?: string - Session ID for workspace context
 *
 * Returns:
 *     FileSearchHookReturn: Search function, results, and state
 *
 * TypeScript Learning Points:
 * - Async API calls with proper error handling
 * - State management for loading and error states
 * - Type-safe response parsing
 * - Custom hook composition
 */

const useFileSearch = (
  agentProfile: string = 'general',
  sessionId?: string
): FileSearchHookReturn => {

  const [results, setResults] = useState<FileSearchResult[]>([])
  const [isSearching, setIsSearching] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  /**
   * Search files by query string
   */
  const searchFiles = useCallback(async (query: string): Promise<FileSearchResult[]> => {
    // Clear previous errors
    setError(null)

    // Don't search for empty queries
    if (!query || query.trim() === '') {
      setResults([])
      return []
    }

    setIsSearching(true)

    try {
      // Build query parameters
      const params = new URLSearchParams({
        query: query.trim(),
        agent_profile: agentProfile,
        limit: '50'
      })

      // Add session_id if provided
      if (sessionId) {
        params.append('session_id', sessionId)
      }

      // Call backend API
      const response = await fetch(`/api/files/search?${params.toString()}`)

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      // Parse response
      const data: FileSearchResponse = await response.json()

      if (data.status === 'error') {
        throw new Error(data.error || 'File search failed')
      }

      // Update results
      setResults(data.results)
      return data.results

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred'
      console.error('[useFileSearch] Search failed:', errorMessage)
      setError(errorMessage)
      setResults([])
      return []

    } finally {
      setIsSearching(false)
    }
  }, [agentProfile, sessionId])

  /**
   * Clear search results
   */
  const clearResults = useCallback(() => {
    setResults([])
    setError(null)
  }, [])

  return {
    searchFiles,
    results,
    isSearching,
    error,
    clearResults
  }
}

export default useFileSearch

/**
 * TypeScript Concepts Demonstrated:
 *
 * 1. **Async API Integration**:
 *    ```typescript
 *    const response = await fetch(`/api/files/search?${params}`)
 *    const data: FileSearchResponse = await response.json()
 *    ```
 *    Type-safe fetch with proper response parsing
 *
 * 2. **URLSearchParams Construction**:
 *    ```typescript
 *    const params = new URLSearchParams({ query, agent_profile, limit })
 *    if (sessionId) params.append('session_id', sessionId)
 *    ```
 *    Dynamic query parameter building
 *
 * 3. **Error Handling Patterns**:
 *    ```typescript
 *    try { ... } catch (err) {
 *      const errorMessage = err instanceof Error ? err.message : 'Unknown error'
 *      setError(errorMessage)
 *    } finally {
 *      setIsSearching(false)
 *    }
 *    ```
 *    Comprehensive error handling with type guards
 *
 * 4. **State Management**:
 *    ```typescript
 *    const [results, setResults] = useState<FileSearchResult[]>([])
 *    const [isSearching, setIsSearching] = useState<boolean>(false)
 *    ```
 *    Multiple related state variables for complex UI states
 *
 * 5. **useCallback Optimization**:
 *    ```typescript
 *    const searchFiles = useCallback(async (query) => { ... }, [deps])
 *    ```
 *    Memoized async function to prevent unnecessary re-renders
 *
 * Architecture Benefits:
 * - **Separation of Concerns**: API logic isolated from UI components
 * - **Reusability**: Can be used by multiple components
 * - **Type Safety**: Full TypeScript coverage prevents runtime errors
 * - **Error Resilience**: Proper error handling and recovery
 * - **Performance**: Optimized with useCallback
 *
 * Usage in Components:
 * ```typescript
 * const { searchFiles, results, isSearching, error } = useFileSearch('general')
 *
 * // Trigger search
 * await searchFiles('sample')
 *
 * // Display results
 * {results.map(file => (
 *   <div key={file.path}>{file.filename}</div>
 * ))}
 *
 * // Show loading state
 * {isSearching && <Spinner />}
 *
 * // Handle errors
 * {error && <ErrorMessage message={error} />}
 * ```
 */
