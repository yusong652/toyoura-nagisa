/**
 * Chat API service for handling message-related operations.
 *
 * Provides methods for sending messages via WebSocket, deleting messages,
 * and managing chat-related functionality in the toyoura-nagisa application.
 *
 * Note: Chat messaging has been migrated from HTTP SSE to WebSocket for
 * better real-time performance and unified architecture.
 */

import { apiClient } from './HttpClient.js'
import type { FileData } from '../types/index.js'

export interface MessageRequest {
  id: string
  text: string
  timestamp: number
  files: Array<{
    name: string
    type: string
    data: string
  }>
}

export interface ChatStreamRequest {
  messageData: string
  session_id: string
  mentioned_files?: string[]  // File paths from @ mentions (frontend-confirmed)
}

export interface MessageDeleteRequest {
  session_id: string
  message_id: string
}

export interface MessageDeleteData {
  session_id: string
  message_id: string
}

export class ChatService {
  /**
   * Send a chat message via WebSocket connection.
   *
   * Note: This method requires a WebSocket connection to be provided via setWebSocketConnection().
   * Platform-specific frontends should inject the WebSocket connection before calling this method.
   *
   * @param text - Message text content
   * @param files - Optional file attachments
   * @param sessionId - Current session identifier
   * @param userMessageId - Unique identifier for the user message
   * @param agentProfile - Agent profile for tool selection
   * @param mentionedFiles - Optional file paths from @ mentions (frontend-confirmed)
   * @returns Promise resolving to mock Response for compatibility (WebSocket doesn't return Response)
   */
  async sendMessage(
    text: string,
    files: FileData[] = [],
    sessionId: string,
    userMessageId: string,
    mentionedFiles: string[] = []
  ): Promise<Response> {
    // Get WebSocket connection
    const wsRef = this.getWebSocketConnection()

    // Validate WebSocket connection
    if (!wsRef) {
      throw new Error('WebSocket connection not established. Call setWebSocketConnection() first.')
    }

    if (wsRef.readyState !== 1 /* OPEN */) {
      throw new Error(`WebSocket connection not ready (state: ${wsRef.readyState}). Please wait for connection to establish.`)
    }

    // Create WebSocket message format
    const websocketMessage: any = {
      type: 'CHAT_MESSAGE',
      session_id: sessionId,
      message_id: userMessageId,
      message: text,
      files: files.map(file => ({
        name: file.name,
        type: file.type,
        data: file.data
      })),
      stream_response: true,
      timestamp: new Date().toISOString()
    }

    // Add mentioned_files only if non-empty (optional field)
    if (mentionedFiles.length > 0) {
      websocketMessage.mentioned_files = mentionedFiles
    }

    // Send via WebSocket - serialize to JSON here for consistency
    wsRef.send(JSON.stringify(websocketMessage))

    // Return mock Response for compatibility with existing code
    // The actual response will come via WebSocket events
    return new Response('{"status": "sent_via_websocket"}', {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    })
  }

  // WebSocket connection (injected by platform-specific frontend)
  private ws: any | null = null

  /**
   * Set WebSocket connection for sending messages.
   * Platform-specific frontends should call this method to inject the WebSocket connection.
   *
   * @param ws - WebSocket connection instance
   */
  public setWebSocketConnection(ws: any): void {
    this.ws = ws
  }

  /**
   * Get WebSocket connection.
   *
   * @returns WebSocket connection or null if not set
   */
  private getWebSocketConnection(): any | null {
    return this.ws
  }

  /**
   * Delete a specific message from a chat session.
   *
   * Note: HttpClient automatically unwraps ApiResponse format,
   * so this returns the data payload directly (MessageDeleteData).
   *
   * @param sessionId - Session containing the message
   * @param messageId - Unique identifier of message to delete
   * @returns Promise resolving to deletion result
   */
  async deleteMessage(sessionId: string, messageId: string): Promise<MessageDeleteData> {
    const request: MessageDeleteRequest = {
      session_id: sessionId,
      message_id: messageId
    }

    return await apiClient.post<MessageDeleteData>('/api/messages/delete', request)
  }
}

// Create a singleton instance
export const chatService = new ChatService()
