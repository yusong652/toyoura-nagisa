/**
 * Connection Manager Context
 * Provides WebSocket connection manager to all components.
 */

import { createContext, useContext } from 'react';
import type { ConnectionManager } from '@toyoura-nagisa/core';

const ConnectionContext = createContext<ConnectionManager | null>(null);

export function useConnectionManager(): ConnectionManager {
  const connectionManager = useContext(ConnectionContext);
  if (!connectionManager) {
    throw new Error('useConnectionManager must be used within a ConnectionProvider');
  }
  return connectionManager;
}

export const ConnectionProvider = ConnectionContext.Provider;
