/**
 * useConnectionState Hook
 *
 * Manages WebSocket connection state and status updates.
 * Subscribes to ConnectionManager events and maps them to UI-friendly status.
 */

import { useState, useEffect } from 'react';
import type { ConnectionManager } from '@toyoura-nagisa/core';
import type { ConnectionStatus } from '../types.js';

interface UseConnectionStateParams {
  connectionManager: ConnectionManager;
}

interface UseConnectionStateReturn {
  connectionStatus: ConnectionStatus;
}

/**
 * Maps internal connection states to UI-friendly status
 */
const CONNECTION_STATUS_MAP: Record<string, ConnectionStatus> = {
  'disconnected': 'disconnected',
  'connecting': 'connecting',
  'connected': 'connected',
  'error': 'error',
  'reconnecting': 'connecting',
  'disconnecting': 'disconnected',
};

export function useConnectionState({
  connectionManager,
}: UseConnectionStateParams): UseConnectionStateReturn {
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected');

  useEffect(() => {
    const handleStateChange = (data: { oldState: string; newState: string }) => {
      setConnectionStatus(CONNECTION_STATUS_MAP[data.newState] || 'disconnected');
    };

    connectionManager.on('stateChanged', handleStateChange);

    return () => {
      connectionManager.off('stateChanged', handleStateChange);
    };
  }, [connectionManager]);

  return {
    connectionStatus,
  };
}
