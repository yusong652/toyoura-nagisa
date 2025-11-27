/**
 * useSessionManager Hook
 *
 * Manages session-related API calls and state.
 * Provides methods for creating, restoring, and deleting sessions.
 */

import { useState, useCallback } from 'react';
import { sessionService, type ChatSession } from '@aiNagisa/core';
import type { SelectOption } from '../components/SelectDialog.js';

export interface UseSessionManagerReturn {
  /** List of available sessions */
  sessions: ChatSession[];
  /** Whether sessions are loading */
  isLoading: boolean;
  /** Error message if any */
  error: string | null;
  /** Load all sessions from API */
  loadSessions: () => Promise<void>;
  /** Create a new session */
  createSession: (name?: string) => Promise<string | null>;
  /** Switch to a session */
  restoreSession: (sessionId: string) => Promise<boolean>;
  /** Delete a session */
  deleteSession: (sessionId: string) => Promise<boolean>;
  /** Convert sessions to SelectDialog options */
  getSessionOptions: (currentSessionId: string | null, excludeCurrent?: boolean) => SelectOption<string>[];
}

export function useSessionManager(): UseSessionManagerReturn {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadSessions = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await sessionService.getSessions();
      setSessions(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load sessions');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const createSession = useCallback(async (name?: string): Promise<string | null> => {
    setError(null);
    try {
      const result = await sessionService.createSession(name);
      return result.session_id;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create session');
      return null;
    }
  }, []);

  const restoreSession = useCallback(async (sessionId: string): Promise<boolean> => {
    setError(null);
    try {
      await sessionService.switchSession(sessionId);
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to restore session');
      return false;
    }
  }, []);

  const deleteSession = useCallback(async (sessionId: string): Promise<boolean> => {
    setError(null);
    try {
      await sessionService.deleteSession(sessionId);
      // Remove from local state
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete session');
      return false;
    }
  }, []);

  const getSessionOptions = useCallback(
    (currentSessionId: string | null, excludeCurrent = false): SelectOption<string>[] => {
      let filteredSessions = sessions;
      if (excludeCurrent && currentSessionId) {
        filteredSessions = sessions.filter((s) => s.id !== currentSessionId);
      }

      return filteredSessions.map((session) => {
        const isCurrent = session.id === currentSessionId;
        const dateStr = session.updated_at
          ? new Date(session.updated_at).toLocaleDateString()
          : '';

        return {
          key: session.id,
          value: session.id,
          label: `${session.name || 'Unnamed'}${isCurrent ? ' (current)' : ''}`,
          description: dateStr,
          // Mark current session as disabled for visual styling (grayed out)
          // Navigation still works, but Enter is ignored in the handler
          disabled: isCurrent && !excludeCurrent,
        };
      });
    },
    [sessions]
  );

  return {
    sessions,
    isLoading,
    error,
    loadSessions,
    createSession,
    restoreSession,
    deleteSession,
    getSessionOptions,
  };
}
