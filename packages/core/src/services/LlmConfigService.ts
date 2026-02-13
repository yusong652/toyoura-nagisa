/**
 * LLM Configuration API service.
 * 
 * Provides methods for managing LLM provider and model configuration.
 */

import { apiClient } from './HttpClient.js'
import type { ChatSession } from '../types/index.js'

export interface ModelDetails {
  id: string
  name: string
  description?: string
  context_window?: number
}

export interface ProviderInfo {
  provider: string
  name: string
  description: string
  models: ModelDetails[]
  api_key_configured: boolean
}

export interface ProviderListResponse {
  providers: ProviderInfo[]
}

export interface LlmConfigUpdateData {
  provider: string
  model: string
  secondary_model?: string
}

export class LlmConfigService {
  /**
   * Get current LLM configuration.
   * 
   * @param sessionId - Optional session ID for session override
   * @returns Promise resolving to current LLM configuration
   */
  async getLlmConfig(sessionId?: string): Promise<LlmConfigUpdateData | null> {
    const url = sessionId ? `/api/llm-config?session_id=${sessionId}` : '/api/llm-config'
    return await apiClient.get<LlmConfigUpdateData | null>(url)
  }

  /**
   * Update LLM configuration.
   * 
   * @param config - New configuration
   * @param sessionId - Session ID for session override
   * @returns Promise resolving to updated configuration
   */
  async updateLlmConfig(config: LlmConfigUpdateData, sessionId: string): Promise<LlmConfigUpdateData> {
    const url = `/api/llm-config?session_id=${sessionId}`
    return await apiClient.post<LlmConfigUpdateData>(url, config)
  }

  /**
   * Get available providers and models.
   * 
   * @returns Promise resolving to provider list
   */
  async getProviders(): Promise<ProviderListResponse> {
    return await apiClient.get<ProviderListResponse>('/api/llm-config/providers')
  }

  /**
   * Get details for a specific model, including context window.
   * 
   * @param provider - Provider identifier
   * @param model - Model identifier
   * @returns Promise resolving to model details
   */
  async getModelDetails(provider: string, model: string): Promise<ModelDetails> {
    return await apiClient.get<ModelDetails>(`/api/llm-config/model-details?provider=${provider}&model=${model}`)
  }
}

// Create a singleton instance
export const llmConfigService = new LlmConfigService()
