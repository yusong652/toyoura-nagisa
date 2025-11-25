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
type WebSocketConstructor = new (
  url: string,
  protocols?: string | string[]
) => WebSocketInstance;
type WebSocketInstance = {
  readyState: number;
  send(data: string): void;
  close(code?: number, reason?: string): void;
  on(event: string, listener: (...args: any[]) => void): void;
};

// Module-level cache for WebSocket class
let WebSocketClass: WebSocketConstructor | null = null;
let wsLoadPromise: Promise<void> | null = null;

async function loadWebSocketClass(): Promise<void> {
  if (WebSocketClass) return;
  if (wsLoadPromise) return wsLoadPromise;

  wsLoadPromise = (async () => {
    try {
      // Use dynamic import for ESM compatibility
      const wsModule = await import('ws');
      WebSocketClass = (wsModule.default || wsModule) as WebSocketConstructor;
    } catch (error) {
      throw new Error(
        "NodeWebSocketAdapter requires 'ws' package. Install with: npm install ws"
      );
    }
  })();

  return wsLoadPromise;
}

export class NodeWebSocketAdapter implements WebSocketAdapter {
  private ws: WebSocketInstance | null = null;

  constructor() {
    // Start loading ws module (non-blocking)
    loadWebSocketClass();
  }

  async connect(url: string, protocols?: string | string[]): Promise<void> {
    // Ensure ws module is loaded
    await loadWebSocketClass();
    if (!WebSocketClass) {
      throw new Error('WebSocket class not initialized');
    }
    this.ws = new WebSocketClass(url, protocols);
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
      // ws library 'message' event: (data: RawData, isBinary: boolean)
      // RawData = Buffer | ArrayBuffer | Buffer[]
      this.ws.on('message', (data: Buffer | ArrayBuffer | Buffer[], _isBinary: boolean) => {
        let message: string;
        if (Buffer.isBuffer(data)) {
          message = data.toString('utf-8');
        } else if (Array.isArray(data)) {
          // Buffer[] - concatenate all buffers
          message = Buffer.concat(data).toString('utf-8');
        } else if (data instanceof ArrayBuffer) {
          message = Buffer.from(data).toString('utf-8');
        } else {
          // Fallback for any other type
          message = String(data);
        }
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
