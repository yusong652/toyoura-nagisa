/**
 * useShellCommand Hook
 *
 * Provides shell command execution for ! prefix user commands.
 * Calls the backend REST API endpoint /api/shell/execute.
 */

import { useState, useCallback, useEffect } from 'react';
import { apiClient } from '@toyoura-nagisa/core';

export interface ShellExecuteRequest {
  command: string;
  session_id: string;
  agent_profile: string;
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

export interface CwdResponse {
  success: boolean;
  cwd: string;
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

export function useShellCommand(
  sessionId: string | null,
  agentProfile: string = 'general'
): UseShellCommandReturn {
  const [isExecuting, setIsExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cwd, setCwd] = useState<string | null>(null);

  // Fetch initial cwd when session and profile are available
  useEffect(() => {
    if (!sessionId) return;

    const fetchCwd = async () => {
      try {
        const response = await apiClient.get<CwdResponse>(
          `/api/shell/cwd/${sessionId}?agent_profile=${encodeURIComponent(agentProfile)}`
        );
        if (response.success && response.cwd) {
          setCwd(response.cwd);
        }
      } catch {
        // Silently ignore errors on initial fetch
      }
    };

    fetchCwd();
  }, [sessionId, agentProfile]);

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
            agent_profile: agentProfile,
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
    [sessionId, agentProfile]
  );

  return {
    executeCommand,
    isExecuting,
    error,
    cwd,
  };
}
