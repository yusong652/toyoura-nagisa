/**
 * Enhanced WebSocket Connection Manager
 *
 * Platform-agnostic WebSocket manager using adapter pattern.
 * Provides robust connection handling with automatic reconnection,
 * heartbeat monitoring, and error recovery for toyoura-nagisa.
 */

import { EventEmitter } from 'eventemitter3';
import { WebSocketAdapter, ReadyState } from './adapters/WebSocketAdapter';

export enum ConnectionState {
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  DISCONNECTING = 'disconnecting',
  DISCONNECTED = 'disconnected',
  ERROR = 'error',
  RECONNECTING = 'reconnecting'
}

/**
 * Generic WebSocket message interface for WebSocketManager
 * For specific message types, use the types from @toyoura-nagisa/core/types
 */
export interface WebSocketManagerMessage {
  type: string;
  timestamp?: string;
  session_id?: string;
  [key: string]: any;
}

export interface ConnectionOptions {
  maxReconnectAttempts?: number;
  reconnectInterval?: number;
  maxReconnectInterval?: number;
  heartbeatInterval?: number;
  heartbeatTimeout?: number;
  enableHeartbeat?: boolean;
  enableAutoReconnect?: boolean;
}

export interface ConnectionStats {
  state: ConnectionState;
  connectedAt?: Date;
  lastHeartbeat?: Date;
  reconnectAttempts: number;
  messagesReceived: number;
  messagesSent: number;
  errors: number;
}

const DEFAULT_OPTIONS: ConnectionOptions = {
  maxReconnectAttempts: 10,
  reconnectInterval: 2000,
  maxReconnectInterval: 60000,
  heartbeatInterval: 60000,
  heartbeatTimeout: 30000,
  enableHeartbeat: true,
  enableAutoReconnect: true
};

export class WebSocketManager extends EventEmitter {
  private adapter: WebSocketAdapter;
  private url: string;
  private options: ConnectionOptions;
  private state: ConnectionState = ConnectionState.DISCONNECTED;
  private reconnectAttempts: number = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private heartbeatTimeoutTimer: ReturnType<typeof setTimeout> | null = null;
  private stats: ConnectionStats;
  private pendingMessages: WebSocketManagerMessage[] = [];
  private isIntentionalClose: boolean = false;

  constructor(adapter: WebSocketAdapter, url: string, options: ConnectionOptions = {}) {
    super();
    this.adapter = adapter;
    this.url = url;
    this.options = { ...DEFAULT_OPTIONS, ...options };
    this.stats = {
      state: ConnectionState.DISCONNECTED,
      reconnectAttempts: 0,
      messagesReceived: 0,
      messagesSent: 0,
      errors: 0
    };
  }

  /**
   * Establish WebSocket connection
   */
  public async connect(): Promise<void> {
    if (this.state === ConnectionState.CONNECTING || this.state === ConnectionState.CONNECTED) {
      return;
    }

    this.isIntentionalClose = false;
    this.setState(ConnectionState.CONNECTING);

    try {
      await this.adapter.connect(this.url);
      this.setupAdapterEventHandlers();

      // Wait for connection to establish or fail
      return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          const error = new Error('Connection timeout');
          cleanup();
          // Schedule reconnect on initial connection timeout
          if (this.options.enableAutoReconnect) {
            this.scheduleReconnect();
          }
          reject(error);
        }, 10000);

        const onOpen = () => {
          clearTimeout(timeout);
          cleanup();
          resolve();
        };

        const onError = (error: Error) => {
          clearTimeout(timeout);
          cleanup();
          reject(error);
        };

        const cleanup = () => {
          this.off('connected', onOpen);
          this.off('error', onError);
        };

