import React, { createContext, useContext, useState, useCallback, ReactNode, useEffect } from 'react'
import { agentService } from '@toyoura-nagisa/core'
import { AgentProfileType, AgentProfileInfo } from '@toyoura-nagisa/core'

interface AgentContextType {
  // Agent profile state (frontend only)
  currentProfile: AgentProfileType
  setCurrentProfile: (profile: AgentProfileType) => void
  availableProfiles: AgentProfileInfo[]
  isProfileLoading: boolean
  refreshProfiles: () => Promise<void>
}

const AgentContext = createContext<AgentContextType | undefined>(undefined)

export const useAgent = (): AgentContextType => {
  const context = useContext(AgentContext)
  if (!context) {
    throw new Error('useAgent must be used within an AgentProvider')
  }
  return context
}

interface AgentProviderProps {
  children: ReactNode
}

export const AgentProvider: React.FC<AgentProviderProps> = ({ children }) => {
  // Agent profile state
  const [currentProfile, setCurrentProfile] = useState<AgentProfileType>(AgentProfileType.GENERAL)
  const [availableProfiles, setAvailableProfiles] = useState<AgentProfileInfo[]>([])
  const [isProfileLoading, setIsProfileLoading] = useState<boolean>(false)

  // Load available profiles on mount
  useEffect(() => {
    refreshProfiles()
  }, [])

  // Refresh available profiles from backend
  const refreshProfiles = useCallback(async (): Promise<void> => {
    setIsProfileLoading(true)
    try {
      // HttpClient unwraps ApiResponse, so we get ProfileListData directly
      const data = await agentService.getAvailableProfiles()
      // Convert backend format to frontend format
      const profiles: AgentProfileInfo[] = data.profiles.map(p => ({
        profile_type: p.profile_type as AgentProfileType,
        name: p.name,
        description: p.description,
        tool_count: p.tool_count,
        estimated_tokens: p.estimated_tokens,
        color: p.color,
        icon: p.icon
      }))
      setAvailableProfiles(profiles)
    } catch (error) {
      console.error('Failed to load agent profiles:', error)
    } finally {
      setIsProfileLoading(false)
    }
  }, [])

  return (
    <AgentContext.Provider value={{
      currentProfile,
      setCurrentProfile,
      availableProfiles,
      isProfileLoading,
      refreshProfiles
    }}>
      {children}
    </AgentContext.Provider>
  )
}