/**
 * Connection module exports
 *
 * Provides platform-agnostic WebSocket connection management
 * with adapters for browser and Node.js environments.
 */

// WebSocket Manager
export { WebSocketManager, ConnectionState } from './WebSocketManager';
export type {
  WebSocketManagerMessage,
  ConnectionOptions,
  ConnectionStats
} from './WebSocketManager';

// Adapters
export { WebSocketAdapter, ReadyState } from './adapters/WebSocketAdapter';
export { BrowserWebSocketAdapter } from './adapters/BrowserWebSocketAdapter';
export { NodeWebSocketAdapter } from './adapters/NodeWebSocketAdapter';
