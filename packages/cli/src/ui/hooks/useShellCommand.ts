/**
 * useShellCommand Hook
 *
 * Provides shell command execution for ! prefix user commands.
 * Calls the backend REST API endpoint /api/shell/execute.
 */

import { useState, useCallback } from 'react';
import { apiClient } from '@toyoura-nagisa/core';

export interface ShellExecuteRequest {
  command: string;
  session_id: string;
  timeout_ms?: number;
}

export interface ShellExecuteResponse {
  success: boolean;
  stdout: string;
  stderr: string;
  exit_code: number;
  cwd: string;
  context: string;
  error?: string;
}

export interface UseShellCommandReturn {
  /** Execute a shell command */
  executeCommand: (command: string) => Promise<ShellExecuteResponse | null>;
  /** Whether execution is in progress */
  isExecuting: boolean;
  /** Last error message if any */
  error: string | null;
  /** Current working directory */
  cwd: string | null;
}

export function useShellCommand(sessionId: string | null): UseShellCommandReturn {
  const [isExecuting, setIsExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cwd, setCwd] = useState<string | null>(null);

  const executeCommand = useCallback(
    async (command: string): Promise<ShellExecuteResponse | null> => {
      if (!sessionId) {
        setError('No active session');
        return null;
      }

      setError(null);
      setIsExecuting(true);

      try {
        const response = await apiClient.post<ShellExecuteResponse>(
          '/api/shell/execute',
          {
            command,
            session_id: sessionId,
          } as ShellExecuteRequest
        );

        // Update cwd from response
        if (response.cwd) {
          setCwd(response.cwd);
        }

        return response;
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Shell command failed';
        setError(errorMessage);
        return null;
      } finally {
        setIsExecuting(false);
      }
    },
    [sessionId]
  );

  return {
    executeCommand,
    isExecuting,
    error,
    cwd,
  };
}
