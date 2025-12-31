/**
 * useFileSearch Hook
 *
 * Provides file search functionality for @ mention autocomplete.
 * Calls the backend REST API endpoint /api/files/search.
 */

import { useState, useCallback, useRef } from 'react';
import { apiClient } from '@toyoura-nagisa/core';

export interface FileSearchResult {
  path: string;
  filename: string;
  score: number;
}

/** Response data from file search (unwrapped from ApiResponse) */
interface FileSearchData {
  query: string;
  workspace: string;
  results: FileSearchResult[];
  total: number;
}

export interface UseFileSearchReturn {
  /** Search files by query */
  searchFiles: (query: string) => Promise<FileSearchResult[]>;
  /** Current search results */
  results: FileSearchResult[];
  /** Whether search is in progress */
  isSearching: boolean;
  /** Error message if any */
  error: string | null;
  /** Clear search results */
  clearResults: () => void;
}

export function useFileSearch(
  agentProfile: string = 'general',
  sessionId?: string
): UseFileSearchReturn {
  const [results, setResults] = useState<FileSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Debounce ref to cancel pending searches
  const searchTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const searchFiles = useCallback(
    async (query: string): Promise<FileSearchResult[]> => {
      // Clear previous errors
      setError(null);

      // Cancel pending search
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
        searchTimeoutRef.current = null;
      }

      // Don't search for empty queries
      if (!query || query.trim() === '') {
        setResults([]);
        return [];
      }

      setIsSearching(true);

      try {
        // Build query parameters
        const params = new URLSearchParams({
          query: query.trim(),
          agent_profile: agentProfile,
          limit: '20',
        });

        // Add session_id if provided
        if (sessionId) {
          params.append('session_id', sessionId);
        }

        // Call backend API - response is unwrapped to FileSearchData
        const data = await apiClient.get<FileSearchData>(
          `/api/files/search?${params.toString()}`
        );

        // Update results
        setResults(data.results);
        return data.results;
      } catch (err: unknown) {
        const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
        setError(errorMessage);
        setResults([]);
        return [];
      } finally {
        setIsSearching(false);
      }
    },
    [agentProfile, sessionId]
  );

  const clearResults = useCallback(() => {
    setResults([]);
    setError(null);
  }, []);

  return {
    searchFiles,
    results,
    isSearching,
    error,
    clearResults,
  };
}
