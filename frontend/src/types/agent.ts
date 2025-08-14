export enum AgentProfileType {
  CODING = 'coding',
  LIFESTYLE = 'lifestyle', 
  GENERAL = 'general',
  DISABLED = 'disabled'
}

export interface AgentProfileInfo {
  profile_type: AgentProfileType
  name: string
  description: string
  tool_count: number
  estimated_tokens: number
  color: string
  icon: string
}

export interface UpdateAgentProfileRequest {
  profile: AgentProfileType
  session_id?: string
}

export interface AgentProfileResponse {
  success: boolean
  current_profile: AgentProfileType
  profile_info: AgentProfileInfo
  tools_enabled: boolean
  message: string
}

export interface GetAgentProfilesResponse {
  success: boolean
  current_profile: AgentProfileType
  available_profiles: AgentProfileInfo[]
  message: string
}