import React from 'react'

export enum ConnectionStatus {
  CONNECTED = 'connected',
  CONNECTING = 'connecting',
  DISCONNECTED = 'disconnected',
  ERROR = 'error'
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
}