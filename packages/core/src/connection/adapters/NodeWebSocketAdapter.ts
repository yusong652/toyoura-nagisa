/**
 * Node.js WebSocket Adapter
 *
 * Adapter for Node.js 'ws' library.
 * Wraps the ws WebSocket to conform to WebSocketAdapter interface.
 *
 * Note: This adapter requires the 'ws' package to be installed.
 * Install with: npm install ws @types/ws
 */

import { WebSocketAdapter, ReadyState } from './WebSocketAdapter';

// Import WebSocket from 'ws' package (will be available in Node.js environment)
// This is a type-only import - actual import happens at runtime
type WebSocketConstructor = any;
type WebSocketInstance = any;

export class NodeWebSocketAdapter implements WebSocketAdapter {
  private ws: WebSocketInstance | null = null;
  private WebSocketClass: WebSocketConstructor | null = null;

  constructor() {
    // Dynamically import 'ws' package (only available in Node.js)
    try {
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const wsModule = require('ws');
      this.WebSocketClass = wsModule.default || wsModule;
    } catch (error) {
      throw new Error(
        "NodeWebSocketAdapter requires 'ws' package. Install with: npm install ws"
      );
    }
  }

  connect(url: string, protocols?: string | string[]): void {
    if (!this.WebSocketClass) {
      throw new Error('WebSocket class not initialized');
    }
    this.ws = new this.WebSocketClass(url, protocols);
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
    return this.ws?.readyState ?? ReadyState.CLOSED;
  }

  onOpen(callback: () => void): void {
    if (this.ws) {
      this.ws.on('open', callback);
    }
  }

  onMessage(callback: (data: string) => void): void {
    if (this.ws) {
      this.ws.on('message', (data: Buffer | string) => {
        const message = typeof data === 'string' ? data : data.toString();
        callback(message);
      });
    }
  }

  onError(callback: (error: Error) => void): void {
    if (this.ws) {
      this.ws.on('error', (error: Error) => {
        callback(error);
      });
    }
  }

  onClose(callback: (code: number, reason: string) => void): void {
    if (this.ws) {
      this.ws.on('close', (code: number, reason: string) => {
        callback(code, reason);
      });
    }
  }
}
