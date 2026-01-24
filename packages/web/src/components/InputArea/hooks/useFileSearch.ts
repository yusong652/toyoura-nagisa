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
 * Updated for 2025 Standard ApiResponse format.
 */

const useFileSearch = (
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

      // Parse response (2025 Standard ApiResponse format)
      const apiResponse: FileSearchResponse = await response.json()

      // Check for business logic errors
      if (!apiResponse.success) {
        throw new Error(apiResponse.message || 'File search failed')
      }

      // Extract results from data
      const searchResults = apiResponse.data?.results || []

      // Update results
      setResults(searchResults)
      return searchResults

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred'
      console.error('[useFileSearch] Search failed:', errorMessage)
      setError(errorMessage)
      setResults([])
      return []

    } finally {
      setIsSearching(false)
    }
  }, [sessionId])

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
