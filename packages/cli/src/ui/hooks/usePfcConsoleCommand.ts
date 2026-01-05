/**
 * usePfcConsoleCommand Hook
 *
 * Provides PFC Python command execution for > prefix user commands.
 * Calls the backend REST API endpoint /api/pfc/console/execute.
 */

import { useState, useCallback, useEffect } from 'react';
import { apiClient } from '@toyoura-nagisa/core';

export interface PfcConsoleExecuteRequest {
  code: string;
  session_id: string;
  agent_profile: string;
  timeout_ms?: number;
}

/** Response data from PFC execution (unwrapped from ApiResponse) */
export interface PfcConsoleExecuteData {
  task_id: string | null;
  script_name: string | null;
  script_path: string | null;
  code_preview: string | null;
  output: string | null;
  error: string | null;
  result: unknown;
  elapsed_time: number | null;
  context: string;
  connected: boolean;
}

/** Response data from connection status (unwrapped from ApiResponse) */
export interface PfcConsoleStatusData {
  connected: boolean;
}

export interface UsePfcConsoleCommandReturn {
  /** Execute PFC Python code */
  executeCode: (code: string) => Promise<PfcConsoleExecuteData | null>;
  /** Whether execution is in progress */
  isExecuting: boolean;
  /** Last error message if any */
  error: string | null;
  /** Whether PFC server is connected */
  isConnected: boolean;
  /** Check PFC server connection status */
  checkConnection: () => Promise<boolean>;
}

export function usePfcConsoleCommand(
  sessionId: string | null,
  agentProfile: string = 'pfc_expert'
): UsePfcConsoleCommandReturn {
  const [isExecuting, setIsExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  // Check connection on mount and when session/profile changes
  const checkConnection = useCallback(async (): Promise<boolean> => {
    try {
      const response = await apiClient.get<PfcConsoleStatusData>(
        '/api/pfc/console/status'
      );
      setIsConnected(response.connected);
      return response.connected;
    } catch {
      setIsConnected(false);
      return false;
    }
  }, []);

  // Check connection status on mount
  useEffect(() => {
    if (!sessionId) return;
    checkConnection();
  }, [sessionId, checkConnection]);

  const executeCode = useCallback(
    async (code: string): Promise<PfcConsoleExecuteData | null> => {
      if (!sessionId) {
        setError('No active session');
        return null;
      }

      setError(null);
      setIsExecuting(true);

      try {
        const response = await apiClient.post<PfcConsoleExecuteData>(
          '/api/pfc/console/execute',
          {
            code,
            session_id: sessionId,
            agent_profile: agentProfile,
          } as PfcConsoleExecuteRequest
        );

        // Update connection status from response
        setIsConnected(response.connected);

        return response;
      } catch (err: unknown) {
        // Extract error message
        const errorMessage = err instanceof Error ? err.message : 'PFC command failed';
        setError(errorMessage);
        setIsConnected(false);
        return null;
      } finally {
        setIsExecuting(false);
      }
    },
    [sessionId, agentProfile]
  );

  return {
    executeCode,
    isExecuting,
    error,
    isConnected,
    checkConnection,
  };
}
