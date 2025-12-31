import { apiClient } from './HttpClient'

interface ProfileInfo {
  profile_type: string
  name: string
  description: string
  tool_count: number
  estimated_tokens: number
  color: string
  icon: string
}

interface ProfileListData {
  profiles: ProfileInfo[]
}

export class AgentService {
  /**
   * Get all available agent profiles with their metadata.
   *
   * Note: HttpClient automatically unwraps ApiResponse format,
   * so this returns the data payload directly (ProfileListData).
   *
   * @returns Promise resolving to list of available profiles
   */
  async getAvailableProfiles(): Promise<ProfileListData> {
    return await apiClient.get<ProfileListData>('/api/profiles')
  }
}

export const agentService = new AgentService()