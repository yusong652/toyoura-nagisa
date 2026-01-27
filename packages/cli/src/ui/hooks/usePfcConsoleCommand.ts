/**
 * usePfcConsoleCommand Hook
 *
 * Provides PFC Python command execution for > prefix user commands.
 * Uses WebSocket communication for real-time execution with Ctrl+B support.
 *
 * Aligned with useShellCommand pattern for consistency.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { apiClient } from '@toyoura-nagisa/core';
import { useConnectionManager } from '../contexts/ConnectionContext.js';

/** Response data from PFC execution */
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
  backgrounded?: boolean;
}

/** Response data from connection status (unwrapped from ApiResponse) */
export interface PfcConsoleStatusData {
  connected: boolean;
}

/** WebSocket result event data */
interface PfcConsoleResultEvent {
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
  success: boolean;
  error_message?: string;
  backgrounded?: boolean;
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
  sessionId: string | null
): UsePfcConsoleCommandReturn {
  const connectionManager = useConnectionManager();
  const [isExecuting, setIsExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  // Store pending resolve/reject for the current execution
  const pendingRef = useRef<{
    resolve: (data: PfcConsoleExecuteData | null) => void;
    reject: (error: Error) => void;
  } | null>(null);

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

  // Handle WebSocket result
  useEffect(() => {
    const handleResult = (event: PfcConsoleResultEvent) => {
      // Update connection status from response
      setIsConnected(event.connected);

      // Resolve pending promise
      if (pendingRef.current) {
        // We resolve with data regardless of success flag, so the UI can display errors
        // effectively using the MessageType.PFC_CONSOLE_RESULT type
        pendingRef.current.resolve({
          task_id: event.task_id,
          script_name: event.script_name,
          script_path: event.script_path,
          code_preview: event.code_preview,
          output: event.output,
          // Use error_message (system error) or error (execution error)
          error: event.error_message || event.error || (event.success ? null : 'PFC command failed'),
          result: event.result,
          elapsed_time: event.elapsed_time,
          context: event.context,
          connected: event.connected,
          backgrounded: event.backgrounded,
        });

        if (!event.success) {
          setError(event.error_message || event.error || 'PFC command failed');
        }

        pendingRef.current = null;
        setIsExecuting(false);
      }
    };

    connectionManager.on('user_pfc_console_result', handleResult);

    return () => {
      connectionManager.off('user_pfc_console_result', handleResult);
    };
  }, [connectionManager]);

  const executeCode = useCallback(
    async (code: string): Promise<PfcConsoleExecuteData | null> => {
      if (!sessionId) {
        setError('No active session');
        return null;
      }

      setError(null);
      setIsExecuting(true);

      return new Promise((resolve, reject) => {
        // Store resolve/reject for when we receive the result
        pendingRef.current = { resolve, reject };

        // Send command via WebSocket
        connectionManager.send({
          type: 'USER_PFC_CONSOLE_EXECUTE',
          session_id: sessionId,
          code,
        });
      });
    },
    [sessionId, connectionManager]
  );

  return {
    executeCode,
    isExecuting,
    error,
    isConnected,
    checkConnection,
  };
}
