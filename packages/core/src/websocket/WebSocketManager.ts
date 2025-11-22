/**
 * WebSocket Manager - Core WebSocket connection management
 * Extracted from frontend/src/contexts/connection/ConnectionContext.tsx
 */

import { EventEmitter } from 'events'
import WebSocket from 'ws'

export enum ConnectionStatus {
  CONNECTING = 'CONNECTING',
  CONNECTED = 'CONNECTED',
  DISCONNECTED = 'DISCONNECTED',
  ERROR = 'ERROR'
}

export interface WebSocketMessage {
  type: string
  [key: string]: any
}

export class WebSocketManager extends EventEmitter {
  private ws: WebSocket | null = null
  private sessionId: string | null = null
  private status: ConnectionStatus = ConnectionStatus.DISCONNECTED
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private baseReconnectDelay = 2000
  private reconnectTimeout: NodeJS.Timeout | null = null
  private shouldReconnect = true

  constructor(private host: string = 'localhost', private port: number = 8000) {
    super()
  }

  /**
   * Connect to WebSocket server for specified session
   * Extracted from ConnectionContext.tsx connectToSession()
   */
  async connect(sessionId: string): Promise<void> {
    if (!sessionId) {
      throw new Error('Session ID is required')
    }

    // Prevent duplicate connections
    if (this.sessionId === sessionId && this.ws?.readyState === WebSocket.OPEN) {
      console.log(`[WebSocket] Already connected to session ${sessionId}`)
      return
    }

    this.sessionId = sessionId
    this.shouldReconnect = true

    // Close previous connection
    if (this.ws) {
      this.ws.close(1000, 'Switching session')
      this.ws = null
    }

    // Clear reconnect timeout
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout)
      this.reconnectTimeout = null
    }

    const wsUrl = `ws://${this.host}:${this.port}/ws/${sessionId}`
    console.log(`[WebSocket] Connecting to ${wsUrl}`)

    this.ws = new WebSocket(wsUrl)
    this.status = ConnectionStatus.CONNECTING
    this.emit('statusChange', this.status)

    this.ws.on('open', () => this.handleOpen())
    this.ws.on('close', (code, reason) => this.handleClose(code, reason.toString()))
    this.ws.on('error', (error) => this.handleError(error))
    this.ws.on('message', (data) => this.handleMessage(data))
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect(): void {
    this.shouldReconnect = false
    this.sessionId = null

    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout)
      this.reconnectTimeout = null
    }

    if (this.ws) {
      this.ws.close(1000, 'Manual disconnect')
      this.ws = null
    }

    this.status = ConnectionStatus.DISCONNECTED
    this.emit('statusChange', this.status)
  }

  /**
   * Send message to WebSocket server
   * Extracted from ConnectionContext.tsx sendWebSocketMessage()
   */
  send(message: WebSocketMessage): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message))
      console.log(`[WebSocket] Sent message:`, message.type)
    } else {
      console.warn('[WebSocket] Not connected, cannot send message')
    }
  }

  /**
   * Get current connection status
   */
  getStatus(): ConnectionStatus {
    return this.status
  }

  /**
   * Get current session ID
   */
  getSessionId(): string | null {
    return this.sessionId
  }

  // Private handlers

  private handleOpen(): void {
    console.log('[WebSocket] Connected')
    this.status = ConnectionStatus.CONNECTED
    this.reconnectAttempts = 0
    this.emit('statusChange', this.status)
    this.emit('connected')
  }

  private handleClose(code: number, reason: string): void {
    console.log(`[WebSocket] Closed - Code: ${code}, Reason: ${reason}`)
    this.status = ConnectionStatus.DISCONNECTED
    this.emit('statusChange', this.status)
    this.emit('disconnected', { code, reason })

    // Auto-reconnect logic (extracted from ConnectionContext.tsx)
    if (this.shouldReconnect && code !== 1000 && this.sessionId) {
      this.attemptReconnect()
    }
  }

  private handleError(error: Error): void {
    console.error('[WebSocket] Error:', error)
    this.status = ConnectionStatus.ERROR
    this.emit('statusChange', this.status)
    this.emit('error', error)
  }

  private handleMessage(data: WebSocket.Data): void {
    try {
      const message: WebSocketMessage = JSON.parse(data.toString())

      // Handle heartbeat
      if (message.type === 'HEARTBEAT') {
        this.send({ type: 'HEARTBEAT_ACK', timestamp: new Date().toISOString() })
        return
      }

      // Emit message event with type-specific event
      this.emit('message', message)
      this.emit(message.type, message)

    } catch (error) {
      console.error('[WebSocket] Failed to parse message:', error)
    }
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('[WebSocket] Max reconnect attempts reached')
      this.status = ConnectionStatus.ERROR
      this.emit('statusChange', this.status)
      this.emit('reconnectFailed')
      return
    }

    this.reconnectAttempts++
    const delay = Math.min(
      this.baseReconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
      30000
    )

    console.log(`[WebSocket] Reconnecting (${this.reconnectAttempts}/${this.maxReconnectAttempts}) in ${delay}ms`)

    this.reconnectTimeout = setTimeout(() => {
      if (this.sessionId && this.shouldReconnect) {
        this.connect(this.sessionId)
      }
    }, delay)
  }
}
