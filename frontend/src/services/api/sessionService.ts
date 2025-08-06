/**
 * Session API service for handling chat session management operations.
 * 
 * Provides methods for creating, switching, deleting sessions, and managing
 * session-related functionality in the aiNagisa application.
 */

import { apiClient } from './httpClient'
import { ChatSession } from '../../types/chat'

export interface CreateSessionRequest {
  name?: string
}

export interface CreateSessionResponse {
  session_id: string
  name?: string
}

export interface SwitchSessionRequest {
  session_id: string
}

export interface SessionHistoryResponse {
  history: Array<{
    id?: string
    role: string
    content: any
    timestamp?: string
    tool_request?: boolean
    tool_calls?: any[]
    tool_state?: {
      is_using_tool?: boolean
      tool_name?: string
      action?: string
    }
    image_path?: string
  }>
}

export interface GenerateTitleRequest {
  session_id: string
}

export interface GenerateTitleResponse {
  success: boolean
  title: string
}

export class SessionService {
  /**
   * Retrieve all available chat sessions for the current user.
   * 
   * @returns Promise resolving to array of chat sessions
   */
  async getSessions(): Promise<ChatSession[]> {
    return await apiClient.get<ChatSession[]>('/api/history/sessions')
  }

  /**
   * Create a new chat session with optional name.
   * 
   * @param name - Optional session name
   * @returns Promise resolving to new session details
   */
  async createSession(name?: string): Promise<CreateSessionResponse> {
    const request: CreateSessionRequest = name ? { name } : {}
    return await apiClient.post<CreateSessionResponse>('/api/history/create', request)
  }

  /**
   * Switch to a different chat session and load its history.
   * 
   * @param sessionId - ID of session to switch to
   * @returns Promise resolving when session switch is complete
   */
  async switchSession(sessionId: string): Promise<void> {
    const request: SwitchSessionRequest = { session_id: sessionId }
    await apiClient.post<void>('/api/history/switch', request)
  }

  /**
   * Get the message history for a specific session.
   * 
   * @param sessionId - ID of session to get history for
   * @returns Promise resolving to session history data
   */
  async getSessionHistory(sessionId: string): Promise<SessionHistoryResponse> {
    return await apiClient.get<SessionHistoryResponse>(`/api/history/${sessionId}`)
  }

  /**
   * Delete a chat session permanently.
   * 
   * @param sessionId - ID of session to delete
   * @returns Promise resolving when session is deleted
   */
  async deleteSession(sessionId: string): Promise<void> {
    await apiClient.delete<void>(`/api/history/${sessionId}`)
  }

  /**
   * Generate an AI-powered title for a chat session based on its content.
   * 
   * @param sessionId - ID of session to generate title for
   * @returns Promise resolving to title generation result
   */
  async generateTitle(sessionId: string): Promise<GenerateTitleResponse> {
    const request: GenerateTitleRequest = { session_id: sessionId }
    return await apiClient.post<GenerateTitleResponse>('/api/history/generate-title', request)
  }
}

// Create a singleton instance
export const sessionService = new SessionService()