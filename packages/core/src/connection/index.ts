/**
 * Connection module exports
 *
 * Provides platform-agnostic WebSocket connection management
 * with adapters for browser and Node.js environments.
 */

// WebSocket Manager
export { WebSocketManager, ConnectionState } from './WebSocketManager.js';
export type {
  WebSocketManagerMessage,
  ConnectionOptions,
  ConnectionStats
} from './WebSocketManager.js';

// Connection Manager (toyoura-nagisa-specific)
export { ConnectionManager } from './ConnectionManager.js';
export type {
  ToolConfirmationData,
  LocationData,
  ConnectionManagerOptions
} from './ConnectionManager.js';

// Adapters
export { WebSocketAdapter, ReadyState } from './adapters/WebSocketAdapter.js';
export { BrowserWebSocketAdapter } from './adapters/BrowserWebSocketAdapter.js';
export { NodeWebSocketAdapter } from './adapters/NodeWebSocketAdapter.js';
