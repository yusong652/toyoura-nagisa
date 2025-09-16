/**
 * Chat API service for handling message-related operations.
 *
 * Provides methods for sending messages via WebSocket, deleting messages,
 * and managing chat-related functionality in the aiNagisa application.
 *
 * Note: Chat messaging has been migrated from HTTP SSE to WebSocket for
 * better real-time performance and unified architecture.
 */

import { apiClient } from './httpClient'
import { FileData } from '../../types/chat'

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
  agent_profile: string
  tts_enabled: boolean
  enable_memory?: boolean
}

export interface MessageDeleteRequest {
  session_id: string
  message_id: string
}

export interface MessageDeleteResponse {
  success: boolean
  detail?: string
}

export class ChatService {
  /**
   * Send a chat message via WebSocket connection.
   *
   * @param text - Message text content
   * @param files - Optional file attachments
   * @param sessionId - Current session identifier
   * @param userMessageId - Unique identifier for the user message
   * @param agentProfile - Agent profile for tool selection
   * @param ttsEnabled - Whether TTS is enabled for response
   * @param memoryEnabled - Whether memory injection is enabled (default: true)
   * @returns Promise resolving to mock Response for compatibility (WebSocket doesn't return Response)
   */
  async sendMessage(
    text: string,
    files: FileData[] = [],
    sessionId: string,
    userMessageId: string,
    agentProfile: string,
    ttsEnabled: boolean,
    memoryEnabled: boolean = true
  ): Promise<Response> {
    // Get WebSocket connection from connection context
    let wsRef = this.getWebSocketConnection()

    // If WebSocket is not ready, try to wait for connection
    if (!wsRef || wsRef.readyState !== WebSocket.OPEN) {
      console.log('[ChatService] WebSocket not ready, attempting to wait for connection...')

      // Try to get connection via context (if available)
      const waitForConnection = (window as any).__waitForConnection
      if (waitForConnection) {
        const connected = await waitForConnection(5000) // 5 second timeout
        if (connected) {
          wsRef = this.getWebSocketConnection()
        }
      }

      // Final check
      if (!wsRef) {
        throw new Error('WebSocket connection not established. Please check your connection and try again.')
      }

      if (wsRef.readyState !== WebSocket.OPEN) {
        throw new Error(`WebSocket connection not ready (${this.getReadyStateText(wsRef.readyState)}). Please wait for connection to establish.`)
      }
    }

    // Create WebSocket message format
    const websocketMessage = {
      type: 'CHAT_MESSAGE',
      session_id: sessionId,
      message_id: userMessageId,
      message: text,
      agent_profile: agentProfile,
      enable_memory: memoryEnabled,
      tts_enabled: ttsEnabled,
      files: files.map(file => ({
        name: file.name,
        type: file.type,
        data: file.data
      })),
      stream_response: true,
      timestamp: new Date().toISOString()
    }

    // Send via WebSocket
    wsRef.send(JSON.stringify(websocketMessage))

    // Return mock Response for compatibility with existing code
    // The actual response will come via WebSocket events
    return new Response('{"status": "sent_via_websocket"}', {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    })
  }

  /**
   * Get WebSocket connection from global context.
   *
   * @returns WebSocket connection or null if not available
   */
  private getWebSocketConnection(): WebSocket | null {
    // First try to get from window global (set by ConnectionContext)
    const wsConnection = (window as any).__wsConnection

    if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
      return wsConnection
    }

    // If not available, log debug info
    console.debug('[ChatService] WebSocket connection status:', {
      exists: !!wsConnection,
      readyState: wsConnection?.readyState,
      readyStateText: this.getReadyStateText(wsConnection?.readyState)
    })

    return null
  }

  /**
   * Get human-readable WebSocket ready state text.
   */
  private getReadyStateText(readyState: number | undefined): string {
    switch (readyState) {
      case WebSocket.CONNECTING: return 'CONNECTING'
      case WebSocket.OPEN: return 'OPEN'
      case WebSocket.CLOSING: return 'CLOSING'
      case WebSocket.CLOSED: return 'CLOSED'
      default: return 'UNKNOWN'
    }
  }

  /**
   * Delete a specific message from a chat session.
   * 
   * @param sessionId - Session containing the message
   * @param messageId - Unique identifier of message to delete
   * @returns Promise resolving to deletion result
   */
  async deleteMessage(sessionId: string, messageId: string): Promise<MessageDeleteResponse> {
    const request: MessageDeleteRequest = {
      session_id: sessionId,
      message_id: messageId
    }

    return await apiClient.post<MessageDeleteResponse>('/api/messages/delete', request)
  }

  /**
   * Generate an AI-created image for the current session.
   * 
   * @param sessionId - Session to generate image for
   * @returns Promise resolving to image generation result
   */
  async generateImage(sessionId: string): Promise<{
    success: boolean
    image_path?: string
    error?: string
  }> {
    try {
      const response = await apiClient.post<{
        success: boolean
        image_path?: string
        error?: string
      }>('/api/generate-image', { session_id: sessionId })
      
      return response
    } catch (error: any) {
      return { 
        success: false, 
        error: error.message || 'Network error during image generation' 
      }
    }
  }

  /**
   * Generate a video from the most recent image in the session.
   * 
   * @param sessionId - Session containing the image to convert to video
   * @param motionStyle - Optional motion style for the video generation
   * @returns Promise resolving to video generation result
   */
  async generateVideo(sessionId: string, motionStyle?: string): Promise<{
    success: boolean
    video_path?: string
    error?: string
  }> {
    try {
      const response = await apiClient.post<{
        success: boolean
        video_path?: string
        error?: string
      }>('/api/generate-video', { 
        session_id: sessionId,
        motion_style: motionStyle
      })
      
      return response
    } catch (error: any) {
      return { 
        success: false, 
        error: error.message || 'Network error during video generation' 
      }
    }
  }
}

// Create a singleton instance
export const chatService = new ChatService()