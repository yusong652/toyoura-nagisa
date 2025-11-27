/**
 * Chat API service for handling message-related operations.
 *
 * Provides methods for sending messages via WebSocket, deleting messages,
 * and managing chat-related functionality in the aiNagisa application.
 *
 * Note: Chat messaging has been migrated from HTTP SSE to WebSocket for
 * better real-time performance and unified architecture.
 */

import { apiClient } from './HttpClient'
import type { FileData } from '../types'

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
  mentioned_files?: string[]  // File paths from @ mentions (frontend-confirmed)
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
   * Note: This method requires a WebSocket connection to be provided via setWebSocketConnection().
   * Platform-specific frontends should inject the WebSocket connection before calling this method.
   *
   * @param text - Message text content
   * @param files - Optional file attachments
   * @param sessionId - Current session identifier
   * @param userMessageId - Unique identifier for the user message
   * @param agentProfile - Agent profile for tool selection
   * @param ttsEnabled - Whether TTS is enabled for response
   * @param memoryEnabled - Whether memory injection is enabled (default: true)
   * @param mentionedFiles - Optional file paths from @ mentions (frontend-confirmed)
   * @returns Promise resolving to mock Response for compatibility (WebSocket doesn't return Response)
   */
  async sendMessage(
    text: string,
    files: FileData[] = [],
    sessionId: string,
    userMessageId: string,
    agentProfile: string,
    ttsEnabled: boolean,
    memoryEnabled: boolean = true,
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