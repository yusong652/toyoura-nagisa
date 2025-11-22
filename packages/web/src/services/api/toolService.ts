/**
 * Tool API service for handling tool and TTS configuration.
 * 
 * Provides methods for managing tool enablement status and TTS settings
 * in the aiNagisa application.
 */

import { apiClient } from './httpClient'

export interface UpdateToolsEnabledRequest {
  enabled: boolean
}

export interface UpdateToolsEnabledResponse {
  success: boolean
  tools_enabled: boolean
}

export interface UpdateTtsEnabledRequest {
  enabled: boolean
}

export interface UpdateTtsEnabledResponse {
  tts_enabled: boolean
}

export class ToolService {
  /**
   * Update the global tools enabled/disabled setting.
   * 
   * @param enabled - Whether tools should be enabled
   * @returns Promise resolving to updated tools status
   */
  async updateToolsEnabled(enabled: boolean): Promise<UpdateToolsEnabledResponse> {
    const request: UpdateToolsEnabledRequest = { enabled }
    return await apiClient.post<UpdateToolsEnabledResponse>('/api/chat/tools-enabled', request)
  }

  /**
   * Update the global TTS enabled/disabled setting.
   * 
   * @param enabled - Whether TTS should be enabled
   * @returns Promise resolving to updated TTS status
   */
  async updateTtsEnabled(enabled: boolean): Promise<UpdateTtsEnabledResponse> {
    const request: UpdateTtsEnabledRequest = { enabled }
    return await apiClient.post<UpdateTtsEnabledResponse>('/api/chat/tts-enabled', request)
  }
}

// Create a singleton instance
export const toolService = new ToolService()