/**
 * toyoura-nagisa Connection Manager
 *
 * Extends WebSocketManager with toyoura-nagisa-specific message handling
 * and business logic for chat sessions, tool confirmations, and notifications.
 */

import { WebSocketManager, ConnectionState, WebSocketManagerMessage } from './WebSocketManager';
import { WebSocketAdapter } from './adapters/WebSocketAdapter';

export interface ToolConfirmationData {
  message_id: string;
  tool_call_id: string;
  tool_name: string;
  command?: string;
  description?: string;
  timestamp?: string;
  // New fields for edit confirmation with diff display
  confirmation_type?: 'edit' | 'exec' | 'info';
  file_name?: string;
  file_path?: string;
  file_diff?: string;
  original_content?: string;
  new_content?: string;
}

export interface LocationData {
  latitude: number;
  longitude: number;
  accuracy?: number;
  altitude?: number;
  altitudeAccuracy?: number;
  heading?: number;
  speed?: number;
  timestamp?: number;
  address?: string;
}

export interface ConnectionManagerOptions {
  maxReconnectAttempts?: number;
  reconnectInterval?: number;
  maxReconnectInterval?: number;
  heartbeatInterval?: number;
  heartbeatTimeout?: number;
  enableHeartbeat?: boolean;
  enableAutoReconnect?: boolean;
}

/**
 * toyoura-nagisa-specific connection manager
 * Handles session-based WebSocket connections with message routing
 */
export class ConnectionManager extends WebSocketManager {
  private sessionId: string | null = null;
  private locationRequestHandler: ((data: any) => Promise<LocationData | null>) | null = null;

  constructor(adapter: WebSocketAdapter, baseUrl: string, options: ConnectionManagerOptions = {}) {
    super(adapter, baseUrl, options);
    this.setupMessageHandlers();
  }

  /**
   * Connect to a specific session
   */
  public async connectToSession(sessionId: string): Promise<void> {
    if (!sessionId) {
      throw new Error('Session ID is required');
    }

    this.sessionId = sessionId;
    const sessionUrl = this.buildSessionUrl(sessionId);
    this.updateUrl(sessionUrl);

    return this.connect();
  }

  /**
   * Get current session ID
   */
  public getSessionId(): string | null {
    return this.sessionId;
  }

  /**
   * Register location request handler
   */
  public setLocationRequestHandler(handler: (data: any) => Promise<LocationData | null>): void {
    this.locationRequestHandler = handler;
  }

  /**
   * Build WebSocket URL for session
   */
  private buildSessionUrl(sessionId: string): string {
    // Extract base URL without path
    const url = new URL(this.getUrl());
    url.pathname = `/ws/${sessionId}`;
    return url.toString();
  }

  /**
   * Get base URL (for updateUrl compatibility)
   */
  private getUrl(): string {
    // Access protected url via type assertion
    return (this as any).url;
  }

  /**
   * Setup toyoura-nagisa-specific message handlers
   */
  private setupMessageHandlers(): void {
    this.on('message', (message: WebSocketManagerMessage) => {
      this.handleNagisaMessage(message);
    });
  }

