import { apiClient } from './httpClient'

interface ProfileInfo {
  profile_type: string
  name: string
  description: string
  tool_count: number
  estimated_tokens: number
  color: string
  icon: string
}

interface GetProfilesResponse {
  success: boolean
  profiles: ProfileInfo[]
  message?: string
  error?: string
}

export class AgentService {
  /**
   * Get all available agent profiles with their metadata
   * @returns Promise resolving to list of available profiles
   */
  async getAvailableProfiles(): Promise<GetProfilesResponse> {
    return await apiClient.get<GetProfilesResponse>('/api/profiles')
  }
}

export const agentService = new AgentService()