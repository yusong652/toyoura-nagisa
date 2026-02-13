/**
 * Session API service for handling chat session management operations.
 * 
 * Provides methods for creating, switching, deleting sessions, and managing
 * session-related functionality in the toyoura-nagisa application.
 */

import { apiClient } from './HttpClient.js'
import type { ChatSession, SessionMode } from '../types/index.js'

export interface CreateSessionRequest {
  name?: string
  workspace_root?: string
}

export interface CreateSessionResponse {
  session_id: string
  name?: string
  llm_config?: ChatSession['llm_config']
}

export interface SwitchSessionRequest {
  session_id: string
}

export interface SessionHistoryResponse {
  session: ChatSession;
  history: Array<{
    id?: string
    role: string
    content: any
    timestamp?: string
    tool_request?: boolean
    tool_calls?: any[]
    image_path?: string
    video_path?: string
  }>
  message_count: number
}

export interface GenerateTitleRequest {
  session_id: string
}

export interface GenerateTitleData {
  session_id: string
  title: string
}

export interface TokenUsageResponse {
  prompt_tokens?: number
  completion_tokens?: number
  total_tokens?: number
  tokens_left?: number
}

export interface UpdateSessionModeRequest {
  mode: SessionMode
}

export interface UpdateSessionModeResponse {
  session_id: string
  mode: SessionMode
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
   * @param workspaceRoot - Optional session workspace root path
   * @returns Promise resolving to new session details
   */
  async createSession(name?: string, workspaceRoot?: string): Promise<CreateSessionResponse> {
    const request: CreateSessionRequest = {}
    if (name) {
      request.name = name
    }
    if (workspaceRoot) {
      request.workspace_root = workspaceRoot
    }
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
   * Update session mode (plan/build).
   */
  async updateSessionMode(sessionId: string, mode: SessionMode): Promise<UpdateSessionModeResponse> {
    const request: UpdateSessionModeRequest = { mode }
    return await apiClient.post<UpdateSessionModeResponse>(`/api/history/${sessionId}/mode`, request)
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
   * Note: HttpClient automatically unwraps ApiResponse format,
   * so this returns the data payload directly (GenerateTitleData).
   *
   * @param sessionId - ID of session to generate title for
   * @returns Promise resolving to title generation result
   */
  async generateTitle(sessionId: string): Promise<GenerateTitleData> {
    const request: GenerateTitleRequest = { session_id: sessionId }
    return await apiClient.post<GenerateTitleData>('/api/history/generate-title', request)
  }

  /**
   * Get token usage information for a specific session.
   *
   * Returns the latest token usage statistics from the last LLM interaction.
   * This data is persisted in runtime_state.json and survives session switches.
   *
   * @param sessionId - ID of session to get token usage for
   * @returns Promise resolving to token usage statistics or empty object
   */
  async getTokenUsage(sessionId: string): Promise<TokenUsageResponse> {
    return await apiClient.get<TokenUsageResponse>(`/api/history/${sessionId}/token-usage`)
  }
}

// Create a singleton instance
export const sessionService = new SessionService()