  /**
   * Handle toyoura-nagisa-specific messages
   */
  private async handleNagisaMessage(message: WebSocketManagerMessage): Promise<void> {
    switch (message.type) {
      case 'LOCATION_REQUEST':
        await this.handleLocationRequest(message);
        break;

      case 'TTS_CHUNK':
        this.emit('tts_chunk', {
          text: message.text,
          audio: message.audio,
          index: message.index,
          is_final: message.is_final,
          message_id: message.message_id,
          engine_status: message.engine_status,
          error: message.error,
          processing_time: message.processing_time
        });
        break;

      case 'STATUS_UPDATE':
        this.emit('status_update', {
          messageId: message.message_id,
          status: message.status,
          errorMessage: message.error_message
        });
        break;

      case 'MESSAGE_CREATE':
        this.emit('message_create', {
          messageId: message.message_id,
          role: message.role,
          initialText: message.initial_text || '',
          streaming: message.streaming !== undefined ? message.streaming : true
        });
        break;

      case 'STREAMING_UPDATE':
        this.emit('streaming_update', {
          messageId: message.message_id,
          content: message.content,
          streaming: message.streaming,
          usage: message.usage
        });
        break;

      case 'TITLE_UPDATE':
        this.emit('title_update', message);
        break;

      case 'TODO_UPDATE':
        this.emit('todo_update', {
          todo: message.todo
        });
        break;

      case 'EMOTION_KEYWORD':
        this.emit('emotion_keyword', message);
        break;

      case 'TOOL_CONFIRMATION_REQUEST':
        this.emit('tool_confirmation_request', {
          message_id: message.message_id,
          tool_call_id: message.tool_call_id,
          tool_name: message.tool_name,
          command: message.command,
          description: message.description,
          timestamp: message.timestamp,
          // New fields for edit confirmation with diff display
          confirmation_type: message.confirmation_type,
          file_name: message.file_name,
          file_path: message.file_path,
          file_diff: message.file_diff,
          original_content: message.original_content,
          new_content: message.new_content
        } as ToolConfirmationData);
        break;

      case 'BACKGROUND_PROCESS_STARTED':
      case 'BACKGROUND_PROCESS_OUTPUT_UPDATE':
      case 'BACKGROUND_PROCESS_COMPLETED':
      case 'BACKGROUND_PROCESS_KILLED':
        this.emit('background_process_notification', message);
        break;

      case 'TOOL_RESULT_UPDATE':
        this.emit('tool_result_update', {
          message_id: message.message_id,
          session_id: message.session_id,
          content: message.content
        });
        break;

      default:
        // Emit generic message for unhandled types
        this.emit('unhandled_message', message);
        break;
    }
  }

  /**
   * Handle location request from backend
   */
  private async handleLocationRequest(data: any): Promise<void> {
    try {
      if (!this.locationRequestHandler) {
        await this.sendLocationError(data.request_id, 'No location handler available');
        return;
      }

      const locationData = await this.locationRequestHandler(data);

      if (locationData) {
        await this.sendLocationResponse(data.request_id, locationData);
      } else {
        await this.sendLocationError(data.request_id, 'Failed to get location');
      }
    } catch (error) {
      await this.sendLocationError(
        data.request_id,
        error instanceof Error ? error.message : 'Unknown error'
      );
    }
  }

  /**
   * Send location response to backend
   */
  private async sendLocationResponse(requestId: string, locationData: LocationData): Promise<void> {
    await this.sendMessage({
      type: 'LOCATION_RESPONSE',
      session_id: this.sessionId ?? undefined,
      request_id: requestId,
      location_data: locationData,
      timestamp: new Date().toISOString()
    });
  }

  /**
   * Send location error response to backend
   */
  private async sendLocationError(requestId: string, error: string): Promise<void> {
    await this.sendMessage({
      type: 'LOCATION_RESPONSE',
      session_id: this.sessionId ?? undefined,
      request_id: requestId,
      error: error,
      timestamp: new Date().toISOString()
    });
  }

  /**
   * Get native WebSocket instance (browser only)
   * Used for compatibility with existing code
   */
  public getNativeWebSocket(): WebSocket | null {
    // Check if adapter has getNativeWebSocket method (BrowserWebSocketAdapter)
    const adapter = this.getAdapter();
    if ('getNativeWebSocket' in adapter && typeof adapter.getNativeWebSocket === 'function') {
      return (adapter as any).getNativeWebSocket();
    }
    return null;
  }

  /**
   * Get adapter instance
   */
  private getAdapter(): WebSocketAdapter {
    return (this as any).adapter;
  }

  /**
   * Disconnect and clear session
   */
  public override disconnect(code?: number, reason?: string): void {
    this.sessionId = null;
    super.disconnect(code, reason);
  }
}

export default ConnectionManager;
