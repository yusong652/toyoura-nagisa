/**
 * Tool API service for handling tool and TTS configuration.
 * 
 * Provides methods for managing tool enablement status and TTS settings
 * in the toyoura-nagisa application.
 */

import { apiClient } from './HttpClient'

export interface UpdateToolsEnabledRequest {
  enabled: boolean
}

export interface UpdateToolsEnabledResponse {
  success: boolean
  tools_enabled: boolean
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
}

// Create a singleton instance
export const toolService = new ToolService()