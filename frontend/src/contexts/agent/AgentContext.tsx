import React, { createContext, useContext, useState, useCallback, ReactNode, useEffect } from 'react'
import { toolService, agentService } from '../../services/api'
import { ToolState } from '../../types/tools'
import { AgentProfileType, AgentProfileInfo } from '../../types/agent'

interface AgentContextType {
  // Tool-related state
  toolState: ToolState | null
  toolsEnabled: boolean
  updateToolsEnabled: (enabled: boolean) => Promise<void>
  setToolState: (state: ToolState | null) => void
  
  // Agent profile state
  currentProfile: AgentProfileType
  availableProfiles: AgentProfileInfo[]
  isProfileLoading: boolean
  updateAgentProfile: (profile: AgentProfileType) => Promise<void>
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
  // Tool state management
  const [toolState, setToolState] = useState<ToolState | null>(null)
  const [toolsEnabled, setToolsEnabled] = useState<boolean>(false)
  
  // Agent profile state
  const [currentProfile, setCurrentProfile] = useState<AgentProfileType>(AgentProfileType.GENERAL)
  const [availableProfiles, setAvailableProfiles] = useState<AgentProfileInfo[]>([])
  const [isProfileLoading, setIsProfileLoading] = useState<boolean>(false)

  // Load available profiles on mount
  useEffect(() => {
    refreshProfiles()
  }, [])

  // Update tools enabled status (legacy support)
  const updateToolsEnabled = useCallback(async (enabled: boolean): Promise<void> => {
    try {
      const data = await toolService.updateToolsEnabled(enabled)
      if (data.success) {
        setToolsEnabled(data.tools_enabled)
      }
    } catch (error) {
      console.error('Failed to update tools status:', error)
      throw error
    }
  }, [])

  // Refresh available profiles
  const refreshProfiles = useCallback(async (): Promise<void> => {
    try {
      const data = await agentService.getAvailableProfiles()
      if (data.success) {
        setAvailableProfiles(data.available_profiles)
        setCurrentProfile(data.current_profile)
        // Update tools enabled based on current profile
        setToolsEnabled(data.current_profile !== AgentProfileType.DISABLED)
      }
    } catch (error) {
      console.error('Failed to load agent profiles:', error)
    }
  }, [])

  // Update agent profile
  const updateAgentProfile = useCallback(async (profile: AgentProfileType): Promise<void> => {
    setIsProfileLoading(true)
    try {
      // TODO: Get current session ID from session context
      const sessionId = undefined // We'll need to get this from useSession()
      
      const data = await agentService.updateAgentProfile(profile, sessionId)
      if (data.success) {
        setCurrentProfile(data.current_profile)
        setToolsEnabled(data.tools_enabled)
        
        // Update the profile info in availableProfiles
        setAvailableProfiles(prev => 
          prev.map(p => 
            p.profile_type === profile ? data.profile_info : p
          )
        )
      }
    } catch (error) {
      console.error('Failed to update agent profile:', error)
      throw error
    } finally {
      setIsProfileLoading(false)
    }
  }, [])

  return (
    <AgentContext.Provider value={{
      toolState,
      toolsEnabled,
      updateToolsEnabled,
      setToolState,
      currentProfile,
      availableProfiles,
      isProfileLoading,
      updateAgentProfile,
      refreshProfiles
    }}>
      {children}
    </AgentContext.Provider>
  )
}