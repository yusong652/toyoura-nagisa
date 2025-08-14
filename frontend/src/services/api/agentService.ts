import { apiClient } from './httpClient'
import { 
  AgentProfileType, 
  UpdateAgentProfileRequest, 
  AgentProfileResponse, 
  GetAgentProfilesResponse 
} from '../../types/agent'

export class AgentService {
  /**
   * Update agent profile
   * @param profile - Agent profile type to switch to
   * @param sessionId - Optional session ID for cache clearing
   * @returns Promise resolving to updated agent profile info
   */
  async updateAgentProfile(profile: AgentProfileType, sessionId?: string): Promise<AgentProfileResponse> {
    const request: UpdateAgentProfileRequest = { 
      profile,
      session_id: sessionId
    }
    return await apiClient.post<AgentProfileResponse>('/api/agent/profile', request)
  }

  /**
   * Get all available agent profiles
   * @returns Promise resolving to list of available profiles
   */
  async getAvailableProfiles(): Promise<GetAgentProfilesResponse> {
    return await apiClient.get<GetAgentProfilesResponse>('/api/agent/profiles')
  }

  /**
   * Get current agent status
   * @returns Promise resolving to current agent status info
   */
  async getAgentStatus(): Promise<any> {
    return await apiClient.get<any>('/api/agent/status')
  }
}

export const agentService = new AgentService()