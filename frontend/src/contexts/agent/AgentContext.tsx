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

  // Refresh available profiles from backend
  const refreshProfiles = useCallback(async (): Promise<void> => {
    setIsProfileLoading(true)
    try {
      const data = await agentService.getAvailableProfiles()
      if (data.success) {
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
      }
    } catch (error) {
      console.error('Failed to load agent profiles:', error)
    } finally {
      setIsProfileLoading(false)
    }
  }, [])

  // Simple profile selection (frontend state only)
  const handleSetCurrentProfile = useCallback((profile: AgentProfileType) => {
    setCurrentProfile(profile)
    // Update tools enabled based on selected profile
    setToolsEnabled(profile !== AgentProfileType.DISABLED)
  }, [])

  return (
    <AgentContext.Provider value={{
      toolState,
      toolsEnabled,
      updateToolsEnabled,
      setToolState,
      currentProfile,
      setCurrentProfile: handleSetCurrentProfile,
      availableProfiles,
      isProfileLoading,
      refreshProfiles
    }}>
      {children}
    </AgentContext.Provider>
  )
}