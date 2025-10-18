import React from 'react'

export enum ConnectionStatus {
  CONNECTED = 'connected',
  CONNECTING = 'connecting',
  DISCONNECTED = 'disconnected',
  ERROR = 'error'
}

/**
 * Bash confirmation request data structure
 */
export interface BashConfirmationData {
  confirmation_id: string
  command: string
  description?: string
  timestamp?: string
}

export interface ConnectionContextType {
  connectionStatus: ConnectionStatus
  connectionError: string | null
  wsRef: React.RefObject<WebSocket | null>
  connectToSession: (sessionId: string) => void
  disconnect: () => void
  sendWebSocketMessage: (message: any) => void
  onLocationRequest: (handler: (data: any) => void) => void
  checkConnection: () => Promise<boolean>
  waitForConnection: (timeout?: number) => Promise<boolean>

  // Bash confirmation management
  pendingBashConfirmation: BashConfirmationData | null
  clearPendingBashConfirmation: () => void
}