/**
 * useShellCommand Hook
 *
 * Provides shell command execution for ! prefix user commands.
 * Uses WebSocket communication for real-time execution and future Ctrl+B support.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { apiClient } from '@toyoura-nagisa/core';
import { useConnectionManager } from '../contexts/ConnectionContext.js';

/** Response data from shell execution */
export interface ShellExecuteData {
  stdout: string;
  stderr: string;
  exit_code: number;
  cwd: string;
  context: string;
  backgrounded?: boolean;
  process_id?: string;
}

/** Response data from cwd query (unwrapped from ApiResponse) */
export interface CwdData {
  cwd: string;
}

/** WebSocket result event data */
interface ShellResultEvent {
  stdout: string;
  stderr: string;
  exit_code: number;
  cwd: string;
  context: string;
  success: boolean;
  error_message?: string;
  backgrounded?: boolean;
  process_id?: string;
}

export interface UseShellCommandReturn {
  /** Execute a shell command */
  executeCommand: (command: string) => Promise<ShellExecuteData | null>;
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
  const connectionManager = useConnectionManager();
  const [isExecuting, setIsExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cwd, setCwd] = useState<string | null>(null);

  // Store pending resolve/reject for the current execution
  const pendingRef = useRef<{
    resolve: (data: ShellExecuteData | null) => void;
    reject: (error: Error) => void;
  } | null>(null);

  // Fetch initial cwd when session and profile are available (still uses REST for this one-time query)
  useEffect(() => {
    if (!sessionId) return;

    const fetchCwd = async () => {
      try {
        const response = await apiClient.get<CwdData>(
          `/api/shell/cwd?session_id=${encodeURIComponent(sessionId)}&agent_profile=${encodeURIComponent(agentProfile)}`
        );
        if (response.cwd) {
          setCwd(response.cwd);
        }
      } catch {
        // Silently ignore errors on initial fetch
      }
    };

    fetchCwd();
  }, [sessionId, agentProfile]);

  // Handle WebSocket result
  useEffect(() => {
    const handleResult = (event: ShellResultEvent) => {
      // Update cwd from response
      if (event.cwd) {
        setCwd(event.cwd);
      }

      // Resolve pending promise
      if (pendingRef.current) {
        if (event.success) {
          pendingRef.current.resolve({
            stdout: event.stdout,
            stderr: event.stderr,
            exit_code: event.exit_code,
            cwd: event.cwd,
            context: event.context,
            backgrounded: event.backgrounded,
            process_id: event.process_id,
          });
        } else {
          setError(event.error_message || 'Shell command failed');
          pendingRef.current.resolve(null);
        }
        pendingRef.current = null;
        setIsExecuting(false);
      }
    };

    connectionManager.on('user_shell_result', handleResult);

    return () => {
      connectionManager.off('user_shell_result', handleResult);
    };
  }, [connectionManager]);

  const executeCommand = useCallback(
    async (command: string): Promise<ShellExecuteData | null> => {
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
          type: 'USER_SHELL_EXECUTE',
          session_id: sessionId,
          command,
          agent_profile: agentProfile,
        });
      });
    },
    [sessionId, agentProfile, connectionManager]
  );

  return {
    executeCommand,
    isExecuting,
    error,
    cwd,
  };
}
