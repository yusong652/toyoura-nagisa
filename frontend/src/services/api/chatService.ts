/**
 * Chat API service for handling message-related operations.
 * 
 * Provides methods for sending messages, processing streams, deleting messages,
 * and managing chat-related functionality in the aiNagisa application.
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
  tts_enabled: boolean
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
   * Send a chat message and return streaming response for processing.
   * 
   * @param text - Message text content
   * @param files - Optional file attachments
   * @param sessionId - Current session identifier
   * @param userMessageId - Unique identifier for the user message
   * @param ttsEnabled - Whether TTS is enabled for response
   * @returns Promise resolving to Response object for stream processing
   */
  async sendMessage(
    text: string,
    files: FileData[] = [],
    sessionId: string,
    userMessageId: string,
    ttsEnabled: boolean
  ): Promise<Response> {
    const messageData: MessageRequest = {
      id: userMessageId,
      text,
      timestamp: Date.now(),
      files: files.map(file => ({
        name: file.name,
        type: file.type,
        data: file.data
      }))
    }

    const streamRequest: ChatStreamRequest = {
      messageData: JSON.stringify(messageData),
      session_id: sessionId,
      tts_enabled: ttsEnabled
    }

    return await apiClient.postStream('/api/chat/stream', streamRequest)
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