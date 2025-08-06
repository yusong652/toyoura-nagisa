/**
 * Enhanced WebSocket Connection Manager
 * Provides robust connection handling with automatic reconnection,
 * heartbeat monitoring, and error recovery for aiNagisa frontend.
 */

// Simple EventEmitter implementation for browser environment
class EventEmitter {
  private events: { [key: string]: Function[] } = {};

  on(event: string, listener: Function): this {
    if (!this.events[event]) {
      this.events[event] = [];
    }
    this.events[event].push(listener);
    return this;
  }

  emit(event: string, ...args: any[]): boolean {
    if (!this.events[event]) {
      return false;
    }
    this.events[event].forEach(listener => listener.apply(this, args));
    return true;
  }

  removeListener(event: string, listener: Function): this {
    if (!this.events[event]) {
      return this;
    }
    this.events[event] = this.events[event].filter(l => l !== listener);
    return this;
  }

  removeAllListeners(event?: string): this {
    if (event) {
      delete this.events[event];
    } else {
      this.events = {};
    }
    return this;
  }
}

export enum ConnectionState {
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  DISCONNECTING = 'disconnecting',
  DISCONNECTED = 'disconnected',
  ERROR = 'error',
  RECONNECTING = 'reconnecting'
}

export interface WebSocketMessage {
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
  maxReconnectAttempts: 5,
  reconnectInterval: 1000, // Start with 1 second
  maxReconnectInterval: 30000, // Max 30 seconds
  heartbeatInterval: 30000, // 30 seconds
  heartbeatTimeout: 10000, // 10 seconds
  enableHeartbeat: true,
  enableAutoReconnect: true
};

export class WebSocketManager extends EventEmitter {
  private websocket: WebSocket | null = null;
  private url: string;
  private options: ConnectionOptions;
  private state: ConnectionState = ConnectionState.DISCONNECTED;
  private reconnectAttempts: number = 0;
  private reconnectTimer: number | null = null;
  private heartbeatTimer: number | null = null;
  private heartbeatTimeoutTimer: number | null = null;
  private stats: ConnectionStats;
  private pendingMessages: WebSocketMessage[] = [];
  private isIntentionalClose: boolean = false;

  constructor(url: string, options: ConnectionOptions = {}) {
    super();
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
      this.websocket = new WebSocket(this.url);
      this.setupWebSocketEventHandlers();

      // Wait for connection to establish or fail
      return new Promise((resolve, reject) => {
        const timeout = window.setTimeout(() => {
          reject(new Error('Connection timeout'));
        }, 10000);

        const onOpen = () => {
          clearTimeout(timeout);
          cleanup();
          resolve();
        };

        const onError = (error: Event) => {
          clearTimeout(timeout);
          cleanup();
          reject(error);
        };

        const cleanup = () => {
          this.websocket?.removeEventListener('open', onOpen);
          this.websocket?.removeEventListener('error', onError);
        };

        this.websocket?.addEventListener('open', onOpen);
        this.websocket?.addEventListener('error', onError);
      });
    } catch (error) {
      this.handleError(error as Error);
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
    
    if (this.websocket) {
      this.setState(ConnectionState.DISCONNECTING);
      this.websocket.close(code, reason);
    } else {
      this.setState(ConnectionState.DISCONNECTED);
    }
  }

  /**
   * Send message through WebSocket
   */
  public async sendMessage(message: WebSocketMessage): Promise<boolean> {
    if (this.state !== ConnectionState.CONNECTED) {
      // Queue message for later if connection is being established
      if (this.state === ConnectionState.CONNECTING || this.state === ConnectionState.RECONNECTING) {
        this.pendingMessages.push(message);
        return false;
      }
      
      this.emit('error', new Error('Cannot send message: WebSocket not connected'));
      return false;
    }

    try {
      this.websocket!.send(JSON.stringify(message));
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
           this.websocket?.readyState === WebSocket.OPEN;
  }

  private setupWebSocketEventHandlers(): void {
    if (!this.websocket) return;

    this.websocket.onopen = () => {
      this.setState(ConnectionState.CONNECTED);
      this.stats.connectedAt = new Date();
      this.reconnectAttempts = 0;
      
      // Start heartbeat if enabled
      if (this.options.enableHeartbeat) {
        this.startHeartbeat();
      }
      
      // Send queued messages
      this.flushPendingMessages();
      
      this.emit('connected');
    };

    this.websocket.onclose = (event) => {
      this.setState(ConnectionState.DISCONNECTED);
      this.clearHeartbeatTimers();
      
      this.emit('disconnected', { code: event.code, reason: event.reason });
      
      // Auto-reconnect if not intentional close
      if (!this.isIntentionalClose && this.options.enableAutoReconnect) {
        this.scheduleReconnect();
      }
    };

    this.websocket.onerror = () => {
      this.handleError(new Error('WebSocket error'));
    };

    this.websocket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as WebSocketMessage;
        this.stats.messagesReceived++;
        
        // Handle system messages
        this.handleSystemMessage(message);
        
        this.emit('message', message);
      } catch (error) {
        this.handleError(new Error('Failed to parse message'));
      }
    };
  }

  private handleSystemMessage(message: WebSocketMessage): void {
    switch (message.type) {
      case 'HEARTBEAT':
        // Respond to heartbeat
        this.sendMessage({ type: 'HEARTBEAT_ACK', timestamp: new Date().toISOString() });
        break;
        
      case 'HEARTBEAT_ACK':
        // Update heartbeat stats
        this.stats.lastHeartbeat = new Date();
        this.clearHeartbeatTimeout();
        break;
        
      case 'CONNECTION_ESTABLISHED':
        // Connection confirmed by server
        break;
        
      case 'error':
        this.handleError(new Error(message.error || 'Server error'));
        break;
    }
  }

  private startHeartbeat(): void {
    this.clearHeartbeatTimers();
    
    this.heartbeatTimer = window.setInterval(() => {
      if (this.isConnected()) {
        this.sendHeartbeat();
      }
    }, this.options.heartbeatInterval!);
  }

  private sendHeartbeat(): void {
    this.sendMessage({ type: 'HEARTBEAT', timestamp: new Date().toISOString() });
    
    // Set timeout for heartbeat response
    this.heartbeatTimeoutTimer = window.setTimeout(() => {
      this.handleError(new Error('Heartbeat timeout - connection may be stale'));
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
      this.emit('maxReconnectAttemptsReached');
      return;
    }

    this.setState(ConnectionState.RECONNECTING);
    
    // Exponential backoff
    const delay = Math.min(
      this.options.reconnectInterval! * Math.pow(2, this.reconnectAttempts),
      this.options.maxReconnectInterval!
    );

    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectAttempts++;
      this.stats.reconnectAttempts = this.reconnectAttempts;
      
      this.emit('reconnecting', { attempt: this.reconnectAttempts, delay });
      
      this.connect().catch((error) => {
        this.handleError(error);
        this.scheduleReconnect(); // Try again
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
        // Reconnect with new URL
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