        this.once('connected', onOpen);
        this.once('error', onError);
      });
    } catch (error) {
      this.handleError(error as Error);
      // Schedule reconnect on initial connection failure
      if (this.options.enableAutoReconnect) {
        this.scheduleReconnect();
      }
      throw error;
    }
  }

  /**
   * Disconnect WebSocket connection
   */
  public disconnect(code: number = 1000, reason: string = ''): void {
    this.isIntentionalClose = true;
    this.clearReconnectTimer();
    this.clearHeartbeatTimers();

    this.setState(ConnectionState.DISCONNECTING);
    this.adapter.close(code, reason);
  }

  /**
   * Send message through WebSocket
   */
  public async sendMessage(message: WebSocketManagerMessage): Promise<boolean> {
    if (this.state !== ConnectionState.CONNECTED) {
      if (this.state === ConnectionState.CONNECTING || this.state === ConnectionState.RECONNECTING) {
        this.pendingMessages.push(message);
        return false;
      }

      this.emit('error', new Error('Cannot send message: WebSocket not connected'));
      return false;
    }

    try {
      const messageString = JSON.stringify(message);
      this.adapter.send(messageString);
      this.stats.messagesSent++;
      this.emit('messageSent', message);
      return true;
    } catch (error) {
      this.handleError(error as Error);
      return false;
    }
  }

  /**
   * Send JSON data (legacy compatibility)
   */
  public async send(data: any): Promise<boolean> {
    return this.sendMessage(data);
  }

  /**
   * Get current connection state
   */
  public getState(): ConnectionState {
    return this.state;
  }

  /**
   * Get connection statistics
   */
  public getStats(): ConnectionStats {
    return { ...this.stats, state: this.state };
  }

  /**
   * Check if connection is healthy
   */
  public isConnected(): boolean {
    return this.state === ConnectionState.CONNECTED &&
           this.adapter.getReadyState() === ReadyState.OPEN;
  }

  private setupAdapterEventHandlers(): void {
    this.adapter.onOpen(() => {
      this.setState(ConnectionState.CONNECTED);
      this.stats.connectedAt = new Date();
      this.reconnectAttempts = 0;

      if (this.options.enableHeartbeat) {
        this.startHeartbeat();
      }

      this.flushPendingMessages();
      this.emit('connected');
    });

    this.adapter.onClose((code, reason) => {
      console.log(`[WebSocketManager] Connection closed: code=${code}, reason=${reason}, intentional=${this.isIntentionalClose}`);
      this.setState(ConnectionState.DISCONNECTED);
      this.clearHeartbeatTimers();

      this.emit('disconnected', { code, reason });

      if (!this.isIntentionalClose && this.options.enableAutoReconnect) {
        this.scheduleReconnect();
      }
    });

    this.adapter.onError((error) => {
      this.handleError(error);
    });

    this.adapter.onMessage((data) => {
      try {
        const message = JSON.parse(data) as WebSocketManagerMessage;
        this.stats.messagesReceived++;

        this.handleSystemMessage(message);
        this.emit('message', message);
      } catch (error) {
        this.handleError(new Error('Failed to parse WebSocket message'));
      }
    });
  }

  private handleSystemMessage(message: WebSocketManagerMessage): void {
    switch (message.type) {
      case 'HEARTBEAT':
        // Server sent heartbeat - respond with ACK and reset our timeout
        this.sendMessage({ type: 'HEARTBEAT_ACK', timestamp: new Date().toISOString() });
        this.stats.lastHeartbeat = new Date();
        // Reset timeout since we received a heartbeat from server
        if (this.options.enableHeartbeat) {
          this.resetHeartbeatTimeout();
        }
        break;

      case 'HEARTBEAT_ACK':
        // This is for scenarios where client sends heartbeat and server responds
        // In toyoura-nagisa, server initiates heartbeat, so this is less common
        this.stats.lastHeartbeat = new Date();
        this.clearHeartbeatTimeout();
        break;

      case 'CONNECTION_ESTABLISHED':
        break;

      case 'error':
        this.handleError(new Error(message.error || 'Server error'));
        break;
    }
  }

  private startHeartbeat(): void {
    // Note: In toyoura-nagisa architecture, the server sends HEARTBEAT and client responds with HEARTBEAT_ACK.
    // The client does NOT need to proactively send heartbeats.
    // This method is kept for potential future use with servers that expect client-initiated heartbeats.
    // For toyoura-nagisa backend, heartbeat response is handled in handleSystemMessage().
    this.clearHeartbeatTimers();

    // Set up a timeout to detect if server stops sending heartbeats
    // This helps detect connection staleness from the client side
    this.resetHeartbeatTimeout();
  }

  private resetHeartbeatTimeout(): void {
    this.clearHeartbeatTimeout();

    // If server doesn't send heartbeat within timeout period, connection may be stale
    // Server sends heartbeat every 20s, so we use a longer timeout (e.g., 60s)
    this.heartbeatTimeoutTimer = setTimeout(() => {
      this.handleError(new Error('Heartbeat timeout - no heartbeat from server'));
    }, this.options.heartbeatTimeout!);
  }

  private clearHeartbeatTimeout(): void {
    if (this.heartbeatTimeoutTimer) {
      clearTimeout(this.heartbeatTimeoutTimer);
      this.heartbeatTimeoutTimer = null;
    }
  }

  private clearHeartbeatTimers(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    this.clearHeartbeatTimeout();
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.options.maxReconnectAttempts!) {
      console.log('[WebSocketManager] Max reconnect attempts reached');
      this.emit('maxReconnectAttemptsReached');
      return;
    }

    this.setState(ConnectionState.RECONNECTING);

    const delay = Math.min(
      this.options.reconnectInterval! * Math.pow(2, this.reconnectAttempts),
      this.options.maxReconnectInterval!
    );

    console.log(`[WebSocketManager] Scheduling reconnect in ${delay}ms (attempt ${this.reconnectAttempts + 1})`);

    this.reconnectTimer = setTimeout(() => {
      this.reconnectAttempts++;
      this.stats.reconnectAttempts = this.reconnectAttempts;

      console.log(`[WebSocketManager] Reconnecting... (attempt ${this.reconnectAttempts})`);
      this.emit('reconnecting', { attempt: this.reconnectAttempts, delay });

      this.connect().catch((error) => {
        console.log(`[WebSocketManager] Reconnect failed: ${error.message}`);
        this.handleError(error);
        this.scheduleReconnect();
      });
    }, delay);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private setState(newState: ConnectionState): void {
    if (this.state !== newState) {
      const oldState = this.state;
      this.state = newState;
      this.stats.state = newState;
      this.emit('stateChanged', { oldState, newState });
    }
  }

  private handleError(error: Error): void {
    this.stats.errors++;
    this.setState(ConnectionState.ERROR);
    this.emit('error', error);
  }

  private flushPendingMessages(): void {
    const messages = [...this.pendingMessages];
    this.pendingMessages = [];

    for (const message of messages) {
      this.sendMessage(message);
    }
  }

  /**
   * Update connection URL (requires reconnection)
   */
  public updateUrl(newUrl: string): void {
    if (this.url !== newUrl) {
      this.url = newUrl;

      if (this.isConnected()) {
        this.disconnect();
        this.connect();
      }
    }
  }

  /**
   * Reset connection stats
   */
  public resetStats(): void {
    this.stats = {
      state: this.state,
      connectedAt: this.stats.connectedAt,
      reconnectAttempts: 0,
      messagesReceived: 0,
      messagesSent: 0,
      errors: 0
    };
    this.reconnectAttempts = 0;
  }
}

export default WebSocketManager;
