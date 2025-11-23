/**
 * WebSocket Adapter Interface
 *
 * Platform-agnostic interface for WebSocket connections.
 * Enables using browser WebSocket or Node.js 'ws' library with the same API.
 */

export interface WebSocketAdapter {
  /**
   * Establish WebSocket connection
   * @param url - WebSocket server URL
   * @param protocols - Optional subprotocols
   */
  connect(url: string, protocols?: string | string[]): void;

  /**
   * Send data through the WebSocket
   * @param data - Data to send (will be stringified if needed)
   */
  send(data: string): void;

  /**
   * Close the WebSocket connection
   * @param code - Close code (default: 1000)
   * @param reason - Close reason
   */
  close(code?: number, reason?: string): void;

  /**
   * Get current ready state
   */
  getReadyState(): number;

  /**
   * Register callback for connection open event
   * @param callback - Function to call when connection opens
   */
  onOpen(callback: () => void): void;

  /**
   * Register callback for incoming messages
   * @param callback - Function to call when message is received
   */
  onMessage(callback: (data: string) => void): void;

  /**
   * Register callback for errors
   * @param callback - Function to call when error occurs
   */
  onError(callback: (error: Error) => void): void;

  /**
   * Register callback for connection close
   * @param callback - Function to call when connection closes
   */
  onClose(callback: (code: number, reason: string) => void): void;
}

/**
 * WebSocket ready state constants
 */
export enum ReadyState {
  CONNECTING = 0,
  OPEN = 1,
  CLOSING = 2,
  CLOSED = 3
}
