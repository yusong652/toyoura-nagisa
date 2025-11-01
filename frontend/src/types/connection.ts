import React from 'react'

export enum ConnectionStatus {
  CONNECTED = 'connected',
  CONNECTING = 'connecting',
  DISCONNECTED = 'disconnected',
  ERROR = 'error'
}

/**
 * Tool confirmation request data structure (bash, edit, write, etc.)
 */
export interface ToolConfirmationData {
  tool_call_id: string  // ID used for both matching and tracking
  tool_name: string
  command: string
  description?: string
  timestamp?: string
}

export interface ConnectionContextType {
  connectionStatus: ConnectionStatus
  connectionError: string | null
  sessionId: string | null
  wsRef: React.RefObject<WebSocket | null>
  connectToSession: (sessionId: string) => void
  disconnect: () => void
  sendWebSocketMessage: (message: any) => void
  onLocationRequest: (handler: (data: any) => void) => void
  checkConnection: () => Promise<boolean>
  waitForConnection: (timeout?: number) => Promise<boolean>

  // Tool confirmation management (bash, edit, write, etc.)
  pendingToolConfirmation: ToolConfirmationData | null
  clearPendingToolConfirmation: () => void
}