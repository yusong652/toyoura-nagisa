/**
 * Browser WebSocket Adapter
 *
 * Adapter for browser's native WebSocket API.
 * Wraps the browser WebSocket to conform to WebSocketAdapter interface.
 */

import { WebSocketAdapter } from './WebSocketAdapter.js';

export class BrowserWebSocketAdapter implements WebSocketAdapter {
  private ws: WebSocket | null = null;

  connect(url: string, protocols?: string | string[]): void {
    this.ws = new WebSocket(url, protocols);
  }

  /**
   * Get native WebSocket instance (browser-specific)
   * Used for compatibility with existing code that needs direct WebSocket access
   */
  getNativeWebSocket(): WebSocket | null {
    return this.ws;
  }

  send(data: string): void {
    if (!this.ws) {
      throw new Error('WebSocket not connected');
    }
    this.ws.send(data);
  }

  close(code: number = 1000, reason: string = ''): void {
    if (this.ws) {
      this.ws.close(code, reason);
    }
  }

  getReadyState(): number {
    return this.ws?.readyState ?? 3; // CLOSED
  }

  onOpen(callback: () => void): void {
    if (this.ws) {
      this.ws.onopen = callback;
    }
  }

  onMessage(callback: (data: string) => void): void {
    if (this.ws) {
      this.ws.onmessage = (event: MessageEvent) => {
        callback(event.data);
      };
    }
  }

  onError(callback: (error: Error) => void): void {
    if (this.ws) {
      this.ws.onerror = () => {
        callback(new Error('WebSocket error'));
      };
    }
  }

  onClose(callback: (code: number, reason: string) => void): void {
    if (this.ws) {
      this.ws.onclose = (event) => {
        callback(event.code, event.reason);
      };
    }
  }
}
